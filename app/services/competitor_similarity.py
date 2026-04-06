# -*- coding: utf-8 -*-
"""
「我的房源」与平台 Listing 之间的竞品相似度：分项 0–100，按权重加权；缺失项不参与并自动重加权。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional, Tuple

# 权重总和应为 1.0，便于调参
W_PRICE = 0.35
W_AREA = 0.25
W_BEDROOM = 0.15
W_BED = 0.10
W_CAPACITY = 0.15

_AREA_EPS = 1e-6
_INT_PENALTY = 25.0  # 每差 1 间/床/人扣 25 分，封顶 0


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _price_similarity(my_price: float, comp_price: float) -> Optional[float]:
    if my_price <= 0 or comp_price <= 0:
        return None
    raw = 100.0 - abs(comp_price - my_price) / my_price * 100.0
    return max(0.0, min(100.0, raw))


def _int_feature_similarity(a: Optional[int], b: Optional[int]) -> Optional[float]:
    if a is None or b is None:
        return None
    return max(0.0, 100.0 - _INT_PENALTY * abs(a - b))


def _area_similarity(a1: Optional[float], a2: Optional[float]) -> Optional[float]:
    if a1 is None or a2 is None:
        return None
    if a1 < 0 or a2 < 0:
        return None
    denom = max(a1, a2, _AREA_EPS)
    rel = abs(a1 - a2) / denom
    return max(0.0, min(100.0, 100.0 * (1.0 - min(1.0, rel))))


def _weighted_mean(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """pairs: (weight, score). 仅使用 score 非 None 的项（调用方已过滤为 float）。"""
    if not pairs:
        return None
    w_sum = sum(w for w, _ in pairs)
    if w_sum <= 0:
        return None
    return sum(w * s for w, s in pairs) / w_sum


def compute_my_listing_similarity(my_listing: Any, competitor_listing: Any) -> float:
    """
    综合相似度 0–100。my_listing 需有 current_price、bedroom_count、bed_count、max_guests、area；
    competitor_listing 需有 final_price、bedroom_count、bed_count、capacity、area。
    字段可为 ORM 列类型（Numeric 等）。任一侧缺失的维度跳过，剩余权重按比例放大；全部缺失时返回 50。
    """
    my_price = _to_float(getattr(my_listing, "current_price", None))
    cp = _to_float(getattr(competitor_listing, "final_price", None))

    my_bd = _to_int(getattr(my_listing, "bedroom_count", None))
    c_bd = _to_int(getattr(competitor_listing, "bedroom_count", None))
    my_bed = _to_int(getattr(my_listing, "bed_count", None))
    c_bed = _to_int(getattr(competitor_listing, "bed_count", None))
    my_cap = _to_int(getattr(my_listing, "max_guests", None))
    c_cap = _to_int(getattr(competitor_listing, "capacity", None))
    my_area = _to_float(getattr(my_listing, "area", None))
    c_area = _to_float(getattr(competitor_listing, "area", None))

    parts: List[Tuple[float, float]] = []

    ps = None
    if my_price is not None and cp is not None and my_price > 0 and cp > 0:
        ps = _price_similarity(my_price, cp)
    if ps is not None:
        parts.append((W_PRICE, ps))

    bs = _int_feature_similarity(my_bd, c_bd)
    if bs is not None:
        parts.append((W_BEDROOM, bs))

    beds = _int_feature_similarity(my_bed, c_bed)
    if beds is not None:
        parts.append((W_BED, beds))

    caps = _int_feature_similarity(my_cap, c_cap)
    if caps is not None:
        parts.append((W_CAPACITY, caps))

    ars = _area_similarity(my_area, c_area)
    if ars is not None:
        parts.append((W_AREA, ars))

    out = _weighted_mean(parts)
    if out is None:
        return 50.0
    return max(0.0, min(100.0, out))
