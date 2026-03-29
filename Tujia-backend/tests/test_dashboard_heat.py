"""驾驶舱商圈热度：排名映射与排序键。"""
from app.api.endpoints.dashboard import (
    _assign_rank_display_heat,
    _dashboard_trade_area_heat_raw,
    _heat_row_sort_key,
    _normalize_heat_displays,
)


def test_normalize_all_equal_returns_sixty():
    assert _normalize_heat_displays([1.0, 1.0, 1.0]) == [60, 60, 60]


def test_normalize_two_endpoints():
    h = _normalize_heat_displays([0.0, 10.0])
    assert h[0] == 20
    assert h[1] == 100


def test_rank_display_heat_top_distinct():
    rows = [
        {"raw": 50.0, "listing_count": 1, "name": "A"},
        {"raw": 40.0, "listing_count": 1, "name": "B"},
        {"raw": 30.0, "listing_count": 1, "name": "C"},
    ]
    _assign_rank_display_heat(rows)
    by_name = {r["name"]: r["heat"] for r in rows}
    assert by_name["A"] == 100
    assert by_name["B"] == 99
    assert by_name["C"] == 98


def test_rank_display_same_raw_tie_break_still_distinct_scores():
    rows = [
        {"raw": 42.0, "listing_count": 5, "name": "光谷"},
        {"raw": 42.0, "listing_count": 5, "name": "江汉路"},
        {"raw": 42.0, "listing_count": 5, "name": "楚河汉街"},
    ]
    _assign_rank_display_heat(rows)
    heats = sorted([r["heat"] for r in rows], reverse=True)
    assert heats == [100, 99, 98]


def test_rank_single_row_sixty():
    rows = [{"raw": 10.0, "listing_count": 1, "name": "X"}]
    _assign_rank_display_heat(rows)
    assert rows[0]["heat"] == 60


def test_heat_row_sort_key_tie_breaker():
    a = {"raw": 10.0, "listing_count": 3, "name": "B"}
    b = {"raw": 10.0, "listing_count": 5, "name": "A"}
    c = {"raw": 9.0, "listing_count": 99, "name": "Z"}
    ordered = sorted([a, b, c], key=_heat_row_sort_key)
    assert ordered[0] == b
    assert ordered[1] == a
    assert ordered[2] == c


def test_raw_formula_monotonic_in_listing_count():
    r1 = _dashboard_trade_area_heat_raw(1, 4.5, 10.0)
    r2 = _dashboard_trade_area_heat_raw(100, 4.5, 10.0)
    assert r2 > r1
