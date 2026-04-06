# -*- coding: utf-8 -*-
"""竞品相似度（我的房源 vs 平台 Listing）单测。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.competitor_similarity import compute_my_listing_similarity


def _my(**kw):
    base = dict(
        current_price=300.0,
        bedroom_count=2,
        bed_count=2,
        max_guests=4,
        area=60.0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _comp(**kw):
    base = dict(
        final_price=300.0,
        bedroom_count=2,
        bed_count=2,
        capacity=4,
        area=60.0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_identical_listing_near_100():
    s = compute_my_listing_similarity(_my(), _comp())
    assert s >= 99.0
    assert s <= 100.0


def test_large_price_gap_lowers_score():
    high = compute_my_listing_similarity(_my(current_price=200.0), _comp(final_price=200.0))
    low = compute_my_listing_similarity(_my(current_price=200.0), _comp(final_price=400.0))
    assert low < high


def test_bedroom_mismatch_lowers_score():
    match = compute_my_listing_similarity(_my(), _comp())
    mismatch = compute_my_listing_similarity(_my(), _comp(bedroom_count=5))
    assert mismatch < match


def test_missing_area_reweights_remaining():
    """面积缺失时仍用价格与户型等计算，不应直接 50。"""
    s = compute_my_listing_similarity(
        _my(area=None),
        _comp(area=None),
    )
    assert s >= 95.0


def test_all_dimensions_missing_returns_50():
    s = compute_my_listing_similarity(
        SimpleNamespace(
            current_price=None,
            bedroom_count=None,
            bed_count=None,
            max_guests=None,
            area=None,
        ),
        SimpleNamespace(
            final_price=None,
            bedroom_count=None,
            bed_count=None,
            capacity=None,
            area=None,
        ),
    )
    assert s == pytest.approx(50.0)


def test_no_price_but_layout_match_uses_structure_only():
    s = compute_my_listing_similarity(
        _my(current_price=0),
        _comp(final_price=0),
    )
    # 无有效价格时仅用户型/面积，完全匹配时应接近满分
    assert s >= 99.0
