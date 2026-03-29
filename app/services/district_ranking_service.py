# -*- coding: utf-8 -*-
"""
行政区投资/热度排行（MySQL 路径）

优先使用价格日历中 can_booking=0 的天次占比，作为「相对订房紧张度」的数据化代理；
样本不足时回退到评分+收藏启发式，并在结果中标注 occupancy_basis，便于论文与验收说明依据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.database import Listing, PriceCalendar

logger = logging.getLogger(__name__)

MIN_LISTINGS_PER_DISTRICT = 5
# 单区日历天次低于该阈值则认为统计不稳，不用日历占比
MIN_CALENDAR_ROWS_PER_DISTRICT = 200

# 与 /api/investment/ranking、/api/analysis/roi-ranking 返回的 field_glossary 共用
DISTRICT_ROI_RANKING_FIELD_GLOSSARY: Dict[str, str] = {
    "roi_score": (
        "0–100 综合吸引力分：日历/启发式需求代理、评分、价格带、供给规模加权；非财务年化收益率。"
    ),
    "occupancy_rate": (
        "需求强度代理(%)：calendar_unavailable_share 时为日历不可订天次占比；"
        "heuristic_rating_favorites 时为评分+收藏启发式；非 PMS 真实入住率。"
    ),
    "calendar_unavailable_share_pct": (
        "与 occupancy_rate 同源，仅日历样本充足时有值；不可订天次/总天次×100。"
    ),
    "estimated_roi": (
        "收入强度比：估算年毛收入÷(区日均×30)，非标准 ROI；"
        "勿与投资计算器返回的 annual_roi（首付股本回报）混淆。"
    ),
    "revenue_intensity_ratio": "与 estimated_roi 同值，命名强调非财务 ROI。",
}


def _price_band_norm(avg_price: float) -> float:
    """适中均价映射到 0–100，供加权综合分使用。"""
    if 200 <= avg_price <= 400:
        raw = 80.0
    elif 150 <= avg_price < 200 or 400 < avg_price <= 500:
        raw = 70.0
    elif avg_price > 0:
        raw = 60.0
    else:
        raw = 55.0
    return max(0.0, min(100.0, (raw - 60.0) / 20.0 * 100.0))


def _heuristic_occupancy_pct(avg_rating: float, avg_favorites: float) -> float:
    return round(
        max(
            42.0,
            min(
                90.0,
                58.0
                + (avg_rating - 4.0) * 18.0
                + min(avg_favorites * 0.06, 12.0),
            ),
        ),
        1,
    )


def fetch_calendar_booked_share_by_district(
    db: Session, min_rows: int = MIN_CALENDAR_ROWS_PER_DISTRICT
) -> Dict[str, Tuple[float, int]]:
    """
    各行政区：不可订天次 / 日历总天次 × 100。

    依据：途家日历 can_booking=0 表示该日不可预订，在样本期内占比越高，
    说明相对订房更紧（或供给更满），可作为需求强度的数据代理，而非主观系数。
    """
    rows = (
        db.query(
            Listing.district,
            func.count(PriceCalendar.id).label("total"),
            func.sum(case((PriceCalendar.can_booking == 0, 1), else_=0)).label("booked"),
        )
        .join(Listing, PriceCalendar.unit_id == Listing.unit_id)
        .filter(Listing.district.isnot(None), Listing.district != "")
        .group_by(Listing.district)
        .having(func.count(PriceCalendar.id) >= min_rows)
        .all()
    )
    out: Dict[str, Tuple[float, int]] = {}
    for district, total, booked in rows:
        if not district:
            continue
        t = int(total or 0)
        b = int(booked or 0)
        if t <= 0:
            continue
        pct = round(100.0 * b / float(t), 1)
        out[str(district)] = (pct, t)
    if out:
        logger.info(
            "district_ranking: calendar_booked_share for %s districts (min_rows=%s)",
            len(out),
            min_rows,
        )
    else:
        logger.info(
            "district_ranking: no district met calendar sample threshold (min_rows=%s)",
            min_rows,
        )
    return out


def _activity_norm(listing_count: int) -> float:
    return float(min(100, listing_count * 5))


def build_mysql_district_roi_rankings(
    db: Session, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    供 hive_service MySQL 回退与 /api/analysis/roi-ranking 共用。

    综合分（0–100）：40% 入住代理 + 25% 评分 + 25% 价格适宜度 + 10% 供给活跃度；
    入住代理优先用日历不可订占比（在同批有日历的区之间 min-max 归一化），
    否则用启发式百分比并线性映射到 0–100。
    """
    cal_map = fetch_calendar_booked_share_by_district(db)
    cal_pcts = [v[0] for v in cal_map.values()]
    lo = min(cal_pcts) if cal_pcts else 0.0
    hi = max(cal_pcts) if cal_pcts else 0.0

    def norm_calendar_pct(pct: float) -> float:
        if not cal_pcts or hi <= lo:
            return 50.0
        return max(0.0, min(100.0, (pct - lo) / (hi - lo) * 100.0))

    results = (
        db.query(
            Listing.district,
            func.avg(Listing.final_price).label("avg_price"),
            func.count(Listing.unit_id).label("total_listings"),
            func.avg(Listing.rating).label("avg_rating"),
            func.avg(Listing.favorite_count).label("avg_favorites"),
        )
        .filter(Listing.final_price.isnot(None))
        .group_by(Listing.district)
        .having(func.count(Listing.unit_id) >= MIN_LISTINGS_PER_DISTRICT)
        .all()
    )

    rankings: List[Dict[str, Any]] = []
    for r in results:
        district = r.district
        if not district:
            continue
        avg_price = float(r.avg_price or 0)
        avg_rating = float(r.avg_rating or 0)
        avg_favorites = float(r.avg_favorites or 0)
        listing_count = int(r.total_listings or 0)

        cal_entry = cal_map.get(str(district))
        if cal_entry is not None:
            occupancy_rate, cal_n = cal_entry
            occ_basis = "calendar_unavailable_share"
            occ_norm = norm_calendar_pct(occupancy_rate)
            data_note = "mysql_calendar_weighted"
        else:
            occupancy_rate = _heuristic_occupancy_pct(avg_rating, avg_favorites)
            cal_n = None
            occ_basis = "heuristic_rating_favorites"
            occ_norm = max(
                0.0,
                min(100.0, (occupancy_rate - 42.0) / (90.0 - 42.0) * 100.0),
            )
            data_note = "mysql_mixed_heuristic_occ"

        rating_norm = max(0.0, min(100.0, (avg_rating / 5.0) * 100.0))
        price_norm = _price_band_norm(avg_price)
        act_norm = _activity_norm(listing_count)

        composite = (
            occ_norm * 0.40
            + rating_norm * 0.25
            + price_norm * 0.25
            + act_norm * 0.10
        )
        roi_score = round(composite, 1)
        inv_int = int(max(0, min(100, round(composite))))

        monthly_revenue = avg_price * 30.0 * (occupancy_rate / 100.0) if avg_price > 0 else 0.0
        estimated_roi = (
            (monthly_revenue * 12.0 / (avg_price * 30.0 + 1.0)) if avg_price > 0 else 0.0
        )
        er_rounded = round(estimated_roi, 1)
        calendar_unavailable_pct = (
            round(occupancy_rate, 1) if occ_basis == "calendar_unavailable_share" else None
        )

        risk_level = (
            "收益突出"
            if composite >= 75
            else "中等收益"
            if composite >= 60
            else "保守区间"
        )
        recommendation = "推荐投资" if composite >= 70 else "谨慎投资"

        rankings.append(
            {
                "district": district,
                "roi_score": roi_score,
                "avg_price": round(avg_price, 2),
                "occupancy_rate": occupancy_rate,
                "occupancy_basis": occ_basis,
                "calendar_sample_rows": cal_n,
                "calendar_unavailable_share_pct": calendar_unavailable_pct,
                "recommendation": recommendation,
                "estimated_monthly_revenue": round(monthly_revenue, 2),
                "estimated_roi": er_rounded,
                "revenue_intensity_ratio": er_rounded,
                "investment_score": inv_int,
                "risk_level": risk_level,
                "data_source_note": data_note,
            }
        )

    rankings.sort(key=lambda x: x["roi_score"], reverse=True)
    if limit is not None:
        return rankings[:limit]
    return rankings


def build_analysis_roi_ranking_rows(db: Session, limit: int) -> List[Dict[str, Any]]:
    """/api/analysis/roi-ranking：字段子集 + 与历史一致的四档文案。"""
    full = build_mysql_district_roi_rankings(db, limit=None)
    out: List[Dict[str, Any]] = []
    for row in full[:limit]:
        sc = float(row["roi_score"])
        if sc >= 80:
            rec = "强烈推荐"
        elif sc >= 70:
            rec = "推荐投资"
        elif sc >= 60:
            rec = "谨慎考虑"
        else:
            rec = "不推荐"
        out.append(
            {
                "district": row["district"],
                "roi_score": round(sc, 1),
                "avg_price": row["avg_price"],
                "occupancy_rate": row["occupancy_rate"],
                "occupancy_basis": row["occupancy_basis"],
                "calendar_sample_rows": row["calendar_sample_rows"],
                "calendar_unavailable_share_pct": row.get(
                    "calendar_unavailable_share_pct"
                ),
                "estimated_roi": row.get("estimated_roi"),
                "revenue_intensity_ratio": row.get("revenue_intensity_ratio"),
                "recommendation": rec,
                "data_source_note": row["data_source_note"],
            }
        )
    return out
