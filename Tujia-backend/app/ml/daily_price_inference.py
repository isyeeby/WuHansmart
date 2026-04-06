# -*- coding: utf-8 -*-
"""
日级 XGBoost 推理：从房源静态字段 + 目标日期 + 预测 horizon（未来第几天）构造与训练一致的特征行。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.ml.daily_calendar_features import add_daily_date_features, add_holiday_proximity_features
from app.ml.price_feature_config import compute_is_budget_structural, ordered_facility_columns
from app.models.schemas import PredictionRequest

_FACILITY_ORDERED = ordered_facility_columns()


def _facility_mapping_from_features(features: Dict[str, Any]) -> Dict[str, int]:
    """设施字段 → 训练用二值列，与训练脚本特征构造一致。"""
    hot_water_v = (
        int(bool(features.get("hot_water")))
        if features.get("hot_water") is not None
        else (1 if features.get("has_heater") else 0)
    )
    return {
        "near_subway": int(bool(features.get("near_metro") or features.get("near_subway"))),
        "near_station": int(bool(features.get("near_station"))),
        "near_university": int(bool(features.get("near_university"))),
        "near_ski": int(bool(features.get("near_ski"))),
        "river_view": 1
        if (features.get("has_view") and "江景" in str(features.get("view_type", "")))
        else int(features.get("river_view", 0)),
        "lake_view": 1
        if (features.get("has_view") and "湖景" in str(features.get("view_type", "")))
        else int(features.get("lake_view", 0)),
        "mountain_view": 1
        if (features.get("has_view") and "山景" in str(features.get("view_type", "")))
        else int(features.get("mountain_view", 0)),
        "terrace": int(bool(features.get("has_terrace") or features.get("terrace"))),
        "sunroom": int(features.get("sunroom", 0)),
        "garden": int(features.get("garden", 0)),
        "city_view": int(features.get("city_view", 0)),
        "projector": int(bool(features.get("has_projector") or features.get("projector"))),
        "big_projector": int(features.get("big_projector", 0)),
        "washer": int(bool(features.get("has_washer") or features.get("washer"))),
        "bathtub": int(bool(features.get("has_bathtub") or features.get("bathtub"))),
        "view_bathtub": int(features.get("view_bathtub", 0)),
        "karaoke": int(features.get("karaoke", 0)),
        "mahjong": int(bool(features.get("has_mahjong") or features.get("mahjong"))),
        "big_living_room": int(bool(features.get("big_living_room") or features.get("has_big_living_room"))),
        "kitchen": int(bool(features.get("has_kitchen") or features.get("kitchen"))),
        "fridge": int(bool(features.get("has_fridge") or features.get("fridge"))),
        "oven": int(features.get("oven", 0)),
        "dry_wet_sep": int(features.get("dry_wet_sep", 0)),
        "smart_lock": int(bool(features.get("has_smart_lock") or features.get("smart_lock"))),
        "smart_toilet": int(features.get("smart_toilet", 0)),
        "ac": int(bool(features.get("has_air_conditioning", 1) or features.get("ac", 1))),
        "hot_water": hot_water_v,
        "elevator": int(bool(features.get("has_elevator") or features.get("elevator"))),
        "pet_friendly": int(bool(features.get("pet_friendly"))),
        "free_parking": int(bool(features.get("has_parking") or features.get("free_parking"))),
        "paid_parking": int(features.get("paid_parking", 0)),
        "free_water": int(features.get("free_water", 0)),
        "front_desk": int(features.get("front_desk", 0)),
        "butler": int(features.get("butler", 0)),
        "luggage": int(features.get("luggage", 0)),
        "style_modern": int(features.get("style_modern", 0)),
        "style_ins": int(features.get("style_ins", 0)),
        "style_western": int(features.get("style_western", 0)),
        "style_chinese": int(features.get("style_chinese", 0)),
        "style_japanese": int(features.get("style_japanese", 0)),
        "real_photo": int(features.get("real_photo", 0)),
        "instant_confirm": int(features.get("instant_confirm", 0)),
        "family_friendly": int(features.get("family_friendly", 0)),
        "business": int(features.get("business", 0)),
    }


def prediction_request_to_features_dict(req: PredictionRequest) -> Dict[str, Any]:
    """PredictionRequest -> 与 ModelManager 一致的 features 字典（日级推理用）。"""
    return {
        "district": req.district,
        "trade_area": req.trade_area or req.district,
        "rating": req.rating,
        "has_rating_ob": 0 if req.rating is None else 1,
        "bedroom_count": req.bedrooms,
        "bed_count": req.bed_count or req.bedrooms,
        "area": float(req.area or 50),
        "capacity": req.capacity,
        "favorite_count": req.favorite_count,
        "has_favorite_ob": 0 if req.favorite_count is None else 1,
        "latitude": req.latitude if req.latitude is not None else 30.5,
        "longitude": req.longitude if req.longitude is not None else 114.3,
        "house_type": str(req.room_type or "整套"),
        "has_heater": bool(req.has_heater),
        "near_metro": req.near_metro,
        "near_station": req.near_station,
        "near_university": req.near_university,
        "near_ski": req.near_ski,
        "has_projector": req.has_projector,
        "has_washer": req.has_washer,
        "has_bathtub": req.has_bathtub,
        "has_smart_lock": req.has_smart_lock,
        "has_air_conditioning": req.has_air_conditioning,
        "has_kitchen": req.has_kitchen,
        "has_fridge": req.has_fridge,
        "has_terrace": req.has_terrace,
        "has_elevator": req.has_elevator,
        "has_mahjong": req.has_mahjong,
        "big_living_room": req.has_big_living_room,
        "has_view": req.has_view,
        "view_type": req.view_type,
        "garden": req.garden,
        "has_parking": req.has_parking,
        "pet_friendly": req.pet_friendly,
        "can_booking": 1.0,
    }


def _district_ta_encoding(
    district: str,
    trade_area: str,
    house_type: str,
    district_encoder: Dict[str, int],
    trade_area_encoder: Dict[str, int],
    house_type_encoder: Dict[str, int],
    district_stats: Dict[str, Dict[str, float]],
    ta_stats: Dict[str, Dict[str, float]],
) -> Tuple[int, int, int, Dict[str, float]]:
    d_enc = int(district_encoder.get(district, 0)) if district_encoder else 0
    ta_enc = int(trade_area_encoder.get(trade_area, 0)) if trade_area_encoder else d_enc
    ht_enc = int(house_type_encoder.get(house_type, 0)) if house_type_encoder else 0
    ds = district_stats.get(district) if district_stats else None
    if ds:
        dist_mean = float(ds.get("dist_mean", 200))
        dist_median = float(ds.get("dist_median", 165))
        dist_std = float(ds.get("dist_std", 100))
        dist_count = float(ds.get("dist_count", 10))
    else:
        dist_mean, dist_median, dist_std, dist_count = 200.0, 165.0, 100.0, 10.0
    tas = ta_stats.get(trade_area) if ta_stats else None
    if tas:
        ta_mean = float(tas.get("ta_mean", dist_mean))
        ta_median = float(tas.get("ta_median", dist_median))
        ta_std = float(tas.get("ta_std", dist_std))
        ta_count = float(tas.get("ta_count", dist_count))
    else:
        ta_mean, ta_median, ta_std, ta_count = dist_mean, dist_median, dist_std, dist_count
    dist_cols = {
        "dist_mean": dist_mean,
        "dist_median": dist_median,
        "dist_std": dist_std,
        "dist_count": dist_count,
        "ta_mean": ta_mean,
        "ta_median": ta_median,
        "ta_std": ta_std,
        "ta_count": ta_count,
    }
    return d_enc, ta_enc, ht_enc, dist_cols


def build_daily_inference_dataframe(
    features: Dict[str, Any],
    anchor_dates: List[date],
    horizon_offsets: List[int],
    feature_names: List[str],
    district_encoder: Dict[str, int],
    trade_area_encoder: Dict[str, int],
    house_type_encoder: Dict[str, int],
    district_stats: Dict[str, Dict[str, float]],
    ta_stats: Dict[str, Dict[str, float]],
    lag_defaults: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    构造多行日级特征矩阵。anchor_dates[i] 为第 i 行目标日；horizon_offsets[i] 为「未来第几天」(通常 0..13)。
    """
    if len(anchor_dates) != len(horizon_offsets):
        raise ValueError("anchor_dates 与 horizon_offsets 长度须一致")
    lag_defaults = lag_defaults or {}

    district = str(features.get("district") or "")
    trade_area = str(features.get("trade_area") or district)
    house_type = str(features.get("house_type") or "整套")
    area = float(features.get("area", 50))
    bedroom_count = int(features.get("bedroom_count", 1))
    bed_count = int(features.get("bed_count", bedroom_count))
    capacity = int(features.get("capacity", bedroom_count * 2))

    r_med = 4.85
    if features.get("has_rating_ob") == 0 or features.get("rating") is None:
        rating = r_med
    else:
        rating = float(features.get("rating") or r_med)
    if features.get("has_favorite_ob") == 0 or features.get("favorite_count") is None:
        favorite_count = 0
    else:
        favorite_count = int(features.get("favorite_count") or 0)

    lat = float(features.get("latitude", 30.5))
    lon = float(features.get("longitude", 114.3))
    can_booking = float(features.get("can_booking", 1.0))

    d_enc, ta_enc, ht_enc, dist_cols = _district_ta_encoding(
        district,
        trade_area,
        house_type,
        district_encoder,
        trade_area_encoder,
        house_type_encoder,
        district_stats,
        ta_stats,
    )
    fac_map = _facility_mapping_from_features(features)
    facility_count = sum(int(fac_map.get(c, 0) or 0) for c in _FACILITY_ORDERED)
    is_large = 1 if (bedroom_count >= 4 or area >= 150) else 0
    is_budget = int(compute_is_budget_structural(area, bedroom_count))
    area_per_bedroom = area / (bedroom_count + 1)
    heat_score = float(favorite_count) * float(rating) / 10.0

    static_base: Dict[str, Any] = {
        "rating": rating,
        "area": area,
        "bedroom_count": bedroom_count,
        "bed_count": bed_count,
        "capacity": capacity,
        "favorite_count": favorite_count,
        "latitude": lat,
        "longitude": lon,
        "is_large": is_large,
        "is_budget": is_budget,
        "can_booking": can_booking,
        "district_encoded": d_enc,
        "trade_area_encoded": ta_enc,
        "house_type_encoded": ht_enc,
        "area_per_bedroom": area_per_bedroom,
        "heat_score": heat_score,
        "facility_count": facility_count,
        **dist_cols,
        **fac_map,
    }

    cal_df = pd.DataFrame({"calendar_date": pd.to_datetime(anchor_dates)})
    cal_df = add_daily_date_features(cal_df, "calendar_date")
    cal_df = add_holiday_proximity_features(cal_df, "calendar_date", max_span=60)
    cal_df["cal_offset_days"] = [float(h) for h in horizon_offsets]

    cal_cols = [c for c in cal_df.columns if c != "calendar_date"]
    rows: List[Dict[str, Any]] = []
    for i in range(len(anchor_dates)):
        row = dict(static_base)
        for c in cal_cols:
            v = cal_df.iloc[i][c]
            row[c] = float(v) if pd.notna(v) else 0.0
        rows.append(row)

    out = pd.DataFrame(rows)
    for name in feature_names:
        if name not in out.columns:
            out[name] = float(lag_defaults.get(name, 0.0))
    out = out[feature_names]
    return out.fillna(0.0).replace([np.inf, -np.inf], 0.0)


def load_district_stats_daily(path: str) -> Dict[str, Dict[str, float]]:
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Dict[str, float]] = {}
    for item in data:
        d = str(item.get("district", ""))
        if d:
            out[d] = {k: float(v) for k, v in item.items() if k != "district"}
    return out


def load_trade_area_stats_daily(path: str) -> Dict[str, Dict[str, float]]:
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Dict[str, float]] = {}
    for item in data:
        key = str(item.get("trade_area", ""))
        if key:
            out[key] = {k: float(v) for k, v in item.items() if k != "trade_area"}
    return out
