# -*- coding: utf-8 -*-
"""
民宿价格预测模型训练（MySQL / Hive ODS）— 毕业论文可用流程
==========================================================

**部署说明**：线上 API 定价仅加载 ``train_model_daily_mysql.py`` 的日级产物；本脚本输出不再由
``ModelManager`` 加载，仅供离线实验或论文复现对照。

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
6. 商圈目标编码：仅用训练集按 trade_area 聚合 ta_mean/median/std/count；n≥TRAIN_MIN_TRADE_AREA_SAMPLES
   的商圈写入 trade_area_target_stats.json；稀疏/未见商圈用该行 dist_* 回退（无测试集泄漏）。
7. 价格日历：离线训练造特征时从 price_calendars / Hive 按 unit_id 聚合；剔除「有日历行但全日价格为 0」
   的房源后再训练。**定价 API 不查库**，推理侧日历列用 calendar_feature_defaults.json。训练时对日历列做随机 dropout（置默认），
   早停验证集始终为冷日历；**训练/测试集上打印的指标**均在预测前将日历列置为默认值（与 API 一致），
   不使用行内离线合并的真实 cal_*。
8. 早停：训练集内 85/15 划分，验证折日历=默认；**禁止**用留出测试集参与早停或调参。

运行：在 Tujia-backend 目录下
    python scripts/train_model_mysql.py
    python scripts/train_model_mysql.py --data-source hive    # 仅 Hive ODS
    python scripts/train_model_mysql.py --data-source mysql   # 仅 MySQL
    python scripts/train_model_mysql.py --data-source auto    # 优先 Hive，失败则 MySQL

环境变量 TRAIN_DATA_SOURCE=auto|hive|mysql 可覆盖默认（命令行优先）。
TRAIN_CALENDAR_DROPOUT_PROB：训练行日历列随机替换为默认的比例，默认 0.5。
TRAIN_XGB_NUM_BOOST_ROUND / TRAIN_XGB_EARLY_STOPPING_ROUNDS / TRAIN_XGB_MAX_DEPTH / TRAIN_XGB_GAMMA 等可调树与早停。
TRAIN_MIN_TRADE_AREA_SAMPLES：商圈目标编码最少样本数，默认 3。

超参搜索（与线上一致）：python scripts/train_model_mysql.py --tune [--tune-trials 40] [--tune-folds 4]
在**训练集内**分层 K 折上最小化冷日历验证 MAE（原价）；留出测试集不参与选参。需 pip install optuna。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import StratifiedKFold, train_test_split

warnings.filterwarnings("ignore")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Listing, SessionLocal
from app.ml.calendar_features import (
    CALENDAR_FEATURE_NAMES,
    filter_out_all_zero_price_calendar_units,
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

    df, n_drop_zero_cal = filter_out_all_zero_price_calendar_units(df)
    if n_drop_zero_cal:
        print(f"已剔除价格日历全日为 0 的房源: {n_drop_zero_cal} 条")

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


def _replace_calendar_with_defaults(
    x: pd.DataFrame, calendar_defaults: Dict[str, float]
) -> pd.DataFrame:
    out = x.copy()
    for c in CALENDAR_FEATURE_NAMES:
        if c in out.columns:
            out[c] = float(calendar_defaults.get(c, 0.0))
    return out


def _calendar_dropout_train(
    x: pd.DataFrame,
    calendar_defaults: Dict[str, float],
    prob: float,
    seed: int = 42,
) -> pd.DataFrame:
    """按行以概率 prob 将日历列替换为训练导出的默认值，弱化对逐套真实日历的依赖。"""
    out = x.copy()
    cal_cols = [c for c in CALENDAR_FEATURE_NAMES if c in out.columns]
    if not cal_cols or prob <= 0:
        return out
    rng = np.random.default_rng(seed)
    n = len(out)
    drop = rng.random(n) < prob
    if not drop.any():
        return out
    defaults = {c: float(calendar_defaults.get(c, 0.0)) for c in cal_cols}
    idx = np.where(drop)[0]
    for i in idx:
        for c in cal_cols:
            out.iat[i, out.columns.get_loc(c)] = defaults[c]
    return out


def _metrics_dict(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)
    denom = np.maximum(y_true.astype(np.float64), 1e-6)
    mape = float(np.mean(np.abs((y_true - y_pred) / denom)) * 100)
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}


def _price_row_weight(price: float) -> float:
    if price < 100:
        return 2.0
    if price > 500:
        return 1.5
    return 1.0


def _nthread() -> int:
    return max(1, min(32, (os.cpu_count() or 4)))


def _build_booster_params_from_env() -> Dict[str, Any]:
    return {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "max_depth": int(os.environ.get("TRAIN_XGB_MAX_DEPTH", "6")),
        "min_child_weight": float(os.environ.get("TRAIN_XGB_MIN_CHILD_WEIGHT", "3")),
        "subsample": float(os.environ.get("TRAIN_XGB_SUBSAMPLE", "0.8")),
        "colsample_bytree": float(os.environ.get("TRAIN_XGB_COLSAMPLE_BYTREE", "0.8")),
        "eta": float(os.environ.get("TRAIN_XGB_ETA", "0.05")),
        "reg_alpha": float(os.environ.get("TRAIN_XGB_REG_ALPHA", "0.1")),
        "reg_lambda": float(os.environ.get("TRAIN_XGB_REG_LAMBDA", "1.0")),
        "gamma": float(os.environ.get("TRAIN_XGB_GAMMA", "0")),
        "seed": 42,
        "nthread": _nthread(),
    }


def _fit_xgb_booster_cold_val(
    X_fit_mixed: pd.DataFrame,
    X_val_cold: pd.DataFrame,
    y_fit_log: pd.Series,
    y_val_log: pd.Series,
    weights_fit: pd.Series,
    feature_cols: List[str],
    native_params: Dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int,
) -> Any:
    X_fit_np = np.ascontiguousarray(X_fit_mixed.to_numpy(dtype=np.float32))
    X_val_np = np.ascontiguousarray(X_val_cold.to_numpy(dtype=np.float32))
    d_fit = xgb.DMatrix(
        X_fit_np,
        label=np.ascontiguousarray(y_fit_log.to_numpy(dtype=np.float32)),
        weight=np.ascontiguousarray(weights_fit.to_numpy(dtype=np.float32)),
        feature_names=list(feature_cols),
    )
    d_val = xgb.DMatrix(
        X_val_np,
        label=np.ascontiguousarray(y_val_log.to_numpy(dtype=np.float32)),
        feature_names=list(feature_cols),
    )
    return xgb.train(
        native_params,
        d_fit,
        num_boost_round=num_boost_round,
        evals=[(d_val, "validation")],
        early_stopping_rounds=early_stopping_rounds,
        verbose_eval=False,
    )


def _cv_mean_mae_cold_calendar(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    calendar_defaults: Dict[str, float],
    native_params: Dict[str, Any],
    cal_dropout_prob: float,
    num_boost_round: int,
    es_rounds: int,
    n_folds: int,
    base_seed: int,
    trial_offset: int = 0,
) -> float:
    """
    仅在 train_df 上分层 K 折：fit 用日历 dropout，早停验证=冷日历；
    返回各折验证集「冷日历 expm1 预测 vs 原价」MAE 均值。
    """
    n = len(train_df)
    if n < 80:
        raise ValueError("训练样本过少，无法进行可靠交叉验证")
    y_strat = train_df["price_bucket"].values
    max_k = int(pd.Series(y_strat).value_counts().min())
    if max_k < 2:
        raise ValueError("price_bucket 分层失败，请检查数据")
    k = min(max(2, n_folds), max_k)
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=base_seed)
    maes: List[float] = []
    for fold_i, (tr_i, va_i) in enumerate(skf.split(np.zeros(n), y_strat)):
        tr = train_df.iloc[tr_i]
        va = train_df.iloc[va_i]
        X_tr = tr[feature_cols]
        X_va = va[feature_cols]
        y_tr_log = tr["price_log"]
        y_va_log = va["price_log"]
        y_va_raw = va["price"]
        w_tr = tr["price"].apply(_price_row_weight)
        drop_seed = base_seed + fold_i * 97 + trial_offset * 1009
        X_tr_mixed = _calendar_dropout_train(
            X_tr, calendar_defaults, cal_dropout_prob, seed=drop_seed
        )
        X_va_cold = _replace_calendar_with_defaults(X_va, calendar_defaults)
        booster = _fit_xgb_booster_cold_val(
            X_tr_mixed,
            X_va_cold,
            y_tr_log,
            y_va_log,
            w_tr,
            feature_cols,
            dict(native_params),
            num_boost_round,
            es_rounds,
        )
        dm = xgb.DMatrix(
            np.ascontiguousarray(X_va_cold.to_numpy(dtype=np.float32)),
            feature_names=list(feature_cols),
        )
        pred = np.expm1(booster.predict(dm))
        maes.append(mean_absolute_error(y_va_raw.values, pred))
    return float(np.mean(maes))


def _trial_to_hyperparam_dict(
    max_depth: int,
    min_child_weight: float,
    subsample: float,
    colsample_bytree: float,
    eta: float,
    reg_alpha: float,
    reg_lambda: float,
    gamma: float,
    calendar_dropout_prob: float,
    num_boost_round: int,
    early_stopping_rounds: int,
) -> Dict[str, Any]:
    return {
        "native_params": {
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "max_depth": max_depth,
            "min_child_weight": min_child_weight,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "eta": eta,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "gamma": gamma,
            "seed": 42,
            "nthread": _nthread(),
        },
        "calendar_dropout_prob": calendar_dropout_prob,
        "num_boost_round": num_boost_round,
        "early_stopping_rounds": early_stopping_rounds,
    }


def _hyperparams_from_optuna_params(p: Dict[str, Any]) -> Dict[str, Any]:
    return _trial_to_hyperparam_dict(
        max_depth=int(p["max_depth"]),
        min_child_weight=float(p["min_child_weight"]),
        subsample=float(p["subsample"]),
        colsample_bytree=float(p["colsample_bytree"]),
        eta=float(p["eta"]),
        reg_alpha=float(p["reg_alpha"]),
        reg_lambda=float(p["reg_lambda"]),
        gamma=float(p["gamma"]),
        calendar_dropout_prob=float(p["calendar_dropout"]),
        num_boost_round=int(p["num_boost_round"]),
        early_stopping_rounds=int(p["early_stopping_rounds"]),
    )


def _optuna_objective_factory(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    calendar_defaults: Dict[str, float],
    n_folds: int,
    base_seed: int,
) -> Callable[[Any], float]:
    def objective(trial: Any) -> float:
        hp = _trial_to_hyperparam_dict(
            max_depth=trial.suggest_int("max_depth", 3, 8),
            min_child_weight=trial.suggest_float("min_child_weight", 1.0, 10.0, log=True),
            subsample=trial.suggest_float("subsample", 0.65, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.65, 1.0),
            eta=trial.suggest_float("eta", 0.02, 0.11, log=True),
            reg_alpha=trial.suggest_float("reg_alpha", 0.02, 1.5, log=True),
            reg_lambda=trial.suggest_float("reg_lambda", 0.4, 6.0, log=True),
            gamma=trial.suggest_float("gamma", 0.0, 0.6),
            calendar_dropout_prob=trial.suggest_float("calendar_dropout", 0.38, 0.72),
            num_boost_round=trial.suggest_int("num_boost_round", 500, 2200),
            early_stopping_rounds=trial.suggest_int("early_stopping_rounds", 35, 130),
        )
        return _cv_mean_mae_cold_calendar(
            train_df,
            feature_cols,
            calendar_defaults,
            hp["native_params"],
            float(hp["calendar_dropout_prob"]),
            int(hp["num_boost_round"]),
            int(hp["early_stopping_rounds"]),
            n_folds,
            base_seed,
            trial_offset=int(trial.number),
        )

    return objective


def _random_search_hyperparams(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    calendar_defaults: Dict[str, float],
    n_trials: int,
    n_folds: int,
    base_seed: int,
) -> Tuple[Dict[str, Any], float]:
    rng = np.random.default_rng(base_seed)
    best_mae = float("inf")
    best_hp: Optional[Dict[str, Any]] = None
    for t in range(n_trials):
        hp = _trial_to_hyperparam_dict(
            max_depth=int(rng.integers(3, 9)),
            min_child_weight=float(10 ** rng.uniform(np.log10(1.0), np.log10(10.0))),
            subsample=float(rng.uniform(0.65, 1.0)),
            colsample_bytree=float(rng.uniform(0.65, 1.0)),
            eta=float(10 ** rng.uniform(np.log10(0.02), np.log10(0.11))),
            reg_alpha=float(10 ** rng.uniform(np.log10(0.02), np.log10(1.5))),
            reg_lambda=float(10 ** rng.uniform(np.log10(0.4), np.log10(6.0))),
            gamma=float(rng.uniform(0.0, 0.6)),
            calendar_dropout_prob=float(rng.uniform(0.38, 0.72)),
            num_boost_round=int(rng.integers(500, 2201)),
            early_stopping_rounds=int(rng.integers(35, 131)),
        )
        mae = _cv_mean_mae_cold_calendar(
            train_df,
            feature_cols,
            calendar_defaults,
            hp["native_params"],
            float(hp["calendar_dropout_prob"]),
            int(hp["num_boost_round"]),
            int(hp["early_stopping_rounds"]),
            n_folds,
            base_seed,
            trial_offset=t,
        )
        if mae < best_mae:
            best_mae = mae
            best_hp = hp
    assert best_hp is not None
    return best_hp, best_mae


def run_hyperparameter_search(
    train_df: pd.DataFrame,
    feature_cols: List[str],
    calendar_defaults: Dict[str, float],
    n_trials: int,
    n_folds: int,
    seed: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """返回 (hyperparams 包, 元数据)。优化目标：冷日历验证 MAE（原价）的 CV 均值。"""
    meta: Dict[str, Any] = {"n_trials": n_trials, "n_folds_requested": n_folds, "seed": seed}
    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="minimize", study_name="price_xgb_cold_mae")
        study.optimize(
            _optuna_objective_factory(train_df, feature_cols, calendar_defaults, n_folds, seed),
            n_trials=n_trials,
            show_progress_bar=False,
        )
        bt = study.best_trial
        meta["backend"] = "optuna"
        meta["best_cv_mae_mean"] = float(bt.value)
        meta["study_summary"] = {
            "n_trials_completed": len(study.trials),
            "best_trial_number": bt.number,
        }
        hp = _hyperparams_from_optuna_params(bt.params)
        return hp, meta
    except ImportError:
        print("[调参] 未安装 optuna，使用随机搜索（建议: pip install optuna）")
        hp, best_mae = _random_search_hyperparams(
            train_df, feature_cols, calendar_defaults, n_trials, n_folds, seed
        )
        meta["backend"] = "random_fallback"
        meta["best_cv_mae_mean"] = float(best_mae)
        return hp, meta


def _category_map(series: pd.Series) -> Dict[str, int]:
    """在训练集上拟合类别 -> 整数编码（按字典序稳定可复现）。"""
    s = series.fillna("").astype(str)
    cats = sorted(s.unique())
    return {c: i for i, c in enumerate(cats)}


def _apply_category_map(series: pd.Series, mapping: Dict[str, int], default: int = 0) -> pd.Series:
    return series.fillna("").astype(str).map(lambda x: mapping.get(x, default))


def preprocess_after_split(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    Dict[str, Any],
    pd.DataFrame,
    List[str],
    Dict[str, float],
    pd.DataFrame,
]:
    """
    在训练/测试划分之后：仅用训练集估计行政区/商圈目标编码与类别映射，再变换两侧数据。
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

    # —— 商圈目标编码：仅训练集聚合；稀疏商圈用行政区统计回退 ——
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
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df["_ta_join"] = train_df["trade_area"].fillna("").astype(str).str.strip()
    test_df["_ta_join"] = test_df["trade_area"].fillna("").astype(str).str.strip()
    train_df = train_df.merge(reliable_ta, how="left", left_on="_ta_join", right_on="join_key")
    train_df = train_df.drop(columns=["_ta_join", "join_key"], errors="ignore")
    test_df = test_df.merge(reliable_ta, how="left", left_on="_ta_join", right_on="join_key")
    test_df = test_df.drop(columns=["_ta_join", "join_key"], errors="ignore")
    for ta_c, dist_c in [
        ("ta_mean", "dist_mean"),
        ("ta_median", "dist_median"),
        ("ta_std", "dist_std"),
        ("ta_count", "dist_count"),
    ]:
        train_df[ta_c] = train_df[ta_c].fillna(train_df[dist_c])
        test_df[ta_c] = test_df[ta_c].fillna(test_df[dist_c])
    trade_area_stats_export = reliable_ta.rename(columns={"join_key": "trade_area"})
    print(
        f"商圈目标编码: n>={min_ta} 的商圈数 {len(trade_area_stats_export)} "
        f"（稀疏/未见商圈用行政区 dist_* 回退）"
    )

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
    train_df["heat_score"] = train_df["favorite_count"] * train_df["rating"] / 10
    test_df["heat_score"] = test_df["favorite_count"] * test_df["rating"] / 10

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
        "ta_mean",
        "ta_median",
        "ta_std",
        "ta_count",
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
    return (
        train_df,
        test_df,
        encoders,
        district_stats,
        feature_cols,
        calendar_defaults,
        trade_area_stats_export,
    )


def train_xgb_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
    calendar_defaults: Dict[str, float],
    hyperparams: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Dict[str, float], Dict[str, float], pd.DataFrame]:
    print("\n" + "=" * 60)
    print("模型训练 (XGBoost + 对数目标 + 样本权重 + 日历 dropout + 冷日历早停)")
    print("=" * 60)

    idx = np.arange(len(train_df))
    strat = None
    if "price_bucket" in train_df.columns and len(train_df) >= 80:
        vc = train_df["price_bucket"].value_counts()
        if vc.min() >= 2:
            strat = train_df["price_bucket"].values
    fit_idx, val_idx = train_test_split(
        idx, test_size=0.15, random_state=42, shuffle=True, stratify=strat
    )

    X_fit = train_df.iloc[fit_idx][feature_cols]
    X_val = train_df.iloc[val_idx][feature_cols]
    y_fit_log = train_df["price_log"].iloc[fit_idx]
    y_val_log = train_df["price_log"].iloc[val_idx]
    weights_fit = train_df["price"].iloc[fit_idx].apply(_price_row_weight)

    if hyperparams is not None:
        native_params = dict(hyperparams["native_params"])
        native_params["seed"] = 42
        native_params["nthread"] = _nthread()
        cal_dropout_prob = float(hyperparams["calendar_dropout_prob"])
        num_boost_round = int(hyperparams["num_boost_round"])
        es_rounds = int(hyperparams["early_stopping_rounds"])
    else:
        native_params = _build_booster_params_from_env()
        cal_dropout_prob = float(os.environ.get("TRAIN_CALENDAR_DROPOUT_PROB", "0.5"))
        num_boost_round = int(os.environ.get("TRAIN_XGB_NUM_BOOST_ROUND", "1200"))
        es_rounds = int(os.environ.get("TRAIN_XGB_EARLY_STOPPING_ROUNDS", "80"))

    X_fit_mixed = _calendar_dropout_train(X_fit, calendar_defaults, cal_dropout_prob, seed=42)
    X_val_cold = _replace_calendar_with_defaults(X_val, calendar_defaults)
    print(
        f"日历稳健训练: 训练行日历 dropout 概率={cal_dropout_prob:.2f}；"
        f"早停验证集日历列=训练导出默认值（与线上一致）"
    )

    booster = _fit_xgb_booster_cold_val(
        X_fit_mixed,
        X_val_cold,
        y_fit_log,
        y_val_log,
        weights_fit,
        feature_cols,
        native_params,
        num_boost_round,
        es_rounds,
    )
    booster_best = getattr(booster, "best_iteration", None)
    try:
        n_trees = int(booster.num_boosted_rounds())
    except Exception:
        n_trees = -1
    print(
        f"早停: best_iteration={booster_best} | 树棵数={n_trees} / 上限 {num_boost_round}"
    )

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

    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train_raw = train_df["price"]
    y_test_raw = test_df["price"]

    # 训练/测试指标均用默认日历列预测，与线上一致（不利用行内真实合并的 cal_*）
    if any(c in feature_cols for c in CALENDAR_FEATURE_NAMES):
        X_train_eval = _replace_calendar_with_defaults(X_train, calendar_defaults)
        X_test_eval = _replace_calendar_with_defaults(X_test, calendar_defaults)
    else:
        X_train_eval = X_train
        X_test_eval = X_test
    y_pred_train = np.expm1(model.predict(X_train_eval))
    y_pred_test = np.expm1(model.predict(X_test_eval))

    def _print_metrics_block(name: str, m: Dict[str, float]) -> None:
        print(f"\n{name}:")
        print(f"  MAE:  {m['mae']:.2f} 元")
        print(f"  RMSE: {m['rmse']:.2f} 元")
        print(f"  R²:   {m['r2']:.4f}")
        print(f"  MAPE: {m['mape']:.1f}%")

    train_metrics = _metrics_dict(y_train_raw.values, y_pred_train)
    test_metrics = _metrics_dict(y_test_raw.values, y_pred_test)

    _print_metrics_block("训练集", train_metrics)
    _print_metrics_block("测试集", test_metrics)

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
            mape = float(
                np.mean(np.abs((subset["true"] - subset["pred"]) / subset["true"])) * 100
            )
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
    tuning_meta: Optional[Dict[str, Any]] = None,
    trade_area_stats: Optional[pd.DataFrame] = None,
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

    if trade_area_stats is not None:
        p_ta = OUTPUT_DIR / "trade_area_target_stats.json"
        if len(trade_area_stats) > 0:
            trade_area_stats.to_json(p_ta, orient="records", force_ascii=False, indent=2)
        else:
            with open(p_ta, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
        print(f"商圈目标编码表: {p_ta}（{len(trade_area_stats)} 条）")

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
            "target_encoding": (
                "district + trade_area price moments estimated on training split only; "
                "sparse trade_area uses district fallback"
            ),
            "categorical_encoding": "integer codes fitted on training split only; OOV -> 0",
            "target_transform": "log1p(price); prediction expm1",
            "is_budget_definition": "structural: area<30 and bedroom_count<=1 (no price in feature)",
            "facility_count": "sum of binary facility columns in FACILITY_KEYWORDS mapping",
            "heat_score": "favorite_count * rating / 10 (train + ModelManager)",
            "sample_weights": "higher weight for price<100 and price>500 in training",
            "early_stopping": (
                "85/15 split inside training fold; validation uses cold calendar defaults; "
                "native xgb.train with early_stopping_rounds; test set never used for rounds"
            ),
            "calendar_robust_training": (
                "Training rows: each sample's calendar features replaced by defaults with "
                "probability TRAIN_CALENDAR_DROPOUT_PROB (default 0.5)."
            ),
            "train_test_evaluation": (
                "Reported train and test metrics both predict with calendar columns = "
                "calendar_feature_defaults.json (same as API; no per-row merged calendar at eval)."
            ),
            "price_calendar_features": (
                "Per-unit aggregates (CALENDAR_FEATURE_NAMES): from MySQL price_calendars when "
                "training on MySQL; from Hive ODS ods_price_calendar when training on Hive "
                "(weekend premium may be 0 if not computed in the warehouse). "
                "Listings with calendar rows but all daily prices <= 0 are dropped before training. "
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
            "price_calendar: 离线造特征 + 训练集条件中位数填充",
            "calendar_dropout + cold_calendar_early_stop: 对齐线上不查库",
            "train_test_metrics: 训练/测试集评估预测时日历=默认值，与 API 一致",
            "trade_area_target_encoding: ta_mean/median/std/count + trade_area_target_stats.json",
        ],
    }
    if tuning_meta is not None:
        metrics_data["hyperparameter_tuning"] = tuning_meta
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
    parser.add_argument(
        "--tune",
        action="store_true",
        help="在训练集上做分层 K 折 + Optuna，最小化冷日历验证 MAE；再全量训练并评估留出测试集",
    )
    parser.add_argument(
        "--tune-trials",
        type=int,
        default=40,
        help="Optuna 试验次数（默认 40）",
    )
    parser.add_argument(
        "--tune-folds",
        type=int,
        default=4,
        help="交叉验证折数（默认 4，受各价格分桶最小样本数限制）",
    )
    parser.add_argument(
        "--tune-seed",
        type=int,
        default=42,
        help="调参 CV 与搜索的随机种子",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("民宿价格预测模型训练（论文规范流程）")
    print(f"数据模式: {args.data_source}" + (" | 超参搜索: 开" if args.tune else ""))
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

    (
        train_df,
        test_df,
        encoders,
        district_stats,
        feature_cols,
        calendar_defaults,
        trade_area_stats_export,
    ) = preprocess_after_split(train_df, test_df)
    if len(train_df) < 50 or len(test_df) < 10:
        print("错误: 训练或测试样本过少，请检查数据库或过滤条件。")
        sys.exit(1)

    tuning_meta: Optional[Dict[str, Any]] = None
    hp_override: Optional[Dict[str, Any]] = None
    if args.tune:
        print("\n" + "=" * 60)
        print(
            "超参搜索：目标=训练集内 K 折「冷日历」验证 MAE（原价）；"
            "留出测试集不参与选参"
        )
        print("=" * 60)
        hp_override, tuning_meta = run_hyperparameter_search(
            train_df,
            feature_cols,
            calendar_defaults,
            n_trials=max(5, args.tune_trials),
            n_folds=max(2, args.tune_folds),
            seed=args.tune_seed,
        )
        tune_path = OUTPUT_DIR / "xgb_tune_best_params.json"
        with open(tune_path, "w", encoding="utf-8") as f:
            json.dump(
                {"hyperparams": hp_override, "meta": tuning_meta},
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        print(
            f"最优 CV 平均 MAE（冷日历）: {tuning_meta['best_cv_mae_mean']:.4f} 元 | "
            f"已写入 {tune_path}"
        )

    model, train_metrics, test_metrics, importance = train_xgb_model(
        train_df, test_df, feature_cols, calendar_defaults, hyperparams=hp_override
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
        tuning_meta=tuning_meta,
        trade_area_stats=trade_area_stats_export,
    )

    print("\n" + "=" * 60)
    print("训练完成")
    print("=" * 60)
    print(f"测试集 R²: {test_metrics['r2']:.4f} | MAE: {test_metrics['mae']:.2f} 元")
    if test_metrics["r2"] > 0.7:
        print("\n[提示] 测试集指标供论文引用；若与旧版偏高差异大，属泄漏消除后的正常变化。")


if __name__ == "__main__":
    main()
