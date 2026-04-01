# -*- coding: utf-8 -*-
"""
房源级 XGBoost 离线验证：仅用数据库中的房源基础信息 + 设施（与线上一致），**不把房价作为模型输入**；
用 listings.final_price 仅作对照标签，计算 MAE / RMSE / R² / MAPE。

与训练主评估口径一致：日历维为冷启动（calendar_feature_defaults.json），不查 price_calendars。

运行（在 Tujia-backend 目录下）：
  python scripts/eval_listing_model_mysql.py
  python scripts/eval_listing_model_mysql.py --limit 500
  python scripts/eval_listing_model_mysql.py --min-price 50 --max-price 5000
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import warnings
from typing import List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Listing, SessionLocal
from app.services.listing_price_bridge import listing_to_prediction_request
from app.services.model_manager import model_manager
from app.services.price_predictor import PricePredictionModel


def _features_from_request(model: PricePredictionModel, request) -> dict:
    """与 PricePredictionModel.predict 内构造一致，供直接调用 ModelManager。"""
    rating_raw = getattr(request, "rating", None)
    favorite_raw = getattr(request, "favorite_count", None)
    return {
        "district": request.district,
        "trade_area": getattr(request, "trade_area", None) or request.district,
        "rating": float(rating_raw) if rating_raw is not None else None,
        "has_rating_ob": 0 if rating_raw is None else 1,
        "bedroom_count": request.bedrooms,
        "bed_count": getattr(request, "bed_count", request.bedrooms) or request.bedrooms,
        "area": getattr(request, "area", 50) or 50,
        "capacity": request.capacity,
        "favorite_count": int(favorite_raw) if favorite_raw is not None else None,
        "has_favorite_ob": 0 if favorite_raw is None else 1,
        "latitude": getattr(request, "latitude", 30.5) or 30.5,
        "longitude": getattr(request, "longitude", 114.3) or 114.3,
        "house_type": getattr(request, "room_type", "整套"),
        "has_heater": bool(getattr(request, "has_heater", False)),
        "near_subway": 1 if getattr(request, "near_metro", False) else 0,
        "near_station": 1 if getattr(request, "near_station", False) else 0,
        "near_university": 1 if getattr(request, "near_university", False) else 0,
        "projector": 1 if getattr(request, "has_projector", False) else 0,
        "washer": 1 if getattr(request, "has_washer", False) else 0,
        "bathtub": 1 if getattr(request, "has_bathtub", False) else 0,
        "smart_lock": 1 if getattr(request, "has_smart_lock", False) else 0,
        "ac": 1 if getattr(request, "has_air_conditioning", True) else 0,
        "kitchen": 1 if getattr(request, "has_kitchen", False) else 0,
        "fridge": 1 if getattr(request, "has_fridge", False) else 0,
        "terrace": 1 if getattr(request, "has_terrace", False) else 0,
        "elevator": 1 if getattr(request, "has_elevator", False) else 0,
        "mahjong": 1 if getattr(request, "has_mahjong", False) else 0,
        "pet_friendly": 1 if getattr(request, "pet_friendly", False) else 0,
        "has_view": 1 if getattr(request, "has_view", False) else 0,
        "view_type": getattr(request, "view_type", None),
        "river_view": 1
        if (getattr(request, "has_view", False) and "江景" in str(getattr(request, "view_type", "")))
        else 0,
        "lake_view": 1
        if (getattr(request, "has_view", False) and "湖景" in str(getattr(request, "view_type", "")))
        else 0,
        "near_ski": 0,
        "mountain_view": 1
        if (getattr(request, "has_view", False) and "山景" in str(getattr(request, "view_type", "")))
        else 0,
        "sunroom": 0,
        "garden": 0,
        "city_view": 0,
        "big_projector": 1 if getattr(request, "has_projector", False) else 0,
        "view_bathtub": 0,
        "karaoke": 0,
        "oven": 0,
        "dry_wet_sep": 0,
        "smart_toilet": 0,
        "free_parking": 1 if getattr(request, "has_parking", False) else 0,
        "paid_parking": 0,
        "free_water": 0,
        "front_desk": 0,
        "butler": 0,
        "luggage": 0,
        "style_modern": 0,
        "style_ins": 0,
        "style_western": 0,
        "style_chinese": 0,
        "style_japanese": 0,
        "real_photo": 0,
        "instant_confirm": 0,
        "family_friendly": 0,
        "business": 0,
    }


def load_listings(limit: int = 0) -> List[Listing]:
    db = SessionLocal()
    try:
        q = (
            db.query(Listing)
            .filter(
                Listing.final_price.isnot(None),
                Listing.final_price > 0,
                Listing.rating.isnot(None),
                Listing.area.isnot(None),
                Listing.district.isnot(None),
            )
            .order_by(Listing.unit_id)
        )
        if limit and limit > 0:
            q = q.limit(limit)
        return q.all()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="房源级模型 MySQL 离线验证（房价不作输入）")
    parser.add_argument("--limit", type=int, default=0, help="最多评估条数，0 表示全部")
    parser.add_argument("--min-price", type=float, default=50.0)
    parser.add_argument("--max-price", type=float, default=5000.0)
    parser.add_argument(
        "--skip-dummy",
        action="store_true",
        help="若 XGBoost 未加载则跳过样本（默认仍用 predict 含启发式兜底）",
    )
    args = parser.parse_args()

    if model_manager.price_model is None:
        print("警告: xgboost_price_model_latest.pkl 未加载，预测将走启发式兜底。")

    listings = load_listings(args.limit)
    print(f"从 MySQL 读取候选房源: {len(listings)} 条")

    model_svc = PricePredictionModel()
    y_true: List[float] = []
    y_pred: List[float] = []
    skipped = 0

    for l in listings:
        price = float(l.final_price)
        if price < args.min_price or price > args.max_price:
            skipped += 1
            continue
        try:
            req = listing_to_prediction_request(l)
        except Exception:
            skipped += 1
            continue
        feats = _features_from_request(model_svc, req)
        if args.skip_dummy and model_manager.price_model is None:
            continue
        pred = model_manager.predict_price(feats)
        if pred is None:
            skipped += 1
            continue
        y_true.append(price)
        y_pred.append(float(pred))

    if len(y_true) < 10:
        print(f"有效样本不足（{len(y_true)}），请放宽过滤或检查数据库。")
        sys.exit(1)

    yt = np.array(y_true, dtype=np.float64)
    yp = np.array(y_pred, dtype=np.float64)
    mae = mean_absolute_error(yt, yp)
    rmse = float(np.sqrt(mean_squared_error(yt, yp)))
    r2 = r2_score(yt, yp)
    mape = float(np.mean(np.abs((yt - yp) / np.maximum(yt, 1e-6))) * 100)

    print("\n" + "=" * 60)
    print("房源级 XGBoost（冷日历）离线验证")
    print("=" * 60)
    print(f"说明: 模型输入不含 final_price；仅用房态、区县、设施、评分等。")
    print(f"有效样本: {len(y_true)} | 因价格区间跳过: {skipped}")
    print(f"价格过滤: [{args.min_price}, {args.max_price}]")
    print(f"\nMAE:  {mae:.2f} 元")
    print(f"RMSE: {rmse:.2f} 元")
    print(f"R²:   {r2:.4f}")
    print(f"MAPE: {mape:.1f}%")

    df = pd.DataFrame({"true": yt, "pred": yp})
    print("\n分桶（真实价）:")
    for low, high, lab in [(50, 100, "低价 50-100"), (100, 300, "中价 100-300"), (300, 5000, "高价 >300")]:
        sub = df[(df["true"] >= low) & (df["true"] < high)]
        if len(sub) > 0:
            m = mean_absolute_error(sub["true"], sub["pred"])
            mp = float(np.mean(np.abs((sub["true"] - sub["pred"]) / sub["true"])) * 100)
            print(f"  {lab}: n={len(sub)}, MAE={m:.1f}, MAPE={mp:.1f}%")

    print("\n示例（前 5 条）: 真实价 -> 预测价")
    for i in range(min(5, len(y_true))):
        print(f"  {y_true[i]:.0f} -> {y_pred[i]:.0f}")


if __name__ == "__main__":
    main()
