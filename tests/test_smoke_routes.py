# -*- coding: utf-8 -*-
"""
轻量路由烟测：启动 FastAPI 应用，对主要 GET 做「非 500」断言。
需本地可连 MySQL（与 .env 一致）；若库为空，部分接口可能 404，仍视为可接受。

运行:
  cd Tujia-backend
  pip install pytest httpx
  pytest tests/test_smoke_routes.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

# 保证以 Tujia-backend 为工作目录时可 import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _assert_not_server_error(resp):
    assert resp.status_code < 500, (resp.status_code, resp.text[:500])


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/api/home/stats",
        "/api/home/hot-districts",
        "/api/home/recommendations",
        "/api/dashboard/summary",
        "/api/dashboard/kpi",
        "/api/dashboard/heatmap",
        "/api/dashboard/trends",
        "/api/dashboard/alerts",
        "/api/listings?page=1&size=2",
        "/api/tags/categories",
        "/api/recommend",
        "/api/predict/district-trade-areas",
        "/api/predict/trend?district=洪山区&days=14",
        "/api/predict/feature-importance",
        "/api/analysis/districts",
        "/api/analysis/facility-premium",
        "/api/investment/ranking?limit=3",
    ],
)
def test_public_get_smoke(path):
    r = client.get(path)
    _assert_not_server_error(r)


def test_geocode_forward_query():
    r = client.get("/api/geocode/forward", params={"q": "武汉市"})
    # 外网 Nominatim 在 CI 可能失败，仅断言不崩溃
    assert r.status_code in (200, 404, 502)


def test_predict_price_post():
    r = client.post(
        "/api/predict/price",
        json={
            "district": "洪山区",
            "bedroom_count": 2,
            "bed_count": 2,
            "bathroom_count": 1,
            "area": 60,
            "capacity": 4,
        },
    )
    _assert_not_server_error(r)


def test_investment_calculate_post():
    r = client.post(
        "/api/investment/calculate",
        json={
            "district": "洪山区",
            "property_price": 80,
            "area_sqm": 65,
            "bedroom_count": 2,
            "expected_daily_price": 260,
        },
    )
    _assert_not_server_error(r)
