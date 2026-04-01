# -*- coding: utf-8 -*-
"""
在「与 train_model_mysql 相同」的划分与预处理下，用磁盘上的 XGBoost 对比真实挂牌价与预测价。

默认：在**留出测试集**上算整体指标，并分层抽样展示（与论文泛化评价一致）。
可选：`--split train` 仅从训练子集随机抽（模型见过，误差偏乐观，仅供对照）。

用法（在 Tujia-backend 根目录）:
  python scripts/sample_prediction_compare.py
  python scripts/sample_prediction_compare.py -n 30 --seed 7
  python scripts/sample_prediction_compare.py --split train
"""
from __future__ import annotations

import argparse
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


def _build_ev(
    split_df: pd.DataFrame, feature_cols: list, model
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    X = split_df[feature_cols]
    y_true = split_df["price"].astype(float).values
    y_pred = np.expm1(model.predict(X))
    ev = split_df[["unit_id", "district", "trade_area", "area", "bedroom_count", "price"]].copy()
    ev = ev.reset_index(drop=True)
    ev["y_true"] = y_true
    ev["y_pred"] = np.round(y_pred, 2)
    ev["err"] = np.round(ev["y_pred"] - ev["y_true"], 2)
    ev["ape_pct"] = np.round(np.abs(ev["err"]) / ev["y_true"] * 100, 2)
    return ev, y_true, y_pred


def main() -> None:
    parser = argparse.ArgumentParser(description="XGBoost 真实数据预测对比")
    parser.add_argument(
        "--split",
        choices=("train", "test"),
        default="test",
        help="test=留出测试集整体指标+分层抽样（默认）；train=仅从训练子集随机抽",
    )
    parser.add_argument(
        "-n",
        "--n-samples",
        type=int,
        default=20,
        help="随机展示条数（split=train 时从训练集抽；split=test 时为分层抽样每档上限合计约 8 条）",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    df = _tm.load_data_from_mysql()
    df = df[(df["price"] >= 50) & (df["price"] <= 5000)].copy()
    df["price_log"] = np.log1p(df["price"])
    df["price_bucket"] = df["price"].apply(_tm.price_bucket)
    train_df, test_df = _tm.stratified_holdout(df)
    train_df, test_df, _, _, feature_cols, _, _ = _tm.preprocess_after_split(train_df, test_df)

    model = joblib.load(MODELS / "xgboost_price_model_latest.pkl")

    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 28)
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

    if args.split == "train":
        n = min(max(1, args.n_samples), len(train_df))
        sampled = train_df.sample(n=n, random_state=args.seed).copy()
        ev_s, y_t, y_p = _build_ev(sampled, feature_cols, model)

        print("=" * 72)
        print(f"训练子集随机抽样 n={n}（不含留出测试集；模型训练时见过该子集，误差倾向偏乐观）")
        print("=" * 72)
        mae = mean_absolute_error(y_t, y_p)
        rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
        r2 = r2_score(y_t, y_p)
        mape = float(np.mean(np.abs((y_t - y_p) / y_t)) * 100)
        print(f"  本批样本 MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.4f}  MAPE={mape:.2f}%")
        print(f"  训练子集总条数={len(train_df)}  测试子集条数={len(test_df)}（本表未使用）")
        print("\n" + "=" * 72)
        print("抽样明细（unit_id / final_price vs 预测）")
        print("=" * 72)
        print(ev_s[cols].to_string(index=False))
        return

    # --split test
    ev, y_true, y_pred = _build_ev(test_df, feature_cols, model)

    print("=" * 72)
    print("测试集整体（与训练脚本留出评估一致）")
    print("=" * 72)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    print(f"  MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.4f}  MAPE={mape:.2f}%")
    print(f"  测试样本数 n={len(ev)}")

    k = max(2, args.n_samples // 3)

    def pick_band(lo: float, hi: float, kk: int, seed: int) -> pd.DataFrame:
        sub = ev[(ev["y_true"] >= lo) & (ev["y_true"] < hi)]
        if sub.empty:
            return sub
        return sub.sample(n=min(kk, len(sub)), random_state=seed)

    samples = pd.concat(
        [
            pick_band(50, 100, k, args.seed),
            pick_band(100, 300, k, args.seed + 1),
            pick_band(300, 1e9, k, args.seed + 2),
        ],
        ignore_index=True,
    )

    print("\n" + "=" * 72)
    print("测试集分层抽样（unit_id / 挂牌价 vs 预测）")
    print("=" * 72)
    print(samples[cols].to_string(index=False))


if __name__ == "__main__":
    main()
