"""
地理编码（正地理编码）：地址/关键词 → 经纬度。

使用 OpenStreetMap Nominatim 公共服务，请求经后端转发以便统一 User-Agent、避免浏览器直连受限。
使用须知：https://operations.osmfoundation.org/policies/nominatim/（勿高频调用，毕设演示足够）。
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["地理编码"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# 政策要求可识别的 User-Agent；部署时可改为你的邮箱或项目主页
USER_AGENT = "TujiaHomestayThesis/1.0 (educational; Wuhan homestay project)"


@router.get("/forward")
def forward_geocode(
    q: str = Query(..., min_length=2, max_length=300, description="地址或关键词，建议含「武汉市」"),
    limit: int = Query(3, ge=1, le=5),
) -> Dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "q": q.strip(),
            "format": "jsonv2",
            "limit": str(limit),
            "addressdetails": "0",
        }
    )
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,en",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        logger.warning("Nominatim HTTP error: %s", e)
        raise HTTPException(status_code=502, detail="地理编码服务暂时不可用") from e
    except urllib.error.URLError as e:
        logger.warning("Nominatim URL error: %s", e)
        raise HTTPException(status_code=502, detail="无法连接地理编码服务，请检查网络") from e

    try:
        data: List[dict] = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail="地理编码返回异常") from e

    results = []
    for item in data:
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        results.append(
            {
                "latitude": round(lat, 7),
                "longitude": round(lon, 7),
                "display_name": item.get("display_name") or "",
            }
        )

    if not results:
        raise HTTPException(status_code=404, detail="未找到匹配位置，请换更完整的地址再试")

    return {"query": q.strip(), "results": results}
