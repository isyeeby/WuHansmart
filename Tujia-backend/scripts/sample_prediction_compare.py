# -*- coding: utf-8 -*-
"""
在「与 train_model_mysql 相同」的划分与预处理下，从测试集抽取真实样本对比 y 与 XGBoost 预测。
用法（在 Tujia-backend 根目录）: python scripts/sample_prediction_compare.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "train_model_mysql", ROOT / "scripts" / "train_model_mysql.py"
)
_tm = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_tm)

MODELS = ROOT / "models"


def main() -> None:
    df = _tm.load_data_from_mysql()
    df = df[(df["price"] >= 50) & (df["price"] <= 5000)].copy()
    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(_tm.price_bucket)
    train_df, test_df = _tm.stratified_holdout(df)
    train_df, test_df, _, _, feature_cols, _ = _tm.preprocess_after_split(train_df, test_df)

    model = joblib.load(MODELS / "xgboost_price_model_latest.pkl")
    X_te = test_df[feature_cols]
    y_true = test_df["price"].astype(float).values
    y_pred = np.expm1(model.predict(X_te))

    ev = test_df[["unit_id", "district", "trade_area", "area", "bedroom_count", "price"]].copy()
    ev = ev.reset_index(drop=True)
    ev["y_true"] = y_true
    ev["y_pred"] = np.round(y_pred, 2)
    ev["err"] = np.round(ev["y_pred"] - ev["y_true"], 2)
    ev["ape_pct"] = np.round(np.abs(ev["err"]) / ev["y_true"] * 100, 2)

    print("=" * 72)
    print("测试集整体（与训练脚本评估一致）")
    print("=" * 72)
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    print(f"  MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.4f}  MAPE={mape:.2f}%")
    print(f"  测试样本数 n={len(ev)}")

    def pick_band(lo: float, hi: float, k: int, seed: int = 42) -> pd.DataFrame:
        sub = ev[(ev["y_true"] >= lo) & (ev["y_true"] < hi)]
        if sub.empty:
            return sub
        return sub.sample(n=min(k, len(sub)), random_state=seed)

    samples = pd.concat(
        [
            pick_band(50, 100, 2),
            pick_band(100, 300, 3),
            pick_band(300, 1e9, 3),
        ],
        ignore_index=True,
    )

    print("\n" + "=" * 72)
    print("真实测试集抽样（unit_id / 挂牌价 final_price vs 模型预测）")
    print("=" * 72)
    cols = [
        "unit_id",
        "district",
        "area",
        "bedroom_count",
        "y_true",
        "y_pred",
        "err",
        "ape_pct",
    ]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 28)
    print(samples[cols].to_string(index=False))


if __name__ == "__main__":
    main()
