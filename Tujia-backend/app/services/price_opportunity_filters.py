# -*- coding: utf-8 -*-
"""
价格洼地候选过滤：床位/青旅等与 XGBoost 整套民宿定价模型不可比，且极低价会导致价差率失真。
与 hive_service MySQL 兜底路径共用同一口径。
"""
from __future__ import annotations

from typing import Any

# 元/晚，与 _mysql_get_price_opportunities 一致
MIN_OPPORTUNITY_PRICE = 80.0
MAX_OPPORTUNITY_PRICE = 500.0

SHARED_LODGING_KEYWORDS = (
    "青旅",
    "青年旅舍",
    "青年旅社",
    "床位",
    "床铺",
    "多人间",
    "胶囊",
    "上下铺",
    "太空舱",
)


def _listing_text_blob(listing: Any) -> str:
    parts = [
        getattr(listing, "title", None) or "",
        getattr(listing, "house_type", None) or "",
        getattr(listing, "house_tags", None) or "",
    ]
    return " ".join(parts)


def is_eligible_price_opportunity_listing(listing: Any) -> bool:
    """是否参与价格洼地：价格带 + 排除共享住宿类标题/类型/标签。"""
    try:
        p = float(getattr(listing, "final_price", None) or 0)
    except (TypeError, ValueError):
        return False
    if p < MIN_OPPORTUNITY_PRICE or p > MAX_OPPORTUNITY_PRICE:
        return False
    blob = _listing_text_blob(listing)
    if any(kw in blob for kw in SHARED_LODGING_KEYWORDS):
        return False
    ht = getattr(listing, "house_type", None) or ""
    if any(x in ht for x in ("合住房间", "床位")):
        return False
    return True
