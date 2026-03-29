# -*- coding: utf-8 -*-
"""业务规则与健康检查单测（不依赖真实 Hive）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints.my_listings import _build_comparison_analysis


def test_health_returns_database_and_hive_shape(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]
    assert isinstance(data["services"].get("hive"), dict)
    assert "required" in data["services"]["hive"]
    assert "reachable" in data["services"]["hive"]


def test_compare_post_too_few_ids_returns_400(client: TestClient):
    r = client.post("/api/compare/", json={"unit_ids": ["a"], "comparison_type": "full"})
    assert r.status_code == 400


def test_build_comparison_analysis_low_price():
    out = _build_comparison_analysis(80.0, 100.0, [90.0, 110.0])
    assert out["advantages"]
    assert isinstance(out.get("disadvantages"), list)


def test_build_comparison_analysis_high_price():
    out = _build_comparison_analysis(150.0, 100.0, [90.0, 110.0])
    assert out["disadvantages"]
    assert out["suggestions"]
