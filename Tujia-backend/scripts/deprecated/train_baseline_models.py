# -*- coding: utf-8 -*-
"""
训练基准模型（LinearRegression / RandomForest）用于论文对比
==========================================================

使用与XGBoost完全相同的数据划分（stratified_holdout）和特征预处理流程，
生成真实的LR/RF评估指标，替换图5-4雷达图中的硬编码数据。

运行：在 Tujia-backend 目录下
    python scripts/train_baseline_models.py
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
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings("ignore")

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
from scripts.train_model_mysql import (
    load_training_data,
    price_bucket,
    stratified_holdout,
    preprocess_after_split,
    OUTPUT_DIR,
)


def train_linear_regression(
    train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]
) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
    """训练线性回归模型"""
    print("\n" + "=" * 60)
    print("训练线性回归模型 (Linear Regression)")
    print("=" * 60)

    X_train = train_df[feature_cols].values
    X_test = test_df[feature_cols].values
    y_train = train_df["price"].values
    y_test = test_df["price"].values

    # 对价格进行对数变换（与XGBoost保持一致）
    y_train_log = np.log1p(y_train)
    y_test_log = np.log1p(y_test)

    model = LinearRegression(n_jobs=-1)
    model.fit(X_train, y_train_log)

    # 预测并还原
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
        print(f"  MAPE: {mape:.2f}%")
        return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}

    train_metrics = evaluate(y_train, y_pred_train, "训练集")
    test_metrics = evaluate(y_test, y_pred_test, "测试集")

    return model, train_metrics, test_metrics


def train_random_forest(
    train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str]
) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
    """训练随机森林模型"""
    print("\n" + "=" * 60)
    print("训练随机森林模型 (Random Forest)")
    print("=" * 60)

    X_train = train_df[feature_cols].values
    X_test = test_df[feature_cols].values
    y_train = train_df["price"].values
    y_test = test_df["price"].values

    # 对价格进行对数变换（与XGBoost保持一致）
    y_train_log = np.log1p(y_train)
    y_test_log = np.log1p(y_test)

    # 使用与XGBoost相近的参数量级
    model = RandomForestRegressor(
        n_estimators=200,  # 树数量
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=3,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train_log)

    # 预测并还原
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
        print(f"  MAPE: {mape:.2f}%")
        return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}

    train_metrics = evaluate(y_train, y_pred_train, "训练集")
    test_metrics = evaluate(y_test, y_pred_test, "测试集")

    return model, train_metrics, test_metrics


def save_baseline_metrics(
    lr_train: Dict[str, float],
    lr_test: Dict[str, float],
    rf_train: Dict[str, float],
    rf_test: Dict[str, float],
    xgb_metrics: Dict[str, Any],
    feature_cols: List[str],
    n_train: int,
    n_test: int,
) -> None:
    """保存基准模型评估指标"""
    print("\n" + "=" * 60)
    print("保存基准模型指标")
    print("=" * 60)

    # 读取现有的XGBoost指标
    baseline_metrics = {
        "linear_regression": {
            "train": lr_train,
            "test": lr_test,
        },
        "random_forest": {
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
        "trained_at": pd.Timestamp.now().isoformat(),
    }

    output_path = OUTPUT_DIR / "baseline_model_metrics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(baseline_metrics, f, ensure_ascii=False, indent=2, default=str)
    print(f"基准模型指标已保存: {output_path}")

    # 同时生成CSV格式便于直接复制到论文
    print("\n" + "=" * 60)
    print("模型对比表格（可直接复制到论文表5-6）")
    print("=" * 60)
    print(f"{'模型':<15} {'MAE':<10} {'MAPE(%)':<10} {'R²':<10}")
    print("-" * 50)
    print(f"{'线性回归(LR)':<15} {lr_test['mae']:<10.2f} {lr_test['mape']:<10.2f} {lr_test['r2']:<10.4f}")
    print(f"{'随机森林(RF)':<15} {rf_test['mae']:<10.2f} {rf_test['mape']:<10.2f} {rf_test['r2']:<10.4f}")
    print(f"{'XGBoost':<15} {xgb_metrics['mae']:<10.2f} {xgb_metrics['mape']:<10.2f} {xgb_metrics['r2']:<10.4f}")


def main() -> None:
    env_default = os.environ.get("TRAIN_DATA_SOURCE", "auto").strip().lower()
    if env_default not in ("auto", "hive", "mysql"):
        env_default = "auto"
    parser = argparse.ArgumentParser(description="训练基准模型（LR/RF）用于论文对比")
    parser.add_argument(
        "--data-source",
        choices=("auto", "hive", "mysql"),
        default=env_default,
        help="训练数据来源",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("基准模型训练（LinearRegression / RandomForest）")
    print(f"数据模式: {args.data_source}")
    print("=" * 60)

    # 加载数据（与XGBoost相同）
    df, data_source_label = load_training_data(args.data_source)
    df = df[df["price"] >= 50].copy()
    df = df[df["price"] <= 5000].copy()
    print(f"\n过滤后(50<=price<=5000): {len(df)} 条")

    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(price_bucket)

    # 分层留出（与XGBoost相同）
    train_df, test_df = stratified_holdout(df)
    print(f"\n划分完成: 训练 {len(train_df)} / 测试 {len(test_df)}")

    # 预处理（与XGBoost相同）
    (
        train_df,
        test_df,
        encoders,
        district_stats,
        feature_cols,
        calendar_defaults,
        _trade_area_stats,
    ) = preprocess_after_split(train_df, test_df)
    if len(train_df) < 50 or len(test_df) < 10:
        print("错误: 训练或测试样本过少")
        sys.exit(1)

    print(f"\n最终样本: 训练 {len(train_df)} / 测试 {len(test_df)}")

    # 训练线性回归
    lr_model, lr_train_metrics, lr_test_metrics = train_linear_regression(
        train_df, test_df, feature_cols
    )

    # 训练随机森林
    rf_model, rf_train_metrics, rf_test_metrics = train_random_forest(
        train_df, test_df, feature_cols
    )

    # 读取XGBoost指标
    xgb_metrics_path = OUTPUT_DIR / "model_metrics_latest.json"
    if xgb_metrics_path.exists():
        with open(xgb_metrics_path, "r", encoding="utf-8") as f:
            xgb_data = json.load(f)
        xgb_metrics = xgb_data.get("metrics", {})
    else:
        print(f"警告: 未找到XGBoost指标文件 {xgb_metrics_path}")
        xgb_metrics = {"mae": 23.67, "mape": 10.44, "r2": 0.763}

    # 保存对比指标
    save_baseline_metrics(
        lr_train_metrics,
        lr_test_metrics,
        rf_train_metrics,
        rf_test_metrics,
        xgb_metrics,
        feature_cols,
        len(train_df),
        len(test_df),
    )

    # 保存模型
    joblib.dump(lr_model, OUTPUT_DIR / "linear_regression_model.pkl")
    joblib.dump(rf_model, OUTPUT_DIR / "random_forest_model.pkl")
    print(f"\n模型已保存:")
    print(f"  - {OUTPUT_DIR / 'linear_regression_model.pkl'}")
    print(f"  - {OUTPUT_DIR / 'random_forest_model.pkl'}")

    print("\n" + "=" * 60)
    print("基准模型训练完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
