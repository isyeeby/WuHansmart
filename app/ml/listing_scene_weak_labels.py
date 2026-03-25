# -*- coding: utf-8 -*-
"""
房源场景弱监督标签（与推荐 travel_purpose 对齐）。

通过关键词在「标题 + 标签 + 摘要」文本上打多标签 0/1，供 TF-IDF + 逻辑回归训练。
可人工增删 KEYWORDS_* 以提升弱标签质量（无需改训练代码结构）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.hospital_poi import min_distance_to_hospitals_km
from app.ml.hospital_poi import coord_to_float as _coord_to_float

# 与 recommender 中 travel_purpose（英文 key）顺序一致
LABEL_NAMES: List[str] = [
    "couple",
    "family",
    "business",
    "exam",
    "team_party",
    "medical",
    "pet_friendly",
    "long_stay",
]

WEAK_RULE_VERSION = "4"

# 距最近医院 POI 小于等于该值（km）时，弱标签 medical 置 1（与文本关键词 OR）
MEDICAL_HOSPITAL_PROXIMITY_KM = 2.0

# 每类一组关键词（命中任一即该维为 1）
# v3：收紧团建（去掉泛化「聚会/派对」）、加强长租短语、宠物去掉单字猫狗、医疗补充就医语境
KEYWORDS_COUPLE: List[str] = [
    "情侣", "浪漫", "蜜月", "二人", "投影", "浴缸", "夜景", "大床",
    "约会", "婚纱", "纪念日",
]
KEYWORDS_FAMILY: List[str] = [
    "亲子", "家庭", "儿童", "婴儿", "宝宝", "带娃", "游乐园", "滑梯",
    "三居", "四居", "两居", "两室一厅", "两居室", "全家", "老人", "长辈",
]
KEYWORDS_BUSINESS: List[str] = [
    "商务", "差旅", "出差", "办公", "会议", "接待", "工位", "注册",
    "写字楼", "CBD", "高铁", "机场",
]
KEYWORDS_EXAM: List[str] = [
    "考研", "自习", "考试", "备考", "图书馆", "安静", "学习", "学生",
    "高校", "大学", "校区", "复习",
]
KEYWORDS_TEAM_PARTY: List[str] = [
    "团建",
    "公司团建",
    "部门团建",
    "团建别墅",
    "团建房",
    "轰趴",
    "轰趴别墅",
    "轰趴馆",
    "轰趴馆别墅",
    "年会",
    "年会场地",
    "拓展活动",
    "拓展训练",
    "包栋",
    "整栋出租",
    "别墅包栋",
    "棋牌室",
    "麻将房",
    "KTV",
    "桌游房",
    "烧烤聚会",
    "派对房",
    "生日派对房",
    "公司聚会",
    "朋友聚会",
    "聚会包场",
    "别墅轰趴",
]
KEYWORDS_MEDICAL: List[str] = [
    "医院",
    "近医院",
    "医院旁",
    "医院附近",
    "距医院",
    "陪护",
    "陪护床",
    "就诊",
    "门诊",
    "复诊",
    "化疗",
    "住院",
    "看病",
    "就医",
    "复查",
    "术后",
    "协和",
    "同济",
    "中医院",
    "人民医院",
    "妇产",
    "省人民",
    "肿瘤",
]
KEYWORDS_PET_FRIENDLY: List[str] = [
    "宠物",
    "携宠",
    "可带宠物",
    "可携带宠物",
    "允许宠物",
    "宠物友好",
    "宠物入住",
    "带宠物",
    "喵星人",
    "遛狗",
    "狗狗友好",
    "猫咪友好",
]
KEYWORDS_LONG_STAY: List[str] = [
    "月租",
    "长租",
    "《长租》",
    "可长租",
    "短租长租",
    "短租/长租",
    "可短租长租",
    "包月",
    "包月租",
    "周租",
    "季租",
    "年租",
    "拎包长住",
    "整租月付",
    "日租月付",
    "月租价",
    "月租房",
    "连续入住",
    "住满一个月",
    "欢迎月租",
    "支持月租",
    "月租优惠",
    "长租优惠",
    "按月出租",
    "住一个月",
    "住一月",
    "月租可",
    "长租可",
]

LABEL_KEYWORDS: Dict[str, List[str]] = {
    "couple": KEYWORDS_COUPLE,
    "family": KEYWORDS_FAMILY,
    "business": KEYWORDS_BUSINESS,
    "exam": KEYWORDS_EXAM,
    "team_party": KEYWORDS_TEAM_PARTY,
    "medical": KEYWORDS_MEDICAL,
    "pet_friendly": KEYWORDS_PET_FRIENDLY,
    "long_stay": KEYWORDS_LONG_STAY,
}


def weak_multilabel(text: str) -> np.ndarray:
    """
    对单条文本生成形状 (len(LABEL_NAMES),) 的 0/1 向量。
    """
    if not text or not text.strip():
        return np.zeros(len(LABEL_NAMES), dtype=np.int32)
    t = text
    out = np.zeros(len(LABEL_NAMES), dtype=np.int32)
    for i, name in enumerate(LABEL_NAMES):
        for kw in LABEL_KEYWORDS.get(name, []):
            if kw in t:
                out[i] = 1
                break
    return out


def weak_multilabel_batch(
    texts: Sequence[str],
    lats: Optional[Sequence[Any]] = None,
    lons: Optional[Sequence[Any]] = None,
    hospitals: Optional[Sequence[dict]] = None,
    medical_geo_km: float = MEDICAL_HOSPITAL_PROXIMITY_KM,
) -> np.ndarray:
    """(n_samples, n_labels) int32。若传入 hospitals 与等长 lats/lons，在距离≤medical_geo_km 时置 medical=1。"""
    rows = [weak_multilabel(s) for s in texts]
    Y = np.stack(rows, axis=0) if rows else np.zeros((0, len(LABEL_NAMES)), dtype=np.int32)
    n = len(texts)
    if (
        hospitals
        and len(hospitals) > 0
        and lats is not None
        and lons is not None
        and len(lats) >= n
        and len(lons) >= n
        and n > 0
    ):
        mi = LABEL_NAMES.index("medical")
        hlist = list(hospitals)
        for i in range(n):
            d = min_distance_to_hospitals_km(_coord_to_float(lats[i]), _coord_to_float(lons[i]), hlist)
            if d is not None and d <= medical_geo_km:
                Y[i, mi] = 1
    return Y
