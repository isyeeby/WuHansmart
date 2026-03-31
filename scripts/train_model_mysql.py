# -*- coding: utf-8 -*-
"""
民宿价格预测模型训练（MySQL / Hive ODS）— 毕业论文可用流程
==========================================================

方法论要点（便于论文「数据处理与建模」章节撰写）：
1. 划分优先：先按价格分桶做分层留出测试集，再于**训练集**上估计一切依赖标签的统计量，
   避免测试集信息通过「全区价格均值/中位数」等特征泄漏到训练过程。
2. 目标变量：对价格做 log1p 变换缓解右偏；预测后 expm1 还原，与线上一致。
3. 类别编码：district / trade_area / house_type 的整数编码仅在训练集上拟合类别表，
   测试集未见类别映射为 0；线上服务加载同一映射表，保证训练–服务一致性。
4. 经济型标记 is_budget：仅使用面积与卧室数等**结构变量**定义，不使用真实成交价，
   避免以因变量构造自变量导致的标签泄漏。
5. facility_count：定义为与模型一致的二值设施特征之和（见 app.ml.price_feature_config），
   与 API 推理侧求和方式相同。
6. 价格日历：从 price_calendars 按 unit_id 聚合均值/方差/分位数/可订比例/周末溢价等；
   与 listings.final_price 互补。缺失日历的样本在划分后仅用训练集统计量填充，避免泄漏。

运行：在 Tujia-backend 目录下
    python scripts/train_model_mysql.py
    python scripts/train_model_mysql.py --data-source hive    # 仅 Hive ODS
    python scripts/train_model_mysql.py --data-source mysql   # 仅 MySQL
    python scripts/train_model_mysql.py --data-source auto    # 优先 Hive，失败则 MySQL

环境变量 TRAIN_DATA_SOURCE=auto|hive|mysql 可覆盖默认（命令行优先）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Listing, SessionLocal
from app.ml.calendar_features import (
    CALENDAR_FEATURE_NAMES,
    impute_calendar_train_test,
    load_calendar_aggregates_for_unit_ids,
)
from app.ml.price_feature_config import (
    FACILITY_KEYWORDS,
    compute_is_budget_structural,
    ordered_facility_columns,
)
from app.ml.house_tags_text import parse_house_tags

OUTPUT_DIR = Path(__file__).parent.parent / "models"
OUTPUT_DIR.mkdir(exist_ok=True)

_FACILITY_COLS_ORDERED = ordered_facility_columns()


def apply_mysql_compatible_filters(df: pd.DataFrame) -> pd.DataFrame:
    """与 ORM 查询条件对齐：有效评分、面积、行政区。"""
    d = df["district"].fillna("").astype(str)
    return df[
        df["rating"].notna()
        & df["area"].notna()
        & df["district"].notna()
        & (d.str.len() > 0)
    ].copy()


def expand_base_dataframe(df_base: pd.DataFrame) -> pd.DataFrame:
    """
    将「基础属性 + 可选已合并的日历列」展开为训练用 DataFrame（含设施二值列与 facility_count）。
    若 df_base 已含 CALENDAR_FEATURE_NAMES，则一并写入记录；否则由调用方再 merge 日历。
    """
    has_cal = all(c in df_base.columns for c in CALENDAR_FEATURE_NAMES)
    records: List[Dict[str, Any]] = []
    for _, r in df_base.iterrows():
        tags_list = parse_house_tags(r.get("house_tags"))
        tags_set = set(tags_list)
        record: Dict[str, Any] = {
            "unit_id": r["unit_id"],
            "price": float(r["price"]),
            "district": str(r.get("district") or ""),
            "trade_area": str(r.get("trade_area") or r.get("district") or ""),
            "rating": float(r["rating"] or 0),
            "area": float(r.get("area") or 50),
            "bedroom_count": int(r.get("bedroom_count") or 1),
            "bed_count": int(r.get("bed_count") or 1),
            "capacity": int(r.get("capacity") or 2),
            "favorite_count": int(r.get("favorite_count") or 0),
            "house_type": str(r.get("house_type") or "整套") or "整套",
            "latitude": float(r.get("latitude") or 0),
            "longitude": float(r.get("longitude") or 0),
        }
        for tag_name, feat_name in FACILITY_KEYWORDS.items():
            record[feat_name] = 1 if tag_name in tags_set else 0
        record["facility_count"] = sum(int(record.get(c, 0) or 0) for c in _FACILITY_COLS_ORDERED)
        if has_cal:
            for c in CALENDAR_FEATURE_NAMES:
                v = r.get(c)
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    record[c] = np.nan
                else:
                    record[c] = v
        records.append(record)
    out = pd.DataFrame(records)
    if has_cal:
        for c in CALENDAR_FEATURE_NAMES:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def load_data_from_mysql() -> pd.DataFrame:
    """从 MySQL 读取房源记录并解析设施二值特征。"""
    print("=" * 60)
    print("从 MySQL 数据库加载数据")
    print("=" * 60)

    db = SessionLocal()
    listings = (
        db.query(Listing)
        .filter(
            Listing.final_price.isnot(None),
            Listing.final_price > 0,
            Listing.rating.isnot(None),
            Listing.area.isnot(None),
            Listing.district.isnot(None),
        )
        .all()
    )
    print(f"查询到 {len(listings)} 条有效数据")

    base_rows: List[Dict[str, Any]] = []
    for l in listings:
        base_rows.append(
            {
                "unit_id": l.unit_id,
                "price": float(l.final_price),
                "district": l.district,
                "trade_area": (l.trade_area or l.district) or "",
                "rating": float(l.rating or 0),
                "area": float(l.area or 50),
                "bedroom_count": int(l.bedroom_count or 1),
                "bed_count": int(l.bed_count or 1),
                "capacity": int(l.capacity or 2),
                "favorite_count": int(l.favorite_count or 0),
                "house_type": (l.house_type or "整套") or "整套",
                "latitude": float(l.latitude or 0),
                "longitude": float(l.longitude or 0),
                "house_tags": l.house_tags,
            }
        )
    df = expand_base_dataframe(pd.DataFrame(base_rows))
    unit_ids = df["unit_id"].tolist()
    cal_df = load_calendar_aggregates_for_unit_ids(db, unit_ids)
    db.close()

    if not cal_df.empty:
        df = df.merge(cal_df, on="unit_id", how="left")
    else:
        for c in CALENDAR_FEATURE_NAMES:
            df[c] = np.nan

    covered = int((df["cal_n_days"].fillna(0) > 0).sum())
    print(f"加载完成: {len(df)} 条数据 | 含价格日历: {covered} ({covered / max(len(df), 1) * 100:.1f}%)")
    return df


def load_training_data(source: str) -> Tuple[pd.DataFrame, str]:
    """
    按数据来源加载与 MySQL 路径列结构一致的训练表。
    auto：优先 Hive ODS（样本数满足阈值），否则 MySQL。
    """
    from app.ml.hive_training_loader import try_load_training_frame_from_hive

    min_auto = 100
    min_hive = 50

    if source == "mysql":
        return load_data_from_mysql(), "MySQL Database"

    if source == "hive":
        print("=" * 60)
        print("从 Hive ODS 加载数据（ods_listings + ods_price_calendar）")
        print("=" * 60)
        base, note = try_load_training_frame_from_hive(min_rows=min_hive)
        if base is None:
            print(f"错误: 无法从 Hive 加载训练数据 ({note})")
            sys.exit(1)
        df = expand_base_dataframe(base)
        df = apply_mysql_compatible_filters(df)
        if len(df) < min_hive:
            print(f"错误: Hive 数据经与 MySQL 对齐的过滤后不足 {min_hive} 条，当前 {len(df)}")
            sys.exit(1)
        covered = int((df["cal_n_days"].fillna(0) > 0).sum())
        print(
            f"加载完成: {len(df)} 条 | 含价格日历: {covered} ({covered / max(len(df), 1) * 100:.1f}%)"
        )
        return df, f"Hive ODS ({note})"

    # auto
    print("=" * 60)
    print("数据来源: auto（优先 Hive ODS，不可用则 MySQL）")
    print("=" * 60)
    base, note = try_load_training_frame_from_hive(min_rows=min_auto)
    if base is not None and len(base) >= min_auto:
        df = expand_base_dataframe(base)
        df = apply_mysql_compatible_filters(df)
        if len(df) >= min_auto:
            covered = int((df["cal_n_days"].fillna(0) > 0).sum())
            print(
                f"Hive 加载完成: {len(df)} 条 | 含价格日历: {covered} ({covered / max(len(df), 1) * 100:.1f}%)"
            )
            return df, f"Hive ODS ({note})"
    print("Hive 不可用或过滤后样本不足，回退 MySQL")
    return load_data_from_mysql(), "MySQL Database (auto fallback)"


def price_bucket(price: float) -> int:
    if price < 100:
        return 0
    if price < 300:
        return 1
    return 2


def stratified_holdout(
    df: pd.DataFrame, n_splits: int = 5, random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    分层留出：与单折 80/20 等价（取 StratifiedKFold 的第一折），保证分桶比例稳定。
    论文中可表述为 stratified hold-out validation, 80%/20%。
    """
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    y_strat = df["price_bucket"].values
    for train_idx, test_idx in skf.split(np.zeros(len(df)), y_strat):
        return df.iloc[train_idx].copy(), df.iloc[test_idx].copy()
    raise RuntimeError("StratifiedKFold 未产生划分")


def _category_map(series: pd.Series) -> Dict[str, int]:
    """在训练集上拟合类别 -> 整数编码（按字典序稳定可复现）。"""
    s = series.fillna("").astype(str)
    cats = sorted(s.unique())
    return {c: i for i, c in enumerate(cats)}


def _apply_category_map(series: pd.Series, mapping: Dict[str, int], default: int = 0) -> pd.Series:
    return series.fillna("").astype(str).map(lambda x: mapping.get(x, default))


def preprocess_after_split(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any], pd.DataFrame, List[str], Dict[str, float]]:
    """
    在训练/测试划分之后：仅用训练集估计行政区目标编码与类别映射，再变换两侧数据。
    """
    print("\n" + "=" * 60)
    print("数据预处理（无标签泄漏：目标编码与编码器仅基于训练集）")
    print("=" * 60)

    # 训练集内：样本数足够的行政区
    dist_counts = train_df.groupby("district").size()
    valid_districts = dist_counts[dist_counts >= 5].index.tolist()
    train_df = train_df[train_df["district"].isin(valid_districts)].copy()
    test_df = test_df[test_df["district"].isin(valid_districts)].copy()
    print(f"训练集行政区过滤(训练内 n>=5): 训练 {len(train_df)} 条, 测试 {len(test_df)} 条")

    # —— 以下聚合仅使用训练集价格，避免测试集标签泄漏 ——
    district_stats = (
        train_df.groupby("district")["price"]
        .agg(dist_mean="mean", dist_median="median", dist_std="std", dist_count="count")
        .reset_index()
    )
    g_mean = float(train_df["price"].mean())
    g_median = float(train_df["price"].median())
    g_std = float(train_df["price"].std()) if len(train_df) > 1 else 0.0
    g_count = int(len(train_df))

    train_df = train_df.merge(district_stats, on="district", how="left")
    test_df = test_df.merge(district_stats, on="district", how="left")

    for col, gv in [
        ("dist_mean", g_mean),
        ("dist_median", g_median),
        ("dist_std", g_std),
        ("dist_count", float(g_count)),
    ]:
        train_df[col] = train_df[col].fillna(gv)
        test_df[col] = test_df[col].fillna(gv)

    train_df["dist_std"] = train_df["dist_std"].fillna(0)
    test_df["dist_std"] = test_df["dist_std"].fillna(0)

    district_map = _category_map(train_df["district"])
    trade_area_map = _category_map(train_df["trade_area"])
    house_type_map = _category_map(train_df["house_type"])

    train_df["district_encoded"] = _apply_category_map(train_df["district"], district_map)
    test_df["district_encoded"] = _apply_category_map(test_df["district"], district_map)
    train_df["trade_area_encoded"] = _apply_category_map(train_df["trade_area"], trade_area_map)
    test_df["trade_area_encoded"] = _apply_category_map(test_df["trade_area"], trade_area_map)
    train_df["house_type_encoded"] = _apply_category_map(train_df["house_type"], house_type_map)
    test_df["house_type_encoded"] = _apply_category_map(test_df["house_type"], house_type_map)

    train_df["rating"] = train_df["rating"].fillna(train_df["rating"].median())
    test_df["rating"] = test_df["rating"].fillna(train_df["rating"].median())
    train_df["favorite_count"] = train_df["favorite_count"].fillna(0)
    test_df["favorite_count"] = test_df["favorite_count"].fillna(0)
    train_df["capacity"] = train_df["capacity"].fillna(train_df["bedroom_count"] * 2)
    test_df["capacity"] = test_df["capacity"].fillna(test_df["bedroom_count"] * 2)
    train_df["bed_count"] = train_df["bed_count"].fillna(train_df["bedroom_count"])
    test_df["bed_count"] = test_df["bed_count"].fillna(test_df["bedroom_count"])

    train_df["area_per_bedroom"] = train_df["area"] / (train_df["bedroom_count"] + 1)
    test_df["area_per_bedroom"] = test_df["area"] / (test_df["bedroom_count"] + 1)
    train_df["heat_score"] = train_df["rating"] * np.log1p(train_df["favorite_count"])
    test_df["heat_score"] = test_df["rating"] * np.log1p(test_df["favorite_count"])

    train_df["is_large"] = ((train_df["bedroom_count"] >= 4) | (train_df["area"] >= 150)).astype(int)
    test_df["is_large"] = ((test_df["bedroom_count"] >= 4) | (test_df["area"] >= 150)).astype(int)
    train_df["is_budget"] = [
        compute_is_budget_structural(a, b)
        for a, b in zip(train_df["area"], train_df["bedroom_count"])
    ]
    test_df["is_budget"] = [
        compute_is_budget_structural(a, b)
        for a, b in zip(test_df["area"], test_df["bedroom_count"])
    ]

    train_df, test_df, calendar_defaults = impute_calendar_train_test(train_df, test_df)

    num_features = [
        "rating",
        "area",
        "bedroom_count",
        "bed_count",
        "capacity",
        "favorite_count",
        "latitude",
        "longitude",
        "is_large",
        "is_budget",
    ]
    loc_features = [
        "district_encoded",
        "trade_area_encoded",
        "dist_mean",
        "dist_median",
        "dist_std",
        "dist_count",
        "house_type_encoded",
    ]
    facility_cols = list(dict.fromkeys(FACILITY_KEYWORDS.values()))
    interaction_features = ["area_per_bedroom", "heat_score", "facility_count"]
    feature_cols = (
        num_features + loc_features + facility_cols + interaction_features + CALENDAR_FEATURE_NAMES
    )
    feature_cols = [c for c in feature_cols if c in train_df.columns]

    for col in feature_cols:
        if col in train_df.columns and train_df[col].isna().any():
            train_df[col] = train_df[col].fillna(0)
        if col in test_df.columns and test_df[col].isna().any():
            test_df[col] = test_df[col].fillna(0)

    encoders = {
        "district": {k: int(v) for k, v in district_map.items()},
        "trade_area": {k: int(v) for k, v in trade_area_map.items()},
        "house_type": {k: int(v) for k, v in house_type_map.items()},
    }

    print(f"预处理完成: 特征数 {len(feature_cols)}（含日历 {len(CALENDAR_FEATURE_NAMES)} 维）")
    return train_df, test_df, encoders, district_stats, feature_cols, calendar_defaults


def train_xgb_model(
    train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]
) -> Tuple[Any, Dict[str, float], Dict[str, float], pd.DataFrame]:
    print("\n" + "=" * 60)
    print("模型训练 (XGBoost + 对数目标 + 样本权重)")
    print("=" * 60)

    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train_log = train_df["price_log"]
    y_test_log = test_df["price_log"]
    y_train_raw = train_df["price"]
    y_test_raw = test_df["price"]

    def get_weight(price: float) -> float:
        if price < 100:
            return 2.0
        if price > 500:
            return 1.5
        return 1.0

    weights = y_train_raw.apply(get_weight)

    params = {
        "objective": "reg:squarederror",
        "max_depth": 6,
        "min_child_weight": 3,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "learning_rate": 0.05,
        "n_estimators": 600,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "n_jobs": -1,
    }

    model = xgb.XGBRegressor(**params)
    # 部分环境下 sklearn 封装的 fit 不支持 early_stopping/callbacks，仅用 eval_set 监控
    model.fit(
        X_train,
        y_train_log,
        sample_weight=weights,
        eval_set=[(X_test, y_test_log)],
        verbose=False,
    )

    y_pred_train = np.expm1(model.predict(X_train))
    y_pred_test = np.expm1(model.predict(X_test))

    def evaluate(y_true: np.ndarray, y_pred: np.ndarray, name: str) -> Dict[str, float]:
        mae = mean_absolute_error(y_true, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = r2_score(y_true, y_pred)
        mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
        print(f"\n{name}:")
        print(f"  MAE:  {mae:.2f} 元")
        print(f"  RMSE: {rmse:.2f} 元")
        print(f"  R²:   {r2:.4f}")
        print(f"  MAPE: {mape:.1f}%")
        return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}

    train_metrics = evaluate(y_train_raw.values, y_pred_train, "训练集")
    test_metrics = evaluate(y_test_raw.values, y_pred_test, "测试集")

    print("\n" + "-" * 40)
    print("分价格区间评估 (测试集)")
    print("-" * 40)
    test_results = pd.DataFrame({"true": y_test_raw.values, "pred": y_pred_test})
    for low, high, label in [
        (50, 100, "低价(50-100)"),
        (100, 300, "中价(100-300)"),
        (300, 5000, "高价(>300)"),
    ]:
        subset = test_results[(test_results["true"] >= low) & (test_results["true"] < high)]
        if len(subset) > 0:
            mae = mean_absolute_error(subset["true"], subset["pred"])
            mape = float(np.mean(np.abs((subset["true"] - subset["pred"]) / subset["true"])) * 100)
            print(f"  {label}: {len(subset)}条, MAE={mae:.0f}元, MAPE={mape:.1f}%")

    importance = pd.DataFrame(
        {"feature": feature_cols, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)
    print("\n特征重要性 Top 10:")
    print(importance.head(10).to_string(index=False))

    return model, train_metrics, test_metrics, importance


def save_artifacts(
    model: Any,
    feature_cols: List[str],
    train_metrics: Dict[str, float],
    test_metrics: Dict[str, float],
    importance: pd.DataFrame,
    encoders: Dict[str, Any],
    district_stats: pd.DataFrame,
    n_train: int,
    n_test: int,
    price_desc: Dict[str, float],
    calendar_defaults: Dict[str, float],
    data_source_label: str,
) -> None:
    print("\n" + "=" * 60)
    print("保存模型与元数据")
    print("=" * 60)

    joblib.dump(model, OUTPUT_DIR / "xgboost_price_model_latest.pkl")
    print(f"模型: {OUTPUT_DIR / 'xgboost_price_model_latest.pkl'}")

    with open(OUTPUT_DIR / "feature_names_latest.json", "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)

    joblib.dump(encoders["district"], OUTPUT_DIR / "district_encoder_latest.pkl")
    joblib.dump(encoders["trade_area"], OUTPUT_DIR / "trade_area_encoder_latest.pkl")
    joblib.dump(encoders["house_type"], OUTPUT_DIR / "house_type_encoder_latest.pkl")
    print("编码器: district / trade_area / house_type -> *_encoder_latest.pkl")

    district_stats.to_json(
        OUTPUT_DIR / "district_stats.json", orient="records", force_ascii=False, indent=2
    )

    with open(OUTPUT_DIR / "calendar_feature_defaults.json", "w", encoding="utf-8") as f:
        json.dump(calendar_defaults, f, ensure_ascii=False, indent=2)
    print(f"日历默认特征: {OUTPUT_DIR / 'calendar_feature_defaults.json'}")

    metrics_data = {
        "metrics": test_metrics,
        "train_metrics": train_metrics,
        "trained_at": pd.Timestamp.now().isoformat(),
        "model_type": "XGBoost Regressor (log1p target)",
        "data_source": data_source_label,
        "feature_count": len(feature_cols),
        "sample_count_train": n_train,
        "sample_count_test": n_test,
        "sample_count_total": n_train + n_test,
        "price_stats": price_desc,
        "district_encoder": encoders["district"],
        "trade_area_encoder": encoders["trade_area"],
        "house_type_encoder": encoders["house_type"],
        "methodology": {
            "split": "stratified_holdout_80_20_first_fold_price_bucket",
            "target_encoding": "district price moments estimated on training split only",
            "categorical_encoding": "integer codes fitted on training split only; OOV -> 0",
            "target_transform": "log1p(price); prediction expm1",
            "is_budget_definition": "structural: area<30 and bedroom_count<=1 (no price in feature)",
            "facility_count": "sum of binary facility columns in FACILITY_KEYWORDS mapping",
            "sample_weights": "higher weight for price<100 and price>500 in training",
            "n_estimators": "600 trees; eval_set held-out log-target for monitoring (no early stop if sklearn fit API lacks callbacks)",
            "price_calendar_features": (
                "Per-unit aggregates (CALENDAR_FEATURE_NAMES): from MySQL price_calendars when "
                "training on MySQL; from Hive ODS ods_price_calendar when training on Hive "
                "(weekend premium may be 0 if not computed in the warehouse). "
                "Missing calendar imputed with train-split medians among units with calendar."
            ),
        },
        "calendar_feature_names": CALENDAR_FEATURE_NAMES,
        "improvements": [
            "no_label_leakage: 行政区统计仅训练集",
            "log_transform: 对数目标",
            "stratified_holdout: 按价格分桶分层留出",
            "sample_weight: 样本权重",
            "is_budget: 结构定义(面积+卧室数)，不含房价",
            "facility_count: 与线上一致的二值设施求和",
            "encoders: district + trade_area + house_type 持久化",
            "price_calendar: 动态定价统计特征 + 训练集条件中位数填充",
            "n_estimators=600: 固定轮数（环境不支持 fit 早停参数时）",
        ],
    }
    with open(OUTPUT_DIR / "model_metrics_latest.json", "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, ensure_ascii=False, indent=2, default=str)

    importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False, encoding="utf-8-sig")
    print(f"指标: {OUTPUT_DIR / 'model_metrics_latest.json'}")


def main() -> None:
    env_default = os.environ.get("TRAIN_DATA_SOURCE", "auto").strip().lower()
    if env_default not in ("auto", "hive", "mysql"):
        env_default = "auto"
    parser = argparse.ArgumentParser(description="民宿价格 XGBoost 训练（MySQL / Hive ODS）")
    parser.add_argument(
        "--data-source",
        choices=("auto", "hive", "mysql"),
        default=env_default,
        help="训练数据来源：auto 优先 Hive，hive/mysql 强制指定",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("民宿价格预测模型训练（论文规范流程）")
    print(f"数据模式: {args.data_source}")
    print("=" * 60)

    df, data_source_label = load_training_data(args.data_source)
    df = df[df["price"] >= 50].copy()
    # 极端高价截断（与常见民宿日价量级一致，可在论文中说明为鲁棒性处理）
    df = df[df["price"] <= 5000].copy()
    print(f"\n过滤后(50<=price<=5000): {len(df)} 条")

    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(price_bucket)

    train_df, test_df = stratified_holdout(df)
    print(f"\n划分完成: 训练 {len(train_df)} / 测试 {len(test_df)}")

    train_df, test_df, encoders, district_stats, feature_cols, calendar_defaults = (
        preprocess_after_split(train_df, test_df)
    )
    if len(train_df) < 50 or len(test_df) < 10:
        print("错误: 训练或测试样本过少，请检查数据库或过滤条件。")
        sys.exit(1)

    model, train_metrics, test_metrics, importance = train_xgb_model(
        train_df, test_df, feature_cols
    )

    full_for_stats = pd.concat([train_df, test_df], ignore_index=True)
    price_desc = {
        "min": float(full_for_stats["price"].min()),
        "max": float(full_for_stats["price"].max()),
        "mean": float(full_for_stats["price"].mean()),
        "median": float(full_for_stats["price"].median()),
    }

    save_artifacts(
        model,
        feature_cols,
        train_metrics,
        test_metrics,
        importance,
        encoders,
        district_stats,
        len(train_df),
        len(test_df),
        price_desc,
        calendar_defaults,
        data_source_label,
    )

    print("\n" + "=" * 60)
    print("训练完成")
    print("=" * 60)
    print(f"测试集 R²: {test_metrics['r2']:.4f} | MAE: {test_metrics['mae']:.2f} 元")
    if test_metrics["r2"] > 0.7:
        print("\n[提示] 测试集指标供论文引用；若与旧版偏高差异大，属泄漏消除后的正常变化。")


if __name__ == "__main__":
    main()
