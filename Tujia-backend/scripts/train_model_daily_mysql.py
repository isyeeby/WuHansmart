# -*- coding: utf-8 -*-
"""
日级价格样本 XGBoost 训练（MySQL price_calendars + listings）

任务（默认）：**房源静态特征 + 日期特征（含节假日/调休/节前节后距离/日历内偏移）→ 当日价格**，
`log1p` 目标、`expm1` 还原。与「只有房源信息、无历史日价」的推理口径一致。

可选：`--with-lags` 加入昨日价与近 7 日均价（仅作对比实验，易抬高 R²）。

划分：
  - `global`（默认）：全局唯一日期轴 70% / 15% / 15% → train/val/test；
  - `per_unit`：每套房源各自按日期 70/15/15，再合并（短于 `--per-unit-min-days` 的房源丢弃）。

产物（不覆盖房源级 models/*_latest*）：
  models/xgboost_price_daily_model.pkl
  models/xgboost_price_daily_q020.pkl / q050 / q080（分位数区间，可用 --skip-quantiles 跳过）
  models/feature_names_daily.json
  models/model_metrics_daily.json
  models/daily_forecast_meta.json（验证集 MAE，供 API 误差带兜底）
  models/daily_lag_inference_defaults.json（仅 --with-lags 时）

运行：在 Tujia-backend 目录下
  python scripts/train_model_daily_mysql.py
  python scripts/train_model_daily_mysql.py --split-mode per_unit
  python scripts/train_model_daily_mysql.py --with-lags
  python scripts/train_model_daily_mysql.py --skip-quantiles   # 仅点预测，加快训练

建议：`pip install chinesecalendar`（节前/节后距离与节假日特征）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Listing, PriceCalendar, SessionLocal
from app.ml.daily_calendar_features import (
    DATE_FEATURE_COLUMNS,
    LAG_FEATURE_COLUMNS,
    add_daily_date_features,
    add_holiday_proximity_features,
    add_prior_price_lags,
    add_unit_calendar_offset,
)
from app.ml.house_tags_text import parse_house_tags
from app.ml.price_feature_config import (
    FACILITY_KEYWORDS,
    compute_is_budget_structural,
    ordered_facility_columns,
)
from scripts.train_model_mysql import (
    OUTPUT_DIR,
    _apply_category_map,
    _build_booster_params_from_env,
    _category_map,
    _fit_xgb_booster_cold_val,
    _metrics_dict,
    _price_row_weight,
)

_FACILITY_ORDERED = ordered_facility_columns()

DAILY_MODEL_PATH = OUTPUT_DIR / "xgboost_price_daily_model.pkl"
DAILY_FEATURE_JSON = OUTPUT_DIR / "feature_names_daily.json"
DAILY_METRICS_JSON = OUTPUT_DIR / "model_metrics_daily.json"


def _listing_rows_to_dataframe(listings: List[Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for l in listings:
        rows.append(
            {
                "unit_id": str(l.unit_id),
                "district": str(l.district or ""),
                "trade_area": str(l.trade_area or l.district or ""),
                "rating": float(l.rating or 0),
                "area": float(l.area or 50),
                "bedroom_count": int(l.bedroom_count or 1),
                "bed_count": int(l.bed_count or 1),
                "capacity": int(l.capacity or 2),
                "favorite_count": int(l.favorite_count or 0),
                "house_type": str(l.house_type or "整套") or "整套",
                "latitude": float(l.latitude or 0),
                "longitude": float(l.longitude or 0),
                "house_tags": l.house_tags,
            }
        )
    return pd.DataFrame(rows)


def _expand_facilities(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for tag_name, feat_name in FACILITY_KEYWORDS.items():
        col: List[int] = []
        for _, r in out.iterrows():
            tags_set = set(parse_house_tags(r.get("house_tags")))
            col.append(1 if tag_name in tags_set else 0)
        out[feat_name] = col
    for c in _FACILITY_ORDERED:
        if c not in out.columns:
            out[c] = 0
    out["facility_count"] = out[list(_FACILITY_ORDERED)].fillna(0).astype(int).sum(axis=1)
    return out


def load_daily_mysql() -> pd.DataFrame:
    print("=" * 60)
    print("日级训练：从 MySQL 加载 listings + price_calendars")
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
    base = _listing_rows_to_dataframe(listings)
    base = _expand_facilities(base)
    uids = base["unit_id"].astype(str).tolist()
    cal_rows: List[PriceCalendar] = []
    chunk = 500
    for i in range(0, len(uids), chunk):
        batch = uids[i : i + chunk]
        cal_rows.extend(db.query(PriceCalendar).filter(PriceCalendar.unit_id.in_(batch)).all())
    db.close()

    if not cal_rows:
        print("错误: price_calendars 无数据")
        sys.exit(1)

    cal_df = pd.DataFrame(
        [
            {
                "unit_id": str(r.unit_id),
                "date": r.date,
                "price": float(r.price),
                "can_booking": float(r.can_booking if r.can_booking is not None else 1),
            }
            for r in cal_rows
        ]
    )
    cal_df["price"] = pd.to_numeric(cal_df["price"], errors="coerce")
    cal_df = cal_df[(cal_df["price"] > 0) & (cal_df["price"] >= 50) & (cal_df["price"] <= 5000)]

    drop_tags = [c for c in base.columns if c == "house_tags"]
    listing_feat = base.drop(columns=drop_tags, errors="ignore")
    df = cal_df.merge(listing_feat, on="unit_id", how="inner")
    df["calendar_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["calendar_date"])
    print(f"日级样本（初筛）: {len(df)} 条 | 房源数: {df['unit_id'].nunique()}")
    return df


def time_split_dates(
    df: pd.DataFrame, date_col: str = "calendar_date"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    work = df.copy()
    work["_dn"] = work[date_col].dt.normalize()
    udates = sorted(work["_dn"].unique())
    n = len(udates)
    if n < 5:
        print(f"错误: 唯一日期仅 {n} 天，无法做 70/15/15 时间切分")
        sys.exit(1)

    train_idx_end = max(1, int(n * 0.70))
    val_idx_end = max(train_idx_end + 1, int(n * 0.85))
    val_idx_end = min(val_idx_end, n - 1)

    train_dates = set(udates[:train_idx_end])
    val_dates = set(udates[train_idx_end:val_idx_end])
    test_dates = set(udates[val_idx_end:])

    train_df = work[work["_dn"].isin(train_dates)].drop(columns=["_dn"])
    val_df = work[work["_dn"].isin(val_dates)].drop(columns=["_dn"])
    test_df = work[work["_dn"].isin(test_dates)].drop(columns=["_dn"])

    meta = {
        "split_mode": "global",
        "n_unique_dates": n,
        "train_dates": len(train_dates),
        "val_dates": len(val_dates),
        "test_dates": len(test_dates),
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
    }
    print(
        f"时间切分: 训练日 {len(train_dates)} / 验证日 {len(val_dates)} / 测试日 {len(test_dates)} "
        f"| 行数 训练 {len(train_df)} 验证 {len(val_df)} 测试 {len(test_df)}"
    )
    return train_df, val_df, test_df, meta


def time_split_per_unit(
    df: pd.DataFrame,
    date_col: str = "calendar_date",
    min_days: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """每套房源按自身日期序列 70/15/15，再纵向合并；日历过短的房源整套丢弃。"""
    train_parts: List[pd.DataFrame] = []
    val_parts: List[pd.DataFrame] = []
    test_parts: List[pd.DataFrame] = []
    dropped = 0
    kept = 0
    for uid, g in df.groupby("unit_id", sort=False):
        g = g.copy()
        g["_dn"] = g[date_col].dt.normalize()
        udates = sorted(g["_dn"].unique())
        n = len(udates)
        if n < min_days:
            dropped += 1
            continue
        train_idx_end = max(1, int(n * 0.70))
        val_idx_end = max(train_idx_end + 1, int(n * 0.85))
        val_idx_end = min(val_idx_end, n - 1)
        td = set(udates[:train_idx_end])
        vd = set(udates[train_idx_end:val_idx_end])
        tsd = set(udates[val_idx_end:])
        train_parts.append(g[g["_dn"].isin(td)])
        val_parts.append(g[g["_dn"].isin(vd)])
        test_parts.append(g[g["_dn"].isin(tsd)])
        kept += 1
    if not train_parts:
        print("错误: per_unit 切分后无有效房源（提高 min_days 或减少过滤）")
        sys.exit(1)
    train_df = pd.concat(train_parts, ignore_index=True).drop(columns=["_dn"], errors="ignore")
    val_df = pd.concat(val_parts, ignore_index=True).drop(columns=["_dn"], errors="ignore")
    test_df = pd.concat(test_parts, ignore_index=True).drop(columns=["_dn"], errors="ignore")
    meta = {
        "split_mode": "per_unit",
        "units_kept": kept,
        "units_dropped_short_calendar": dropped,
        "min_days_per_unit": min_days,
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
    }
    print(
        f"按房源时间切分: 保留房源 {kept} / 丢弃(日历<{min_days}天) {dropped} | "
        f"行数 训练 {len(train_df)} 验证 {len(val_df)} 测试 {len(test_df)}"
    )
    return train_df, val_df, test_df, meta


def preprocess_daily(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    use_lags: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any], pd.DataFrame, List[str], pd.DataFrame]:
    print("\n" + "=" * 60)
    print("日级预处理（目标编码仅用训练段标签，无测试泄漏）")
    print("=" * 60)

    dist_counts = train_df.groupby("district").size()
    valid_districts = dist_counts[dist_counts >= 5].index.tolist()
    train_df = train_df[train_df["district"].isin(valid_districts)].copy()
    val_df = val_df[val_df["district"].isin(valid_districts)].copy()
    test_df = test_df[test_df["district"].isin(valid_districts)].copy()
    print(f"行政区过滤(训练内 n>=5): 训练 {len(train_df)} / 验证 {len(val_df)} / 测试 {len(test_df)}")

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
    val_df = val_df.merge(district_stats, on="district", how="left")
    test_df = test_df.merge(district_stats, on="district", how="left")

    for col, gv in [
        ("dist_mean", g_mean),
        ("dist_median", g_median),
        ("dist_std", g_std),
        ("dist_count", float(g_count)),
    ]:
        train_df[col] = train_df[col].fillna(gv)
        val_df[col] = val_df[col].fillna(gv)
        test_df[col] = test_df[col].fillna(gv)
    train_df["dist_std"] = train_df["dist_std"].fillna(0)
    val_df["dist_std"] = val_df["dist_std"].fillna(0)
    test_df["dist_std"] = test_df["dist_std"].fillna(0)

    min_ta = int(os.environ.get("TRAIN_MIN_TRADE_AREA_SAMPLES", "3"))
    min_ta = max(1, min_ta)
    ta_join_tr = train_df["trade_area"].fillna("").astype(str).str.strip()
    ta_agg = (
        train_df.assign(_ta_join=ta_join_tr)
        .groupby("_ta_join", sort=False)["price"]
        .agg(ta_mean="mean", ta_median="median", ta_std="std", ta_count="count")
        .reset_index()
        .rename(columns={"_ta_join": "join_key"})
    )
    ta_agg["ta_std"] = ta_agg["ta_std"].fillna(0.0)
    reliable_ta = ta_agg[ta_agg["ta_count"] >= min_ta].copy()

    def _merge_ta(d: pd.DataFrame) -> pd.DataFrame:
        x = d.copy()
        x["_ta_join"] = x["trade_area"].fillna("").astype(str).str.strip()
        x = x.merge(reliable_ta, how="left", left_on="_ta_join", right_on="join_key")
        x = x.drop(columns=["_ta_join", "join_key"], errors="ignore")
        for ta_c, dist_c in [
            ("ta_mean", "dist_mean"),
            ("ta_median", "dist_median"),
            ("ta_std", "dist_std"),
            ("ta_count", "dist_count"),
        ]:
            x[ta_c] = x[ta_c].fillna(x[dist_c])
        return x

    train_df = _merge_ta(train_df)
    val_df = _merge_ta(val_df)
    test_df = _merge_ta(test_df)
    trade_area_stats_export = reliable_ta.rename(columns={"join_key": "trade_area"})
    print(f"商圈目标编码: n>={min_ta} 的商圈数 {len(trade_area_stats_export)}")

    district_map = _category_map(train_df["district"])
    trade_area_map = _category_map(train_df["trade_area"])
    house_type_map = _category_map(train_df["house_type"])

    for dframe in (train_df, val_df, test_df):
        dframe["district_encoded"] = _apply_category_map(dframe["district"], district_map)
        dframe["trade_area_encoded"] = _apply_category_map(dframe["trade_area"], trade_area_map)
        dframe["house_type_encoded"] = _apply_category_map(dframe["house_type"], house_type_map)

    rmed = float(train_df["rating"].median())
    for dframe in (train_df, val_df, test_df):
        dframe["rating"] = dframe["rating"].fillna(rmed)
        dframe["favorite_count"] = dframe["favorite_count"].fillna(0)
        dframe["capacity"] = dframe["capacity"].fillna(dframe["bedroom_count"] * 2)
        dframe["bed_count"] = dframe["bed_count"].fillna(dframe["bedroom_count"])

    for dframe in (train_df, val_df, test_df):
        dframe["area_per_bedroom"] = dframe["area"] / (dframe["bedroom_count"] + 1)
        dframe["heat_score"] = dframe["favorite_count"] * dframe["rating"] / 10.0
        dframe["is_large"] = ((dframe["bedroom_count"] >= 4) | (dframe["area"] >= 150)).astype(int)
        dframe["is_budget"] = [
            compute_is_budget_structural(a, b)
            for a, b in zip(dframe["area"], dframe["bedroom_count"])
        ]

    if use_lags:
        lag_med_train = (
            float(train_df["lag1_price"].median())
            if train_df["lag1_price"].notna().any()
            else float(train_df["price"].median())
        )
        roll_med = (
            float(train_df["roll7_prior_mean"].median())
            if train_df["roll7_prior_mean"].notna().any()
            else lag_med_train
        )
        for dframe in (train_df, val_df, test_df):
            dframe["lag1_price"] = dframe["lag1_price"].fillna(lag_med_train)
            dframe["roll7_prior_mean"] = dframe["roll7_prior_mean"].fillna(roll_med)

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
        "can_booking",
    ]
    loc_features = [
        "district_encoded",
        "trade_area_encoded",
        "dist_mean",
        "dist_median",
        "dist_std",
        "dist_count",
        "ta_mean",
        "ta_median",
        "ta_std",
        "ta_count",
        "house_type_encoded",
    ]
    facility_cols = list(dict.fromkeys(FACILITY_KEYWORDS.values()))
    interaction = ["area_per_bedroom", "heat_score", "facility_count"]
    lag_part = LAG_FEATURE_COLUMNS if use_lags else []
    feature_cols = (
        num_features
        + loc_features
        + facility_cols
        + interaction
        + DATE_FEATURE_COLUMNS
        + lag_part
    )
    feature_cols = [c for c in feature_cols if c in train_df.columns]

    for dframe in (train_df, val_df, test_df):
        for col in feature_cols:
            if col in dframe.columns and dframe[col].isna().any():
                dframe[col] = dframe[col].fillna(0)

    encoders = {
        "district": {k: int(v) for k, v in district_map.items()},
        "trade_area": {k: int(v) for k, v in trade_area_map.items()},
        "house_type": {k: int(v) for k, v in house_type_map.items()},
    }
    lag_note = f" + 滞后 {len(LAG_FEATURE_COLUMNS)}" if use_lags else ""
    print(f"特征数: {len(feature_cols)}（含日期 {len(DATE_FEATURE_COLUMNS)}{lag_note}）")
    return train_df, val_df, test_df, encoders, district_stats, feature_cols, trade_area_stats_export


def train_xgb_daily(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[Any, Dict[str, float], Dict[str, float], Dict[str, float], pd.DataFrame]:
    print("\n" + "=" * 60)
    print("XGBoost 日级训练（验证集=时间切分出的中间段，早停）")
    print("=" * 60)

    X_fit = train_df[feature_cols]
    X_val = val_df[feature_cols]
    y_fit_log = train_df["price_log"]
    y_val_log = val_df["price_log"]
    w_fit = train_df["price"].apply(_price_row_weight)

    native = _build_booster_params_from_env()
    num_round = int(os.environ.get("TRAIN_XGB_NUM_BOOST_ROUND", "1200"))
    es_rounds = int(os.environ.get("TRAIN_XGB_EARLY_STOPPING_ROUNDS", "80"))

    booster = _fit_xgb_booster_cold_val(
        X_fit, X_val, y_fit_log, y_val_log, w_fit, feature_cols, native, num_round, es_rounds
    )
    bi = getattr(booster, "best_iteration", None)
    try:
        n_trees = int(booster.num_boosted_rounds())
    except Exception:
        n_trees = -1
    print(f"早停: best_iteration={bi} | 树棵数={n_trees} / 上限 {num_round}")

    fd, tmp_path = tempfile.mkstemp(suffix=".ubj")
    os.close(fd)
    try:
        booster.save_model(tmp_path)
        model = xgb.XGBRegressor()
        model.load_model(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    def _pred(df: pd.DataFrame) -> np.ndarray:
        return np.expm1(model.predict(df[feature_cols].to_numpy(dtype=np.float32)))

    y_train_raw = train_df["price"].values
    y_val_raw = val_df["price"].values
    y_test_raw = test_df["price"].values
    train_m = _metrics_dict(y_train_raw, _pred(train_df))
    val_m = _metrics_dict(y_val_raw, _pred(val_df))
    test_m = _metrics_dict(y_test_raw, _pred(test_df))

    print("\n训练集:")
    print(f"  MAE:  {train_m['mae']:.2f}  RMSE: {train_m['rmse']:.2f}  R²: {train_m['r2']:.4f}")
    print("\n验证集(时间):")
    print(f"  MAE:  {val_m['mae']:.2f}  RMSE: {val_m['rmse']:.2f}  R²: {val_m['r2']:.4f}")
    print("\n测试集(时间):")
    print(f"  MAE:  {test_m['mae']:.2f}  RMSE: {test_m['rmse']:.2f}  R²: {test_m['r2']:.4f}")

    imp = pd.DataFrame({"feature": feature_cols, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    )
    print("\n特征重要性 Top 12:")
    print(imp.head(12).to_string(index=False))

    return model, train_m, val_m, test_m, imp


def _booster_to_xgb_regressor(booster: Any) -> Any:
    fd, tmp_path = tempfile.mkstemp(suffix=".ubj")
    os.close(fd)
    try:
        booster.save_model(tmp_path)
        model = xgb.XGBRegressor()
        model.load_model(tmp_path)
        return model
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def train_daily_quantile_models(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: List[str],
) -> Dict[str, Any]:
    """在 log1p(价格) 上训练 Q20/Q50/Q80 分位数 XGBoost，用于区间预测。"""
    print("\n" + "=" * 60)
    print("分位数模型（reg:quantileerror，验证集早停）")
    print("=" * 60)
    X_fit = train_df[feature_cols]
    X_val = val_df[feature_cols]
    y_fit_log = train_df["price_log"]
    y_val_log = val_df["price_log"]
    w_fit = train_df["price"].apply(_price_row_weight)
    native = _build_booster_params_from_env()
    native.pop("eval_metric", None)
    num_round = int(os.environ.get("TRAIN_XGB_NUM_BOOST_ROUND", "1200"))
    es_rounds = int(os.environ.get("TRAIN_XGB_EARLY_STOPPING_ROUNDS", "80"))
    out: Dict[str, Any] = {}
    for alpha, tag in [(0.2, "q020"), (0.5, "q050"), (0.8, "q080")]:
        p = dict(native)
        p["objective"] = "reg:quantileerror"
        p["quantile_alpha"] = float(alpha)
        booster = _fit_xgb_booster_cold_val(
            X_fit, X_val, y_fit_log, y_val_log, w_fit, feature_cols, p, num_round, es_rounds
        )
        out[tag] = _booster_to_xgb_regressor(booster)
        print(f"  已拟合 {tag} (alpha={alpha})")
    return out


def save_daily_artifacts(
    model: Any,
    feature_cols: List[str],
    train_m: Dict[str, float],
    val_m: Dict[str, float],
    test_m: Dict[str, float],
    encoders: Dict[str, Any],
    district_stats: pd.DataFrame,
    trade_area_stats: pd.DataFrame,
    split_meta: Dict[str, Any],
    n_train: int,
    n_val: int,
    n_test: int,
    use_lags: bool,
) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    joblib.dump(model, DAILY_MODEL_PATH)
    with open(DAILY_FEATURE_JSON, "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)

    for name, enc in encoders.items():
        joblib.dump(enc, OUTPUT_DIR / f"{name}_encoder_daily.pkl")

    district_stats.to_json(
        OUTPUT_DIR / "district_stats_daily.json", orient="records", force_ascii=False, indent=2
    )
    p_ta = OUTPUT_DIR / "trade_area_target_stats_daily.json"
    if len(trade_area_stats) > 0:
        trade_area_stats.to_json(p_ta, orient="records", force_ascii=False, indent=2)
    else:
        with open(p_ta, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)

    split_label = split_meta.get("split_mode", "global")
    if split_label == "per_unit":
        split_str = "per_unit_calendar_70_15_15"
    else:
        split_str = "global_date_70_15_15"
    payload = {
        "model_type": "XGBoost daily (log1p); static + date -> daily price",
        "split": split_str,
        "split_meta": split_meta,
        "train_metrics": train_m,
        "val_metrics": val_m,
        "test_metrics": test_m,
        "n_train": n_train,
        "n_val": n_val,
        "n_test": n_test,
        "feature_count": len(feature_cols),
        "date_features": DATE_FEATURE_COLUMNS,
        "lag_features_used": use_lags,
        "optional_lag_columns": LAG_FEATURE_COLUMNS if use_lags else [],
        "chinesecalendar_note": "建议安装 chinesecalendar：节假日、节前/节后距离、调休",
    }
    with open(DAILY_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 60)
    print("已保存日级模型与元数据（未覆盖 xgboost_price_model_latest.pkl）")
    print("=" * 60)
    print(f"  {DAILY_MODEL_PATH}")
    print(f"  {DAILY_FEATURE_JSON}")
    print(f"  {DAILY_METRICS_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description="日级价格 XGBoost（MySQL + 时间切分）")
    parser.add_argument(
        "--with-lags",
        action="store_true",
        help="加入昨日价、近7日均价（对比用；默认关闭，与无历史日价推理一致）",
    )
    parser.add_argument(
        "--split-mode",
        choices=("global", "per_unit"),
        default="global",
        help="时间切分：global=全局日期轴；per_unit=每套房源各自 70/15/15",
    )
    parser.add_argument(
        "--per-unit-min-days",
        type=int,
        default=10,
        help="per_unit 模式下房源至少拥有的日历天数，不足则整套丢弃（默认 10）",
    )
    parser.add_argument(
        "--skip-quantiles",
        action="store_true",
        help="跳过分位数模型（仅保存点预测模型；API 区间退化为 MAE 带或 ±15%）",
    )
    args = parser.parse_args()

    df = load_daily_mysql()
    df = add_unit_calendar_offset(df, "unit_id", "calendar_date")
    df = add_daily_date_features(df, "calendar_date")
    df = add_holiday_proximity_features(df, "calendar_date", max_span=60)
    if args.with_lags:
        df = add_prior_price_lags(df, "unit_id", "calendar_date", "price")
    else:
        df["lag1_price"] = np.nan
        df["roll7_prior_mean"] = np.nan

    if args.split_mode == "global":
        train_df, val_df, test_df, split_meta = time_split_dates(df)
        split_meta["split_mode"] = "global"
    else:
        train_df, val_df, test_df, split_meta = time_split_per_unit(
            df, "calendar_date", min_days=max(5, args.per_unit_min_days)
        )

    train_df["price_log"] = np.log1p(train_df["price"])
    val_df["price_log"] = np.log1p(val_df["price"])
    test_df["price_log"] = np.log1p(test_df["price"])

    (
        train_df,
        val_df,
        test_df,
        encoders,
        district_stats,
        feature_cols,
        trade_area_stats_export,
    ) = preprocess_daily(train_df, val_df, test_df, use_lags=args.with_lags)

    if len(train_df) < 200 or len(test_df) < 20:
        print("错误: 日级训练/测试样本过少，请检查日历覆盖或放宽过滤。")
        sys.exit(1)

    model, train_m, val_m, test_m, imp = train_xgb_daily(train_df, val_df, test_df, feature_cols)

    quantile_models: Dict[str, Any] = {}
    if not args.skip_quantiles:
        quantile_models = train_daily_quantile_models(train_df, val_df, feature_cols)
        for tag, m in quantile_models.items():
            joblib.dump(m, OUTPUT_DIR / f"xgboost_price_daily_{tag}.pkl")
        print(f"已保存分位数模型: {', '.join(quantile_models.keys())}")
    else:
        for tag in ("q020", "q050", "q080"):
            stale = OUTPUT_DIR / f"xgboost_price_daily_{tag}.pkl"
            if stale.exists():
                try:
                    stale.unlink()
                    print(f"已删除旧分位数模型（与 --skip-quantiles 一致）: {stale.name}")
                except OSError:
                    pass

    forecast_meta = {
        "val_mae_price": float(val_m["mae"]),
        "error_band_multiplier": 1.5,
        "quantile_alphas": [0.2, 0.5, 0.8] if quantile_models else [],
        "trained_with_lags": bool(args.with_lags),
    }
    with open(OUTPUT_DIR / "daily_forecast_meta.json", "w", encoding="utf-8") as f:
        json.dump(forecast_meta, f, ensure_ascii=False, indent=2)
    print(f"已写入 {OUTPUT_DIR / 'daily_forecast_meta.json'}（验证 MAE 供误差带兜底）")

    if args.with_lags:
        lag_def = {}
        for c in LAG_FEATURE_COLUMNS:
            if c in train_df.columns:
                med = train_df[c].median()
                lag_def[c] = float(med) if pd.notna(med) else 0.0
        with open(OUTPUT_DIR / "daily_lag_inference_defaults.json", "w", encoding="utf-8") as f:
            json.dump(lag_def, f, ensure_ascii=False, indent=2)

    save_daily_artifacts(
        model,
        feature_cols,
        train_m,
        val_m,
        test_m,
        encoders,
        district_stats,
        trade_area_stats_export,
        split_meta,
        len(train_df),
        len(val_df),
        len(test_df),
        use_lags=args.with_lags,
    )

    print("\n测试集 R²: {:.4f} | MAE: {:.2f} 元".format(test_m["r2"], test_m["mae"]))


if __name__ == "__main__":
    main()
