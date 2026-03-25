# -*- coding: utf-8 -*-
"""从 MySQL Listing ORM 构造定价预测请求，与 XGBoost 推理特征对齐。"""
from __future__ import annotations

import json
import logging
from typing import Any, List

from app.db.database import Listing
from app.models.schemas import PredictionRequest

logger = logging.getLogger(__name__)


def _extract_tag_texts(house_tags: Any) -> List[str]:
    texts: List[str] = []
    if not house_tags:
        return texts
    if not isinstance(house_tags, str):
        return texts
    try:
        data = json.loads(house_tags)
    except (json.JSONDecodeError, TypeError):
        return [house_tags]
    if not isinstance(data, list):
        return texts
    for item in data:
        if isinstance(item, dict):
            if "text" in item and isinstance(item["text"], str):
                texts.append(item["text"])
            elif "tagText" in item and isinstance(item["tagText"], dict):
                t = item["tagText"].get("text")
                if isinstance(t, str):
                    texts.append(t)
        elif isinstance(item, str):
            texts.append(item)
    return texts


def listing_to_prediction_request(listing: Listing) -> PredictionRequest:
    """
    将 listings 表记录转为 PredictionRequest，并携带 unit_id 以加载日历特征。
    标签解析为启发式设施布尔值（与训练侧 parse 口径尽力一致）。
    """
    texts = _extract_tag_texts(listing.house_tags)
    blob = " ".join(texts)

    has_projector = any(k in blob for k in ("有投影", "巨幕投影", "投影"))
    has_washer = "洗衣机" in blob or "有洗衣机" in blob
    has_bathtub = "浴缸" in blob
    has_smart_lock = "智能门锁" in blob or "智能锁" in blob
    has_kitchen = "厨房" in blob or "可做饭" in blob
    near_metro = "近地铁" in blob or "地铁" in blob
    has_fridge = "冰箱" in blob
    has_terrace = "观景露台" in blob or "露台" in blob
    has_mahjong = "麻将" in blob
    has_elevator = "电梯" in blob
    has_parking = "停车" in blob
    has_view = any(k in blob for k in ("江景", "湖景", "山景"))
    view_type = None
    if "江景" in blob:
        view_type = "江景"
    elif "湖景" in blob:
        view_type = "湖景"

    ht = (listing.house_type or "").strip()
    if "单间" in ht or "独立" in ht or "合租" in ht:
        room_type = "独立房间"
    elif "床位" in ht or "青旅" in ht:
        room_type = "合住房间"
    else:
        room_type = "整套房屋"

    bd = listing.bedroom_count
    if bd is None:
        bd = 1
    bc = listing.bed_count if listing.bed_count is not None else max(1, bd)
    cap = listing.capacity if listing.capacity is not None else max(2, bc * 2)
    cap = max(1, min(20, int(cap)))

    try:
        area_f = float(listing.area) if listing.area is not None else 50.0
    except (TypeError, ValueError):
        area_f = 50.0
    area_i = int(max(10, min(500, round(area_f))))

    rating = float(listing.rating) if listing.rating is not None else None
    fav = int(listing.favorite_count) if listing.favorite_count is not None else None
    lat = float(listing.latitude) if listing.latitude is not None else None
    lng = float(listing.longitude) if listing.longitude is not None else None

    return PredictionRequest(
        district=listing.district or "未知",
        trade_area=listing.trade_area or listing.district or None,
        unit_id=listing.unit_id,
        room_type=room_type,
        capacity=cap,
        bedrooms=int(bd),
        bed_count=max(1, int(bc)),
        bathrooms=1,
        area=area_i,
        has_wifi=True,
        has_kitchen=has_kitchen,
        has_air_conditioning=True,
        has_projector=has_projector,
        has_bathtub=has_bathtub,
        has_washer=has_washer,
        has_smart_lock=has_smart_lock,
        has_tv=True,
        has_heater=False,
        near_metro=near_metro,
        has_elevator=has_elevator,
        has_fridge=has_fridge,
        has_view=bool(has_view),
        view_type=view_type,
        has_terrace=has_terrace,
        has_mahjong=has_mahjong,
        has_big_living_room=False,
        has_parking=has_parking,
        rating=rating,
        favorite_count=fav,
        latitude=lat,
        longitude=lng,
    )
