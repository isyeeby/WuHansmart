# -*- coding: utf-8 -*-
"""
医院 POI：Haversine 直线距离 + 最近点名称，供弱标签「医疗陪护」与 listings.nearest_hospital_km / nearest_hospital_name 回写。

默认数据文件：`Tujia-backend/data/hospital_poi_wuhan.json`（name, lat, lon）。
缺失文件或空列表时，地理逻辑静默跳过。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点球面大圆距离（千米）。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return _EARTH_RADIUS_KM * c


def coord_to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def load_hospital_pois(path: Optional[Path] = None) -> List[dict]:
    """
    读取 JSON 数组，每项需含 lat、lon；name 可选。
    path 默认：本包上级目录的 data/hospital_poi_wuhan.json。
    """
    if path is None:
        # app/ml/hospital_poi.py -> 仓库根 Tujia-backend
        root = Path(__file__).resolve().parent.parent.parent
        path = root / "data" / "hospital_poi_wuhan.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    out: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        lat = coord_to_float(item.get("lat"))
        lon = coord_to_float(item.get("lon"))
        if lat is None or lon is None:
            continue
        name = item.get("name")
        out.append({"name": str(name) if name is not None else "", "lat": lat, "lon": lon})
    return out


def nearest_hospital_km_and_name(
    lat: Optional[float],
    lon: Optional[float],
    hospitals: Sequence[dict],
) -> Tuple[Optional[float], Optional[str]]:
    """返回 (距离 km, 最近 POI 名称)；无坐标或无 POI 时 (None, None)。名称取自 JSON 的 name。"""
    if lat is None or lon is None or not hospitals:
        return None, None
    best_d: Optional[float] = None
    best_name: Optional[str] = None
    for h in hospitals:
        d = haversine_km(lat, lon, float(h["lat"]), float(h["lon"]))
        if best_d is None or d < best_d:
            best_d = d
            raw = h.get("name")
            nm = str(raw).strip() if raw is not None else ""
            best_name = nm if nm else None
    return best_d, best_name


def min_distance_to_hospitals_km(
    lat: Optional[float],
    lon: Optional[float],
    hospitals: Sequence[dict],
) -> Optional[float]:
    """无坐标或无 POI 时返回 None。"""
    d, _ = nearest_hospital_km_and_name(lat, lon, hospitals)
    return d


def batch_nearest_hospital_km_and_name(
    lats: Sequence[Any],
    lons: Sequence[Any],
    hospitals: Sequence[dict],
) -> Tuple[List[Optional[float]], List[Optional[str]]]:
    """与 lats/lons 等长；距离与名称列表一一对应。"""
    n = min(len(lats), len(lons))
    if not hospitals:
        return [None] * n, [None] * n
    kms: List[Optional[float]] = []
    names: List[Optional[str]] = []
    for i in range(n):
        d, nm = nearest_hospital_km_and_name(
            coord_to_float(lats[i]), coord_to_float(lons[i]), hospitals
        )
        kms.append(d)
        names.append(nm)
    return kms, names


def batch_nearest_hospital_km(
    lats: Sequence[Any],
    lons: Sequence[Any],
    hospitals: Sequence[dict],
) -> List[Optional[float]]:
    """与 lats/lons 等长；每条为到最近 POI 的 km 或 None。"""
    kms, _ = batch_nearest_hospital_km_and_name(lats, lons, hospitals)
    return kms
