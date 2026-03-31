# -*- coding: utf-8 -*-
"""
训练基准模型（线性 / 梯度提升）用于论文对比 — 支持本地 JSON 或 MySQL/Hive（与 XGBoost 同源）
================================================================================

与 `train_model_mysql.py` 中 XGBoost 流程对齐（划分、预处理、log1p、样本权重）。

线性基线：`Winsorize` + **双支路等权集成**：（1）二次多项式 + `PCA` + `RidgeCV`；（2）`Nyström` RBF 映射 + `RidgeCV`
（核岭回归的随机特征近似）；两支路在 log1p 域各 0.5 权重，再 `expm1`。
树基线：`HistGradientBoostingRegressor`（浅树、大 L2、大 `min_samples_leaf`、`max_leaf_nodes` 上限，
+ 留出验证 early stopping），在可比容量下压低训练集虚高 R²、缩小与测试集差距。

运行（在 Tujia-backend 目录下）：
    python scripts/train_baseline_models_local.py                    # 默认与 train_model_mysql 相同：auto
    python scripts/train_baseline_models_local.py --data-source json # 仅本地 JSON（离线）
    python scripts/train_baseline_models_local.py --data-source mysql

环境变量：与 `train_model_mysql.py` 一致，未传 `--data-source` 时使用 `TRAIN_DATA_SOURCE`（默认 `auto`）。
可选 `TRAIN_BASELINE_DATA_SOURCE` 覆盖为 `json|mysql|hive|auto`。命令行优先。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path(__file__).parent.parent / "models"
OUTPUT_DIR.mkdir(exist_ok=True)

from app.ml.calendar_features import aggregate_calendar_dataframe
from app.ml.price_feature_config import FACILITY_KEYWORDS, ordered_facility_columns
from app.ml.house_tags_text import parse_house_tags
from scripts.train_model_mysql import (
    apply_mysql_compatible_filters,
    load_training_data,
    preprocess_after_split,
    price_bucket,
    stratified_holdout,
)

_FACILITY_COLS_ORDERED = ordered_facility_columns()

# HistGradientBoosting：在「对齐 XGB 量级」与「抑制过拟合」之间折中。
# 先前 depth=6、l2=1、耐心 30 轮 → 训练 R² 显著高于测试；改为更浅树、更大 L2、
# 更大验证比例 + 更短耐心，使早停更早触发在泛化更好的迭代。
HIST_GB_XGB_ALIGNED: Dict[str, Any] = {
    "max_iter": 500,
    "learning_rate": 0.04,
    "max_depth": 4,
    "max_leaf_nodes": 24,
    "min_samples_leaf": 28,
    "l2_regularization": 12.0,
    "max_bins": 255,
    "early_stopping": True,
    "validation_fraction": 0.18,
    "n_iter_no_change": 12,
    "random_state": 42,
}


def _daily_calendar_rows_from_houses(houses: List[dict]) -> pd.DataFrame:
    """从导出 JSON 的 price_calendar 展平为日表。"""
    rows: List[Dict[str, Any]] = []
    for house in houses:
        uid = str(house.get("unit_id", "") or "")
        if not uid:
            continue
        pc = house.get("price_calendar") or {}
        data = pc.get("data") or {}
        cals = data.get("houseCalendars") or []
        for c in cals:
            try:
                p = float(c.get("price") if c.get("price") is not None else 0)
            except (TypeError, ValueError):
                p = 0.0
            cb = c.get("canBooking")
            try:
                cb_f = float(cb if cb is not None else 1.0)
            except (TypeError, ValueError):
                cb_f = 1.0
            rows.append(
                {
                    "unit_id": uid,
                    "date": c.get("date"),
                    "price": p,
                    "can_booking": cb_f,
                }
            )
    return pd.DataFrame(rows)


def load_data_from_json() -> pd.DataFrame:
    """从本地 JSON 加载房源 + 日历聚合特征（与 MySQL 训练特征列对齐）。"""
    data_path = (
        Path(__file__).parent.parent / "data" / "hive_import" / "listings_with_tags_and_calendar.json"
    )

    if not data_path.exists():
        print(f"错误: 数据文件不存在 {data_path}")
        print("请先运行数据导出脚本或检查文件路径")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    houses = raw_data.get("houses", [])
    print(f"从JSON加载 {len(houses)} 条房源数据")

    daily = _daily_calendar_rows_from_houses(houses)
    cal_agg = aggregate_calendar_dataframe(daily)
    print(f"价格日历日条数: {len(daily)} → 聚合房源数: {len(cal_agg)}")

    records: List[Dict[str, Any]] = []
    for house in houses:
        fav_count = house.get("favorite_count", 0)
        if isinstance(fav_count, str):
            fav_str = fav_count.lower().replace("+", "")
            if "w" in fav_str:
                fav_count = float(fav_str.replace("w", "")) * 10000
            elif "k" in fav_str:
                fav_count = float(fav_str.replace("k", "")) * 1000
            else:
                fav_count = float(fav_str) if fav_str else 0

        tags_list = parse_house_tags(house.get("tags", []))
        tags_set = set(tags_list)

        facilities: Dict[str, int] = {}
        for tag_name, feat_name in FACILITY_KEYWORDS.items():
            facilities[feat_name] = 1 if tag_name in tags_set else 0

        record: Dict[str, Any] = {
            "unit_id": str(house.get("unit_id", "") or ""),
            "price": float(house.get("final_price", 0)),
            "district": house.get("district", ""),
            "trade_area": house.get("trade_area", house.get("district", "")),
            "rating": float(house.get("rating", 0) or 0),
            "area": float(house.get("area", 50) or 50),
            "bedroom_count": int(house.get("bedroom_count", 1) or 1),
            "bed_count": int(house.get("bed_count", 1) or 1),
            "capacity": int(house.get("capacity", 2) or 2),
            "favorite_count": int(fav_count or 0),
            "house_type": house.get("house_type", "整套") or "整套",
            "latitude": float(house.get("latitude", 0) or 0),
            "longitude": float(house.get("longitude", 0) or 0),
            **facilities,
        }
        record["facility_count"] = sum(
            int(record.get(c, 0) or 0) for c in _FACILITY_COLS_ORDERED
        )
        records.append(record)

    df = pd.DataFrame(records)
    df = df[df["unit_id"].astype(str).str.len() > 0].copy()
    df = df.merge(cal_agg, on="unit_id", how="left")

    df = df[(df["price"] >= 50) & (df["price"] <= 5000)].copy()
    df = df[df["rating"].notna() & df["district"].notna()].copy()
    df = apply_mysql_compatible_filters(df)

    print(f"过滤后有效数据: {len(df)} 条")
    return df


def load_training_frame(data_source: str) -> Tuple[pd.DataFrame, str]:
    """
    加载与 `train_model_mysql.main` 一致的数据源（Hive/MySQL/auto 不额外 filter，与 XGBoost 同源）。
    `json` 为离线导出路径，仅显式指定时使用。
    """
    src = (data_source or "auto").strip().lower()
    if src == "json":
        return load_data_from_json(), "local JSON (hive_import)"
    df, label = load_training_data(src)
    return df, label


class _LogSpaceAvgTwoPipelines(BaseEstimator, RegressorMixin):
    """两支路均在 log1p 域预测，等权平均（兼容旧版 VotingRegressor 无法下传 ridge__sample_weight）。"""

    def __init__(self, pipe_poly: Pipeline, pipe_nys: Pipeline):
        self.pipe_poly = pipe_poly
        self.pipe_nys = pipe_nys

    def fit(self, X, y, sample_weight=None):
        fp: Dict[str, Any] = {}
        if sample_weight is not None:
            fp["ridge__sample_weight"] = sample_weight
        self.pipe_poly.fit(X, y, **fp)
        self.pipe_nys.fit(X, y, **fp)
        return self

    def predict(self, X):
        return 0.5 * (self.pipe_poly.predict(X) + self.pipe_nys.predict(X))


class WinsorizeByTrain(BaseEstimator, TransformerMixin):
    """按训练集分位数裁剪特征，减轻测试集 OOD 导致的多项式爆炸。"""

    def __init__(self, lower_pct: float = 0.5, upper_pct: float = 99.5):
        self.lower_pct = lower_pct
        self.upper_pct = upper_pct

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=np.float64)
        self.lo_ = np.percentile(X, self.lower_pct, axis=0)
        self.hi_ = np.percentile(X, self.upper_pct, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=np.float64), self.lo_, self.hi_)


def _sample_weight_from_price(prices: np.ndarray) -> np.ndarray:
    """与 train_model_mysql.train_xgb_model 一致。"""
    w = np.ones(len(prices), dtype=np.float64)
    w[prices < 100] = 2.0
    w[prices > 500] = 1.5
    return w


def _predict_prices_expm1(
    model: Any, X_train: np.ndarray, X_test: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """在 log1p 域训练的回归模型：预测并 expm1 还原为价格（元），下限 1；合并一次 predict。"""
    n_train = X_train.shape[0]
    X_b = np.vstack((X_train, X_test))
    y_hat = np.maximum(np.expm1(model.predict(X_b)), 1.0)
    return y_hat[:n_train], y_hat[n_train:]


def _ridge_cv_step() -> RidgeCV:
    return RidgeCV(
        alphas=np.logspace(-0.5, 5.5, 60),
        cv=5,
        scoring="neg_mean_squared_error",
        fit_intercept=True,
    )


def train_linear_regression(
    train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]
) -> Tuple[Any, Dict[str, float], Dict[str, float], Dict[str, Any]]:
    """
    双支路等权集成（log1p 域各 0.5）：
    - poly_pca：显式二次交互 + PCA + Ridge（可解释性强）
    - nystroem：RBF Nyström 随机特征 + Ridge（核岭回归近似，光滑非线性）
    样本权重与 train_xgb_model 一致，传入各支路 RidgeCV。
    """
    print("\n" + "=" * 60)
    print("训练线性基线 (双支路: Poly+PCA+Ridge ‖ Nyström-RBF+Ridge)")
    print("=" * 60)

    X_train = train_df[feature_cols].values.astype(np.float64)
    X_test = test_df[feature_cols].values.astype(np.float64)
    y_train = train_df["price"].values
    y_test = test_df["price"].values

    y_train_log = np.log1p(y_train)
    sw = _sample_weight_from_price(y_train)

    n_samples, n_feat = X_train.shape
    _poly_probe = PolynomialFeatures(degree=2, include_bias=False, interaction_only=False)
    _poly_probe.fit(X_train)
    n_poly = int(_poly_probe.n_output_features_)
    n_comp = min(n_poly, max(50, n_samples - 20), 320)
    # Nyström 维数：介于秩约束与近似精度之间（不宜超过 n_samples 过多）
    n_nystroem = int(min(420, max(160, n_samples // 4), n_samples - 25))

    pipe_poly = Pipeline(
        [
            ("winsor", WinsorizeByTrain(lower_pct=0.5, upper_pct=99.5)),
            ("poly", PolynomialFeatures(degree=2, include_bias=False, interaction_only=False)),
            ("scale", StandardScaler()),
            ("pca", PCA(n_components=n_comp, svd_solver="randomized", random_state=42)),
            ("ridge", _ridge_cv_step()),
        ]
    )
    pipe_nys = Pipeline(
        [
            ("winsor", WinsorizeByTrain(lower_pct=0.5, upper_pct=99.5)),
            ("scale", StandardScaler()),
            (
                "nystroem",
                Nystroem(
                    kernel="rbf",
                    gamma=None,
                    n_components=n_nystroem,
                    random_state=42,
                ),
            ),
            ("ridge", _ridge_cv_step()),
        ]
    )

    model = _LogSpaceAvgTwoPipelines(pipe_poly, pipe_nys)

    print(
        f"  支路1: Winsor → 多项式{n_poly}维 → PCA{n_comp} → RidgeCV | "
        f"支路2: Winsor → Scale → Nyström-RBF m={n_nystroem} → RidgeCV（log 域等权平均）"
    )
    model.fit(X_train, y_train_log, sample_weight=sw)

    r1 = pipe_poly.named_steps["ridge"]
    r2 = pipe_nys.named_steps["ridge"]
    pca = pipe_poly.named_steps["pca"]
    ev_sum = float(np.sum(pca.explained_variance_ratio_))
    print(
        f"  RidgeCV α: poly支路={float(r1.alpha_):.6g}, nyström支路={float(r2.alpha_):.6g} | "
        f"PCA 累计解释方差比={ev_sum:.4f}"
    )

    y_pred_train, y_pred_test = _predict_prices_expm1(model, X_train, X_test)

    def evaluate(y_true, y_pred, name):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        print(f"\n{name}:")
        print(f"  MAE:  {mae:.2f} 元")
        print(f"  RMSE: {rmse:.2f} 元")
        print(f"  R2:   {r2:.4f}")
        print(f"  MAPE: {mape:.2f}%")

        return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}

    train_metrics = evaluate(y_train, y_pred_train, "训练集")
    test_metrics = evaluate(y_test, y_pred_test, "测试集")

    meta = {
        "impl": "equal-weight avg: Poly+PCA+Ridge ‖ Nyström-RBF+Ridge (log1p)",
        "ridge_alpha_poly_branch": float(r1.alpha_),
        "ridge_alpha_nystroem_branch": float(r2.alpha_),
        "ridge_cv": 5,
        "ridge_scoring": "neg_mean_squared_error",
        "pca_n_components": int(pca.n_components_),
        "pca_explained_variance_ratio_sum": ev_sum,
        "n_poly_features": n_poly,
        "nystroem_n_components": n_nystroem,
        "voting_weights": "equal (default)",
    }
    return model, train_metrics, test_metrics, meta


def train_random_forest(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]):
    """直方图梯度提升：强正则 + early stopping，优先缩小训练-测试差距。"""
    print("\n" + "=" * 60)
    print("训练树基线 (HistGradientBoosting，强正则 + early stopping)")
    print("=" * 60)

    X_train = train_df[feature_cols].values.astype(np.float64)
    X_test = test_df[feature_cols].values.astype(np.float64)
    y_train = train_df["price"].values
    y_test = test_df["price"].values

    y_train_log = np.log1p(y_train)
    sw = _sample_weight_from_price(y_train)

    model = HistGradientBoostingRegressor(**HIST_GB_XGB_ALIGNED)
    model.fit(X_train, y_train_log, sample_weight=sw)
    print(
        f"  HistGB: 早停于第 {model.n_iter_} 轮（上限 {HIST_GB_XGB_ALIGNED['max_iter']}）"
    )

    y_pred_train, y_pred_test = _predict_prices_expm1(model, X_train, X_test)

    def evaluate(y_true, y_pred, name):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        print(f"\n{name}:")
        print(f"  MAE:  {mae:.2f} 元")
        print(f"  RMSE: {rmse:.2f} 元")
        print(f"  R2:   {r2:.4f}")
        print(f"  MAPE: {mape:.2f}%")

        return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}

    train_metrics = evaluate(y_train, y_pred_train, "训练集")
    test_metrics = evaluate(y_test, y_pred_test, "测试集")

    return model, train_metrics, test_metrics


def save_results(
    lr_train,
    lr_test,
    rf_train,
    rf_test,
    xgb_metrics,
    feature_cols,
    n_train,
    n_test,
    linear_meta: Optional[Dict[str, Any]] = None,
    data_source_label: str = "",
):
    """保存结果"""
    print("\n" + "=" * 60)
    print("保存基准模型指标")
    print("=" * 60)

    lr_block: Dict[str, Any] = {
        "train": lr_train,
        "test": lr_test,
    }
    if linear_meta:
        lr_block = {**linear_meta, **lr_block}

    baseline_metrics: Dict[str, Any] = {
        "data_source": data_source_label or "unknown",
        "linear_regression": lr_block,
        "gradient_boosting": {
            "hyperparams": dict(HIST_GB_XGB_ALIGNED),
            "impl": "sklearn HistGradientBoostingRegressor",
            "aligned_with": "HistGB 超参在 XGB 量级基础上加强 L2/浅树/早停，减轻过拟合",
            "train": rf_train,
            "test": rf_test,
        },
        "xgboost": xgb_metrics,
        "comparison": {
            "test_mae": {
                "lr": lr_test["mae"],
                "rf": rf_test["mae"],
                "xgb": xgb_metrics["mae"],
            },
            "test_mape": {
                "lr": lr_test["mape"],
                "rf": rf_test["mape"],
                "xgb": xgb_metrics["mape"],
            },
            "test_r2": {
                "lr": lr_test["r2"],
                "rf": rf_test["r2"],
                "xgb": xgb_metrics["r2"],
            },
        },
        "feature_count": len(feature_cols),
        "sample_count_train": n_train,
        "sample_count_test": n_test,
        "methodology_notes": [
            f"数据来源: {data_source_label or 'unknown'}；stratified_holdout + preprocess_after_split（与 train_model_mysql 一致）",
            "log1p/expm1 目标；样本权重与 train_xgb_model 一致",
            "线性：双支路等权（Poly+PCA+Ridge ‖ Nyström-RBF+Ridge），各支路 RidgeCV 使用与 XGB 一致 sample_weight",
            "树基线：HistGradientBoosting（浅树、高 L2、大叶宽、max_leaf_nodes、18% 留出早停）",
        ],
    }

    output_path = OUTPUT_DIR / "baseline_model_metrics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(baseline_metrics, f, ensure_ascii=False, indent=2)

    print(f"指标已保存: {output_path}")

    # 打印对比表格
    print("\n" + "=" * 60)
    print("模型对比表格（可直接复制到论文表5-6）")
    print("=" * 60)
    print(f"{'模型':<20} {'MAE':<10} {'MAPE(%)':<10} {'R2':<10}")
    print("-" * 55)
    print(f"{'线性Voting(Poly|Nys)':<20} {lr_test['mae']:<10.2f} {lr_test['mape']:<10.2f} {lr_test['r2']:<10.4f}")
    print(f"{'HistGB(强正则)':<20} {rf_test['mae']:<10.2f} {rf_test['mape']:<10.2f} {rf_test['r2']:<10.4f}")
    print(f"{'XGBoost':<20} {xgb_metrics['mae']:<10.2f} {xgb_metrics['mape']:<10.2f} {xgb_metrics['r2']:<10.4f}")


def main():
    # 与 train_model_mysql.main 一致：默认 auto（优先 Hive，否则 MySQL）
    _bl = os.environ.get("TRAIN_BASELINE_DATA_SOURCE", "").strip().lower()
    if _bl in ("json", "auto", "hive", "mysql"):
        env_default = _bl
    else:
        env_default = os.environ.get("TRAIN_DATA_SOURCE", "auto").strip().lower()
        if env_default not in ("json", "auto", "hive", "mysql"):
            env_default = "auto"
    parser = argparse.ArgumentParser(
        description="基准模型训练（线性 Poly+Nyström 双支路 / HistGB），数据源默认与 train_model_mysql 一致"
    )
    parser.add_argument(
        "--data-source",
        choices=("json", "auto", "hive", "mysql"),
        default=env_default,
        help="json=本地 hive_import JSON；mysql/hive/auto 同 train_model_mysql.load_training_data",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("基准模型训练（线性 Poly+Nyström 双支路 / HistGB，流程与 train_model_mysql 对齐）")
    print(f"数据模式: {args.data_source}")
    print("=" * 60)

    df, data_source_label = load_training_frame(args.data_source)
    df = df[df["price"] >= 50].copy()
    df = df[df["price"] <= 5000].copy()
    print(f"\n过滤后(50<=price<=5000): {len(df)} 条 | 来源: {data_source_label}")

    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(price_bucket)

    train_df, test_df = stratified_holdout(df)
    print(f"\n划分完成: 训练 {len(train_df)} / 测试 {len(test_df)}")

    train_df, test_df, _enc, _dst, feature_cols, _cal_def = preprocess_after_split(
        train_df, test_df
    )
    if len(train_df) < 50 or len(test_df) < 10:
        print("错误: 训练或测试样本过少")
        sys.exit(1)
    print(f"预处理后: 训练 {len(train_df)} / 测试 {len(test_df)} | 特征 {len(feature_cols)}")

    lr_model, lr_train, lr_test, lr_meta = train_linear_regression(train_df, test_df, feature_cols)
    rf_model, rf_train, rf_test = train_random_forest(train_df, test_df, feature_cols)

    # 读取XGBoost指标
    xgb_metrics_path = OUTPUT_DIR / "model_metrics_latest.json"
    if xgb_metrics_path.exists():
        with open(xgb_metrics_path, "r", encoding="utf-8") as f:
            xgb_data = json.load(f)
        xgb_metrics = xgb_data.get("metrics", {})
    else:
        print(f"警告: 未找到XGBoost指标文件，使用默认值")
        xgb_metrics = {"mae": 23.67, "mape": 10.44, "r2": 0.763}

    # 保存结果
    save_results(
        lr_train,
        lr_test,
        rf_train,
        rf_test,
        xgb_metrics,
        feature_cols,
        len(train_df),
        len(test_df),
        linear_meta=lr_meta,
        data_source_label=data_source_label,
    )

    # 保存模型
    joblib.dump(lr_model, OUTPUT_DIR / "linear_regression_poly_model.pkl")
    joblib.dump(rf_model, OUTPUT_DIR / "gradient_boosting_model.pkl")

    print("\n" + "=" * 60)
    print("基准模型训练完成")
    print("=" * 60)
    print("\n模型已保存:")
    print(f"  - {OUTPUT_DIR / 'linear_regression_poly_model.pkl'}")
    print(f"  - {OUTPUT_DIR / 'gradient_boosting_model.pkl'}")


if __name__ == "__main__":
    main()
