# -*- coding: utf-8 -*-
"""
轻量路由烟测：对主要 GET 做「非 500」断言。
环境由 tests/conftest.py 配置为 SQLite + init_db；需本地能 import 应用。

运行:
  cd Tujia-backend
  pip install pytest httpx
  pytest tests/test_smoke_routes.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
def test_public_get_smoke(client: TestClient, path):
    r = client.get(path)
    _assert_not_server_error(r)


def test_geocode_forward_query(client: TestClient):
    r = client.get("/api/geocode/forward", params={"q": "武汉市"})
    assert r.status_code in (200, 404, 502)


def test_predict_price_post(client: TestClient):
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


def test_investment_calculate_post(client: TestClient):
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
