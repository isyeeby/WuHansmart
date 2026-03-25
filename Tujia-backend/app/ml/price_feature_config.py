# -*- coding: utf-8 -*-
"""
民宿定价模型：设施关键词与派生特征定义。

训练脚本与 ModelManager 推理共用，保证特征语义一致（论文中可引用为「特征字典单一来源」）。
"""
from __future__ import annotations

from typing import Dict, List

# 设施/标签关键词 -> 模型二值特征列名（与数据库 house_tags 解析一致）
FACILITY_KEYWORDS: Dict[str, str] = {
    # 位置特征
    "近地铁": "near_subway",
    "近火车站": "near_station",
    "近高校": "near_university",
    "近滑雪场": "near_ski",
    # 景观特征
    "江景": "river_view",
    "湖景": "lake_view",
    "山景": "mountain_view",
    "观景露台": "terrace",
    "阳光房": "sunroom",
    "私家花园": "garden",
    "格调小院": "garden",
    "高层城景": "city_view",
    # 设施特征
    "有投影": "projector",
    "巨幕投影": "big_projector",
    "有洗衣机": "washer",
    "有浴缸": "bathtub",
    "观景浴缸": "view_bathtub",
    "KTV": "karaoke",
    "卡拉OK": "karaoke",
    "有麻将机": "mahjong",
    "可做饭": "kitchen",
    "有冰箱": "fridge",
    "有烤箱": "oven",
    "干湿分离": "dry_wet_sep",
    "智能门锁": "smart_lock",
    "智能马桶": "smart_toilet",
    "冷暖空调": "ac",
    "全天热水": "hot_water",
    "有电梯": "elevator",
    # 服务特征
    "可带宠物": "pet_friendly",
    "免费停车": "free_parking",
    "付费停车位": "paid_parking",
    "免费瓶装水": "free_water",
    "前台接待": "front_desk",
    "管家服务": "butler",
    "行李寄存": "luggage",
    # 装修风格
    "现代风": "style_modern",
    "网红INS风": "style_ins",
    "欧美风": "style_western",
    "中式风": "style_chinese",
    "日式风": "style_japanese",
    # 认证特征
    "实拍看房": "real_photo",
    "立即确认": "instant_confirm",
    # 人群特征
    "亲子精选": "family_friendly",
    "商务差旅": "business",
}


def ordered_facility_columns() -> List[str]:
    """与训练时列顺序一致的去重设施特征名列表（用于 facility_count 等）。"""
    return list(dict.fromkeys(FACILITY_KEYWORDS.values()))


def compute_is_budget_structural(area: float, bedroom_count: int) -> int:
    """
    经济型户型结构代理（不使用房价标签，避免标签泄漏）。

    定义：面积偏小且卧室数不超过 1，表示「小户型/低配套供给」结构类别，
    与是否「当前挂低价」无因果依赖，可用于论文中说明「结构变量而非结果变量」。
    """
    try:
        a = float(area)
        b = int(bedroom_count)
    except (TypeError, ValueError):
        return 0
    return 1 if (a < 30 and b <= 1) else 0
