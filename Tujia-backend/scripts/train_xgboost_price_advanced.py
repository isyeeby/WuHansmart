# -*- coding: utf-8 -*-
"""
进阶 XGBoost 民宿日价训练（独立脚本，不修改其它模块）
====================================================

在 `train_model_mysql.py` 同源数据与 **preprocess_after_split**（无标签泄漏、日历段表、
设施稀疏剔除等）之上，额外做：

1. **结构/交互特征**（仅由已有列派生，不新增数据库列）
2. **分层 K 折 + 随机搜索**：优化目标为验证折上 **原价 MAE**（expm1 后），测试集从不参与选参
3. **可选目标函数**：`reg:squarederror` / `reg:absoluteerror`（XGBoost 2.x）
4. **多种子集成**：对同一组最优超参训练多棵随机种子模型，预测取 log 空间平均再 expm1，
   常见可进一步降低方差、压低 MAE

产物写入 ``models/*_advanced.*`` 与 ``price_model_advanced_bundle.joblib``，
**不会覆盖** ``xgboost_price_model_latest.pkl`` 及 ``*_latest.*``。

用法（在 Tujia-backend 目录）::

    python scripts/train_xgboost_price_advanced.py
    python scripts/train_xgboost_price_advanced.py --n-trials 80 --ensemble-size 7 --cv 5
    python scripts/train_xgboost_price_advanced.py --no-ensemble   # 仅单模型，便于对比速度
    python scripts/train_xgboost_price_advanced.py --aggressive-search --legacy-weights  # 旧版宽搜索+强样本权重

默认 **泛化优先**：浅树、强正则、温和样本权重、CV 指标用各折 MAE **中位数**；``--aggressive-search`` 恢复深树/宽搜索。

集成推理：加载 bundle 后对各子模型 ``predict`` 得到 log 预测，算术平均再 ``expm1``。
若上线需与线上一致，须在推理侧补齐 ``extra_engineered_features`` 中列名（见 metrics JSON）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import StratifiedKFold, train_test_split

warnings.filterwarnings("ignore")

_script_dir = Path(__file__).resolve().parent
_backend_root = _script_dir.parent
for _p in (_backend_root, _script_dir):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

MODELS_DIR = _backend_root / "models"
MODELS_DIR.mkdir(exist_ok=True)

import train_model_mysql as tmm  # noqa: E402
from app.ml.price_feature_config import FACILITY_KEYWORDS  # noqa: E402

_FACILITY_COL_NAMES = list(dict.fromkeys(FACILITY_KEYWORDS.values()))


class _TeeStdout:
    """写日志并尽量写控制台，避免部分环境下 stdout 已关闭导致中断。"""

    def __init__(self, log_path: Path) -> None:
        self._file = open(log_path, "w", encoding="utf-8")
        self._consoles: List[Any] = []
        for s in (sys.__stdout__, sys.stderr):
            if s is None:
                continue
            try:
                if hasattr(s, "writable") and not s.writable():
                    continue
                s.write("")
                s.flush()
                self._consoles.append(s)
            except (ValueError, OSError, AttributeError):
                continue

    def write(self, data: str) -> int:
        self._file.write(data)
        self._file.flush()
        for c in self._consoles:
            try:
                c.write(data)
                c.flush()
            except (ValueError, OSError, AttributeError):
                pass
        return len(data)

    def flush(self) -> None:
        self._file.flush()
        for c in self._consoles:
            try:
                c.flush()
            except (ValueError, OSError, AttributeError):
                pass

    @property
    def encoding(self) -> str:
        return "utf-8"


sys.stdout = _TeeStdout(MODELS_DIR / "train_advanced_last_run.log")
ARTIFACT_TAG = "advanced"
# 训练子集内用于早停/监控的验证比例（与旧版 train_model_mysql ES_VAL_FRACTION 对齐）
INNER_VAL_FRACTION = 0.15


def _sample_weights_array(prices: np.ndarray, *, legacy_weights: bool = False) -> np.ndarray:
    """默认温和权重减轻尾部主导、缓解过拟合；--legacy-weights 使用与线脚本相近的较强权重。"""
    w = np.ones(len(prices), dtype=np.float64)
    if legacy_weights:
        w[prices < 100] = 2.0
        w[prices > 500] = 1.5
    else:
        w[prices < 100] = 1.22
        w[prices > 500] = 1.1
    return w


def add_engineered_features(
    train_df: pd.DataFrame, test_df: pd.DataFrame, existing_cols: set[str]
) -> List[str]:
    """
    在预处理后的表上追加数值特征；返回**真正新增**的列名（若 preprocess 已含 log1p_area 等则不再重复进列表）。
    """
    for df in (train_df, test_df):
        br = df["bedroom_count"].clip(lower=1).astype(float)
        ar = df["area"].clip(lower=1.0).astype(float)
        if "log1p_area" not in df.columns:
            df["log1p_area"] = np.log1p(ar)
        la = pd.to_numeric(df["log1p_area"], errors="coerce").fillna(np.log1p(ar)).astype(float)
        df["rating_x_log_area"] = df["rating"].astype(float) * la
        df["guest_density"] = df["capacity"].astype(float) / ar
        df["sqrt_bedroom"] = np.sqrt(br)
        ds = df["dist_median"].astype(float) / (df["dist_std"].astype(float).abs() + 1.0)
        df["dist_stability"] = ds.clip(0.0, 80.0)
        df["area_x_house_type_enc"] = df["area"].astype(float) * df["house_type_encoded"].astype(float)
        if "cal_n_days" in df.columns:
            cnd = pd.to_numeric(df["cal_n_days"], errors="coerce").fillna(0.0).clip(0, 1e4)
            df["log1p_cal_n_days"] = np.log1p(cnd)
            df["has_calendar"] = (cnd > 0).astype(np.float64)
        else:
            df["log1p_cal_n_days"] = 0.0
            df["has_calendar"] = 0.0

    candidates = [
        "log1p_area",
        "rating_x_log_area",
        "guest_density",
        "sqrt_bedroom",
        "dist_stability",
        "area_x_house_type_enc",
        "log1p_cal_n_days",
        "has_calendar",
    ]
    return [c for c in candidates if c not in existing_cols]


def merge_feature_list(base_feature_cols: List[str], extra_cols: List[str]) -> List[str]:
    cal_ordered = [c for c in tmm.CALENDAR_FEATURE_NAMES if c in base_feature_cols]
    non_cal = [c for c in base_feature_cols if c not in tmm.CALENDAR_FEATURE_NAMES]
    merged = non_cal + [c for c in extra_cols if c not in non_cal]
    merged.extend([c for c in cal_ordered if c not in merged])
    return merged


def mae_original(y_log: np.ndarray, pred_log: np.ndarray) -> float:
    return float(mean_absolute_error(np.expm1(y_log), np.expm1(pred_log)))


def _fit_one(
    X_fit: pd.DataFrame,
    y_fit_log: np.ndarray,
    w_fit: np.ndarray,
    X_val: pd.DataFrame,
    y_val_log: np.ndarray,
    params: Dict[str, Any],
    early_stopping_rounds: int,
) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(**params)
    kw = dict(
        X=X_fit,
        y=y_fit_log,
        sample_weight=w_fit,
        eval_set=[(X_val, y_val_log)],
        verbose=False,
    )
    try:
        model.fit(**kw, early_stopping_rounds=early_stopping_rounds)
    except TypeError:
        model.fit(**kw)
    return model


def cv_mean_mae(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    params: Dict[str, Any],
    *,
    n_splits: int,
    early_stopping_rounds: int,
    random_state: int,
    legacy_weights: bool,
    cv_aggregate: str,
) -> float:
    X = train_df[feature_cols]
    y_log = train_df["price_log"].values
    strat = train_df["price_bucket"].values
    w_full = _sample_weights_array(train_df["price"].to_numpy(dtype=np.float64, copy=False), legacy_weights=legacy_weights)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_scores: List[float] = []

    for fold_idx, (fit_idx, val_idx) in enumerate(skf.split(X, strat)):
        strat_tr = train_df.iloc[fit_idx]["price_bucket"].values

        inner_tr, inner_val = train_test_split(
            np.arange(len(fit_idx)),
            test_size=INNER_VAL_FRACTION,
            random_state=random_state + fold_idx,
            stratify=strat_tr,
        )
        i_tr = fit_idx[inner_tr]
        i_es = fit_idx[inner_val]

        model = _fit_one(
            X.iloc[i_tr],
            y_log[i_tr],
            w_full[i_tr],
            X.iloc[i_es],
            y_log[i_es],
            params,
            early_stopping_rounds,
        )
        pred_val = model.predict(X.iloc[val_idx])
        fold_scores.append(mae_original(y_log[val_idx], pred_val))

    if cv_aggregate == "median":
        return float(np.median(fold_scores))
    return float(np.mean(fold_scores))


def random_params(rng: random.Random, *, aggressive: bool) -> Dict[str, Any]:
    """aggressive=False：浅树、高 min_child_weight、强正则、低子采样，利于测试集泛化。"""
    if aggressive:
        obj = rng.choice(["reg:squarederror", "reg:absoluteerror"])
        return {
            "objective": obj,
            "tree_method": "hist",
            "max_depth": int(rng.choice([4, 5, 6, 7, 8, 9])),
            "min_child_weight": float(rng.choice([1, 2, 3, 4, 5, 7, 10])),
            "max_delta_step": 0,
            "subsample": float(rng.uniform(0.62, 0.94)),
            "colsample_bytree": float(rng.uniform(0.62, 0.94)),
            "colsample_bylevel": float(rng.uniform(0.72, 1.0)),
            "learning_rate": float(10 ** rng.uniform(-2.15, -0.65)),
            "n_estimators": int(rng.choice([1600, 2000, 2400, 3000, 3600])),
            "reg_alpha": float(10 ** rng.uniform(-2.2, 0.4)),
            "reg_lambda": float(10 ** rng.uniform(-0.35, 0.95)),
            "gamma": float(rng.uniform(0.0, 0.45)),
            "random_state": 42,
            "n_jobs": -1,
        }
    obj = "reg:squarederror" if rng.random() < 0.8 else "reg:absoluteerror"
    return {
        "objective": obj,
        "tree_method": "hist",
        "max_depth": int(rng.choice([3, 4, 5])),
        "min_child_weight": float(rng.choice([8, 10, 12, 14, 16, 18])),
        "max_delta_step": 0,
        "subsample": float(rng.uniform(0.52, 0.76)),
        "colsample_bytree": float(rng.uniform(0.48, 0.68)),
        "colsample_bylevel": float(rng.uniform(0.55, 0.8)),
        "learning_rate": float(10 ** rng.uniform(-1.35, -0.92)),
        "n_estimators": int(rng.choice([700, 900, 1100, 1400, 1700])),
        "reg_alpha": float(10 ** rng.uniform(-0.75, 0.2)),
        "reg_lambda": float(10 ** rng.uniform(0.45, 1.08)),
        "gamma": float(rng.uniform(0.15, 0.4)),
        "random_state": 42,
        "n_jobs": -1,
    }


def default_baseline_like_params(*, aggressive: bool) -> Dict[str, Any]:
    if aggressive:
        return {
            "objective": "reg:squarederror",
            "tree_method": "hist",
            "max_depth": 6,
            "min_child_weight": 3,
            "subsample": 0.82,
            "colsample_bytree": 0.78,
            "colsample_bylevel": 0.9,
            "learning_rate": 0.04,
            "n_estimators": 2000,
            "reg_alpha": 0.1,
            "reg_lambda": 2.0,
            "gamma": 0.06,
            "max_delta_step": 0,
            "random_state": 42,
            "n_jobs": -1,
        }
    return {
        "objective": "reg:squarederror",
        "tree_method": "hist",
        "max_depth": 4,
        "min_child_weight": 10.0,
        "subsample": 0.68,
        "colsample_bytree": 0.58,
        "colsample_bylevel": 0.72,
        "learning_rate": 0.06,
        "n_estimators": 1400,
        "reg_alpha": 0.45,
        "reg_lambda": 6.5,
        "gamma": 0.22,
        "max_delta_step": 0,
        "random_state": 42,
        "n_jobs": -1,
    }


def fit_final_ensemble(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    params: Dict[str, Any],
    *,
    ensemble_size: int,
    early_stopping_rounds: int,
    base_seed: int,
    legacy_weights: bool,
) -> List[xgb.XGBRegressor]:
    """全训练集：每个成员独立划分早停验证集 + 不同 random_state。"""
    models: List[xgb.XGBRegressor] = []
    for k in range(ensemble_size):
        seed = base_seed + k * 17
        tr_sub, va_sub = train_test_split(
            train_df,
            test_size=INNER_VAL_FRACTION,
            random_state=seed,
            stratify=train_df["price_bucket"],
        )
        p = {**params, "random_state": seed}
        w = _sample_weights_array(
            tr_sub["price"].to_numpy(dtype=np.float64, copy=False),
            legacy_weights=legacy_weights,
        )
        m = _fit_one(
            tr_sub[feature_cols],
            tr_sub["price_log"].values,
            w,
            va_sub[feature_cols],
            va_sub["price_log"].values,
            p,
            early_stopping_rounds,
        )
        models.append(m)
    return models


def predict_ensemble_mean_log(models: Sequence[xgb.XGBRegressor], X: pd.DataFrame) -> np.ndarray:
    preds = np.column_stack([m.predict(X) for m in models])
    return preds.mean(axis=1)


def evaluate(
    y_raw: np.ndarray,
    pred_log: np.ndarray,
    name: str,
) -> Dict[str, float]:
    y_pred = np.expm1(pred_log)
    mae = mean_absolute_error(y_raw, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_raw, y_pred)))
    r2 = r2_score(y_raw, y_pred)
    mape = float(np.mean(np.abs((y_raw - y_pred) / y_raw)) * 100)
    print(f"\n{name}:")
    print(f"  MAE:  {mae:.2f} 元")
    print(f"  RMSE: {rmse:.2f} 元")
    print(f"  R²:   {r2:.4f}")
    print(f"  MAPE: {mape:.1f}%")
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}


def mean_feature_importance(models: Sequence[xgb.XGBRegressor], feature_cols: List[str]) -> pd.DataFrame:
    imp = np.mean([m.feature_importances_ for m in models], axis=0)
    return (
        pd.DataFrame({"feature": feature_cols, "importance": imp})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def save_all(
    models: List[xgb.XGBRegressor],
    feature_cols: List[str],
    extra_engineered: List[str],
    train_metrics: Dict[str, float],
    test_metrics: Dict[str, float],
    importance: pd.DataFrame,
    encoders: Dict[str, Any],
    district_stats: pd.DataFrame,
    calendar_defaults: Dict[str, float],
    cal_seg_art: Dict[str, Any],
    numeric_imputations: Dict[str, float],
    kept_facility_cols: List[str],
    sparse_dropped: List[str],
    best_params: Dict[str, Any],
    cv_mae: float,
    data_source_label: str,
    n_train: int,
    n_test: int,
    ensemble_size: int,
    training_meta: Optional[Dict[str, Any]] = None,
) -> None:
    bundle = {
        "version": 1,
        "estimators": models,
        "feature_names": feature_cols,
        "extra_engineered_features": extra_engineered,
        "target_transform": "log1p",
        "inverse_transform": "expm1",
        "ensemble_predict": "mean of booster.predict in log space, then expm1",
        "best_xgb_params_template": {k: v for k, v in best_params.items() if k not in ("random_state", "n_jobs")},
        "ensemble_size": ensemble_size,
    }
    joblib.dump(bundle, MODELS_DIR / "price_model_advanced_bundle.joblib")
    print(f"\n集成包: {MODELS_DIR / 'price_model_advanced_bundle.joblib'}")

    # 单文件备份：第一个成员（便于仅用单模型时 joblib.load）
    joblib.dump(models[0], MODELS_DIR / f"xgboost_price_model_{ARTIFACT_TAG}.pkl")

    with open(MODELS_DIR / f"feature_names_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)

    joblib.dump(encoders["district"], MODELS_DIR / f"district_encoder_{ARTIFACT_TAG}.pkl")
    joblib.dump(encoders["trade_area"], MODELS_DIR / f"trade_area_encoder_{ARTIFACT_TAG}.pkl")
    joblib.dump(encoders["house_type"], MODELS_DIR / f"house_type_encoder_{ARTIFACT_TAG}.pkl")

    district_stats.to_json(
        MODELS_DIR / f"district_stats_{ARTIFACT_TAG}.json",
        orient="records",
        force_ascii=False,
        indent=2,
    )
    with open(MODELS_DIR / f"calendar_feature_defaults_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(calendar_defaults, f, ensure_ascii=False, indent=2)
    with open(MODELS_DIR / f"calendar_segment_table_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(cal_seg_art, f, ensure_ascii=False, indent=2, default=str)
    with open(MODELS_DIR / f"facility_columns_active_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(kept_facility_cols, f, ensure_ascii=False, indent=2)
    with open(MODELS_DIR / f"numeric_imputation_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(numeric_imputations, f, ensure_ascii=False, indent=2)

    metrics = {
        "metrics": test_metrics,
        "train_metrics": train_metrics,
        "cv_mean_mae_original_scale": cv_mae,
        "ensemble_size": ensemble_size,
        "extra_engineered_features": extra_engineered,
        "best_params": {k: v for k, v in best_params.items() if k != "n_jobs"},
        "data_source": data_source_label,
        "feature_count": len(feature_cols),
        "sample_count_train": n_train,
        "sample_count_test": n_test,
        "trained_at": pd.Timestamp.now().isoformat(),
        "facility_columns_dropped_sparse": sparse_dropped,
        "calendar_feature_names": list(tmm.CALENDAR_FEATURE_NAMES),
        "methodology": (
            "Same leakage-safe preprocess as train_model_mysql; extra numeric features; "
            "stratified K-fold random search on original-scale MAE (aggregate mean or median per --cv-aggregate); "
            "test holdout never used for selection; final ensemble with inner early stopping. "
            "Default search emphasizes shallow trees + strong regularization for generalization."
        ),
    }
    if training_meta:
        metrics["training_meta"] = training_meta
    with open(MODELS_DIR / f"model_metrics_{ARTIFACT_TAG}.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    importance.to_csv(
        MODELS_DIR / f"feature_importance_{ARTIFACT_TAG}.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main() -> None:
    env_default = os.environ.get("TRAIN_DATA_SOURCE", "auto").strip().lower()
    if env_default not in ("auto", "hive", "mysql"):
        env_default = "auto"

    parser = argparse.ArgumentParser(description="进阶 XGBoost：工程特征 + 搜索 + 集成（独立产物）")
    parser.add_argument("--data-source", choices=("auto", "hive", "mysql"), default=env_default)
    parser.add_argument("--cv", type=int, default=5)
    parser.add_argument("--n-trials", type=int, default=50, help="随机搜索候选组数（含默认起点）")
    parser.add_argument(
        "--early-stopping-rounds",
        type=int,
        default=70,
        help="早停轮数；默认略收紧以抑制过拟合",
    )
    parser.add_argument(
        "--ensemble-size",
        type=int,
        default=3,
        help="集成成员数；单模型可设 1 或 --no-ensemble",
    )
    parser.add_argument(
        "--no-ensemble",
        action="store_true",
        help="单模型（等价于 --ensemble-size 1，训练更快）",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-search", action="store_true", help="跳过搜索，仅用默认参数")
    parser.add_argument(
        "--aggressive-search",
        action="store_true",
        help="使用深树/宽搜索空间（易过拟合；默认关闭为泛化优先）",
    )
    parser.add_argument(
        "--legacy-weights",
        action="store_true",
        help="样本权重 2.0/1.5（与线脚本同量级）；默认用温和权重减轻尾部过拟合",
    )
    parser.add_argument(
        "--cv-aggregate",
        choices=("mean", "median"),
        default="median",
        help="多折 CV 汇总方式；median 对异常折更稳（默认）",
    )
    args = parser.parse_args()
    if args.no_ensemble:
        args.ensemble_size = 1
    rng = random.Random(args.seed)

    print("\n" + "=" * 60)
    print("进阶 XGBoost（工程特征 + CV 搜索 + 可选集成）")
    mode = "aggressive" if args.aggressive_search else "generalization"
    print(
        f"数据 {args.data_source} | CV={args.cv}({args.cv_aggregate}) | trials={args.n_trials} | "
        f"集成={args.ensemble_size} | 模式={mode} | 权重={'legacy' if args.legacy_weights else 'soft'}"
    )
    print("=" * 60)

    df, data_source_label = tmm.load_training_data(args.data_source)
    df = df[(df["price"] >= 50) & (df["price"] <= 5000)].copy()
    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(tmm.price_bucket)

    train_df, test_df = tmm.stratified_holdout(df)
    (
        train_df,
        test_df,
        encoders,
        district_stats,
        base_features,
        calendar_defaults,
        _trade_area_stats,
    ) = tmm.preprocess_after_split(train_df, test_df)

    kept_facility_cols = [c for c in base_features if c in _FACILITY_COL_NAMES]
    sparse_dropped: List[str] = []
    numeric_imputations: Dict[str, float] = {}
    cal_seg_art: Dict[str, Any] = {
        "version": 0,
        "note": "当前 preprocess_after_split 仅返回 calendar_defaults，无单独段表对象",
    }

    if len(train_df) < 50 or len(test_df) < 10:
        print("样本过少，退出。")
        sys.exit(1)

    extra_cols = add_engineered_features(train_df, test_df, set(base_features))
    feature_cols = merge_feature_list(base_features, extra_cols)

    for c in feature_cols:
        if c in train_df.columns and train_df[c].isna().any():
            train_df[c] = train_df[c].fillna(0)
        if c in test_df.columns and test_df[c].isna().any():
            test_df[c] = test_df[c].fillna(0)

    best_params = default_baseline_like_params(aggressive=args.aggressive_search)
    cv_mae = cv_mean_mae(
        train_df,
        feature_cols,
        best_params,
        n_splits=args.cv,
        early_stopping_rounds=args.early_stopping_rounds,
        random_state=args.seed,
        legacy_weights=args.legacy_weights,
        cv_aggregate=args.cv_aggregate,
    )
    agg_label = "中位数" if args.cv_aggregate == "median" else "均值"
    print(f"\n默认参数 CV MAE（原价，各折{agg_label}）: {cv_mae:.4f}")

    if not args.skip_search:
        best_mae = cv_mae
        for t in range(1, args.n_trials):
            cand = random_params(rng, aggressive=args.aggressive_search)
            try:
                mae = cv_mean_mae(
                    train_df,
                    feature_cols,
                    cand,
                    n_splits=args.cv,
                    early_stopping_rounds=args.early_stopping_rounds,
                    random_state=args.seed,
                    legacy_weights=args.legacy_weights,
                    cv_aggregate=args.cv_aggregate,
                )
            except Exception as e:
                print(f"  [trial {t}] 跳过（参数/目标不兼容）: {e}")
                continue
            if mae < best_mae:
                best_mae = mae
                best_params = {k: v for k, v in cand.items()}
                print(f"  [trial {t}] 更优 CV MAE={mae:.4f}")
        cv_mae = best_mae
        print(f"\n搜索结束: 最优 CV 平均 MAE = {cv_mae:.4f}")
        print("最优参数:", json.dumps({k: v for k, v in best_params.items() if k != "n_jobs"}, indent=2, default=str))

    print(f"\n训练最终模型（成员数 {args.ensemble_size}）…")
    ens = fit_final_ensemble(
        train_df,
        feature_cols,
        best_params,
        ensemble_size=max(1, args.ensemble_size),
        early_stopping_rounds=args.early_stopping_rounds,
        base_seed=args.seed,
        legacy_weights=args.legacy_weights,
    )

    X_tr = train_df[feature_cols]
    X_te = test_df[feature_cols]
    pred_tr_log = predict_ensemble_mean_log(ens, X_tr)
    pred_te_log = predict_ensemble_mean_log(ens, X_te)

    train_metrics = evaluate(train_df["price"].values, pred_tr_log, "训练集（全训练样本，集成平均）")
    test_metrics = evaluate(test_df["price"].values, pred_te_log, "测试集（留出）")

    gap_r2 = train_metrics["r2"] - test_metrics["r2"]
    if gap_r2 > 0.28:
        print(f"\n[提示] 训练R² - 测试R² = {gap_r2:.3f}，若测试 MAE 仍不满意可试 --no-ensemble 或更强正则")

    imp = mean_feature_importance(ens, feature_cols)
    print("\n特征重要性 Top 12（集成平均）:")
    print(imp.head(12).to_string(index=False))

    save_all(
        ens,
        feature_cols,
        extra_cols,
        train_metrics,
        test_metrics,
        imp,
        encoders,
        district_stats,
        calendar_defaults,
        cal_seg_art,
        numeric_imputations,
        kept_facility_cols,
        sparse_dropped,
        best_params,
        cv_mae,
        data_source_label,
        len(train_df),
        len(test_df),
        len(ens),
        training_meta={
            "aggressive_search": args.aggressive_search,
            "legacy_weights": args.legacy_weights,
            "cv_aggregate": args.cv_aggregate,
            "early_stopping_rounds": args.early_stopping_rounds,
        },
    )

    print("\n" + "=" * 60)
    print("完成。对比 `train_model_mysql.py` 请看同一测试集上 MAE / R²。")
    print("=" * 60)


if __name__ == "__main__":
    main()
