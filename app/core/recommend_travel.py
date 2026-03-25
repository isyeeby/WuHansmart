"""出行目的：问卷/用户表中文 → 条件推荐引擎使用的英文 key（与 scene_scores、PURPOSE_* 一致）。"""
from __future__ import annotations

from typing import Optional

_CN_TO_EN = {
    "情侣": "couple",
    "家庭": "family",
    "商务": "business",
    "考研": "exam",
    "团建聚会": "team_party",
    "医疗陪护": "medical",
    "宠物友好": "pet_friendly",
    "长租": "long_stay",
    # 休闲无单独场景分，映射到 couple 以保留设施/价格偏置
    "休闲": "couple",
}

_VALID_EN = frozenset(
    {
        "couple",
        "family",
        "business",
        "exam",
        "team_party",
        "medical",
        "pet_friendly",
        "long_stay",
    }
)


def travel_purpose_for_condition_recommend(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).strip()
    if s in _CN_TO_EN:
        return _CN_TO_EN[s]
    if s in _VALID_EN:
        return s
    return None
