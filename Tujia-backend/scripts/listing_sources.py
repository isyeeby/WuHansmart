# -*- coding: utf-8 -*-
"""
途家两源 JSON 约定
==================
- tujia_calendar_data.json：价日历、截面价、经纬度、基础标签等（量大，需流式解析）
- tujia_calendar_data_tags.json：详情页结构（户型、位置模块等）

**完整可用的房源** = 上述两文件中 **unit_id 的交集**。仅存在于单一文件的记录视为不完整，导入/回填默认可跳过。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Set

import ijson  # type: ignore


def parse_favorite_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if "w" in v:
            try:
                return int(float(v.replace("w", "").replace("+", "")) * 10000)
            except ValueError:
                return 0
        if "k" in v:
            try:
                return int(float(v.replace("k", "").replace("+", "")) * 1000)
            except ValueError:
                return 0
        try:
            return int(float(v))
        except ValueError:
            return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_tags_unit_id_set(tags_json: Path) -> Set[str]:
    """流式读取 tags 对象的所有 key（unit_id），不把整文件载入内存。"""
    out: Set[str] = set()
    with open(tags_json, "rb") as f:
        for uid, _payload in ijson.kvitems(f, "tags"):
            s = str(uid).strip()
            if s:
                out.add(s)
    return out


def build_calendar_maps(calendar_json: Path) -> Dict[str, Any]:
    """
    流式扫描日历 JSON，构建按 unit_id 索引的字段映射与 calendar_id 集合。
    """
    calendar_ids: Set[str] = set()
    price_map: Dict[str, float] = {}
    district_map: Dict[str, str] = {}
    trade_area_map: Dict[str, str] = {}
    rating_map: Dict[str, float] = {}
    lat_map: Dict[str, float] = {}
    lon_map: Dict[str, float] = {}
    title_map: Dict[str, str] = {}
    cover_map: Dict[str, str] = {}
    fav_map: Dict[str, int] = {}
    pics_map: Dict[str, str] = {}

    with open(calendar_json, "rb") as f:
        for house in ijson.items(f, "houses.item", use_float=True):
            uid = house.get("unit_id")
            if uid is None:
                continue
            u = str(uid).strip()
            if not u:
                continue
            calendar_ids.add(u)
            price_map[u] = float(house.get("final_price") or 0)
            district_map[u] = str(house.get("district") or "")
            trade_area_map[u] = str(house.get("trade_area") or "")
            rating_map[u] = float(house.get("rating") or 0)
            la = house.get("latitude")
            lo = house.get("longitude")
            try:
                if la is not None and lo is not None:
                    lat_map[u] = float(la)
                    lon_map[u] = float(lo)
            except (TypeError, ValueError):
                pass
            title_map[u] = str(house.get("title") or "")
            cover_map[u] = str(house.get("cover_image") or "")
            fav_map[u] = parse_favorite_count(house.get("favorite_count"))
            pics = house.get("house_pics", [])
            if isinstance(pics, list):
                pics_map[u] = json.dumps(pics, ensure_ascii=False)

    return {
        "calendar_ids": calendar_ids,
        "price_map": price_map,
        "district_map": district_map,
        "trade_area_map": trade_area_map,
        "rating_map": rating_map,
        "lat_map": lat_map,
        "lon_map": lon_map,
        "title_map": title_map,
        "cover_map": cover_map,
        "fav_map": fav_map,
        "pics_map": pics_map,
    }


def summarize_intersection(
    calendar_json: Path, tags_json: Path
) -> Dict[str, Any]:
    """按 unit_id 唯一值统计：交集 = 两文件均存在的房源。"""
    tags_set = load_tags_unit_id_set(tags_json)
    calendar_ids: Set[str] = set()
    with open(calendar_json, "rb") as f:
        for house in ijson.items(f, "houses.item", use_float=True):
            uid = house.get("unit_id")
            if uid is None:
                continue
            u = str(uid).strip()
            if u:
                calendar_ids.add(u)
    inter = calendar_ids & tags_set
    return {
        "tags_unique_count": len(tags_set),
        "calendar_unique_count": len(calendar_ids),
        "intersection_count": len(inter),
        "calendar_only_count": len(calendar_ids - tags_set),
        "tags_only_count": len(tags_set - calendar_ids),
    }
