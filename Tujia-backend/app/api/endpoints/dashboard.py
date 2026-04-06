#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard模块 API

KPI 中「入住率」「平台 ROI」为基于评分/收藏/供给的启发式代理指标，非订单口径。
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
import calendar

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models import schemas
from app.db.database import get_db
from app.services.kpi_helpers import occupancy_proxy, market_return_index

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])


def _price_calendar_period_daily_avg(
    db: Session, start_dt: datetime, end_dt: datetime
) -> float:
    """
    价格日历在 [start_dt, end_dt]（含）内：按自然日聚合后再对「有数据的日期」取平均。
    无行或全部无有效价时返回 0.0。
    """
    from app.db.database import PriceCalendar

    rows = (
        db.query(
            PriceCalendar.date,
            func.avg(PriceCalendar.price).label("daily_avg"),
        )
        .filter(PriceCalendar.date >= start_dt.strftime("%Y-%m-%d"))
        .filter(PriceCalendar.date <= end_dt.strftime("%Y-%m-%d"))
        .group_by(PriceCalendar.date)
        .order_by(PriceCalendar.date)
        .all()
    )
    daily_avgs = [float(r.daily_avg or 0) for r in rows if r.daily_avg is not None]
    if not daily_avgs:
        return 0.0
    return sum(daily_avgs) / len(daily_avgs)


def _dashboard_trade_area_heat_raw(
    listing_count: int,
    avg_rating: float,
    avg_favorites: float,
) -> float:
    """
    商圈热度「原始分」（仅用于排序与相对比较，不限幅）。

    供给用 log 压缩避免大商圈扎堆顶格；评分线性；收藏用 log 压缩。
    与旧版 40+30+30 封顶公式相比，更易拉开差距。
    """
    lc = int(listing_count or 0)
    ar = float(avg_rating or 0)
    af = float(avg_favorites or 0)
    return math.log1p(max(0, lc)) * 14.0 + ar * 9.0 + math.log1p(max(0.0, af)) * 5.0


def _normalize_heat_displays(scores: list[float]) -> list[int]:
    """将标量序列 min–max 映射到 20～100 整数；全为同一值时给 60。"""
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if mx <= mn:
        return [60] * len(scores)
    out: list[int] = []
    for r in scores:
        v = 20.0 + (r - mn) / (mx - mn) * 80.0
        out.append(int(round(max(20, min(100, v)))))
    return out


def _heat_row_sort_key(x: dict) -> tuple:
    """raw 降序；并列时房源数降序；再按名称稳定排序。"""
    return (-float(x["raw"]), -int(x.get("listing_count") or 0), x.get("name") or "")


def _assign_rank_display_heat(rows: list[dict]) -> None:
    """
    展示热度按全局排名映射：第 1 名 100，每降一名减 1，最低不低于 20。
    避免「多数商圈 raw 接近最高、少数极冷」时 min–max 四舍五入后几乎全是 100。

    仅 1 个商圈时给 60。超过 81 名后均为 20（整数刻度只有 81 档）。
    """
    if not rows:
        return
    ordered = sorted(rows, key=_heat_row_sort_key)
    if len(ordered) == 1:
        ordered[0]["heat"] = 60
        return
    for i, row in enumerate(ordered):
        row["heat"] = max(20, 100 - i)


def _trade_area_heat_rows(db: Session) -> list[dict]:
    """
    按 行政区+商圈 聚合 listings，计算 raw（排序依据）与展示 heat（按全局名次映射 20～100）。
    """
    from app.db.database import Listing

    results = db.query(
        Listing.district,
        Listing.trade_area,
        func.avg(Listing.longitude).label("avg_longitude"),
        func.avg(Listing.latitude).label("avg_latitude"),
        func.avg(Listing.final_price).label("avg_price"),
        func.count(Listing.unit_id).label("listing_count"),
        func.avg(Listing.rating).label("avg_rating"),
        func.avg(Listing.favorite_count).label("avg_favorites"),
    ).group_by(Listing.district, Listing.trade_area).all()

    rows: list[dict] = []
    for r in results:
        lc = int(r.listing_count or 0)
        ar = float(r.avg_rating or 0)
        af = float(r.avg_favorites or 0)
        raw = _dashboard_trade_area_heat_raw(lc, ar, af)
        rows.append(
            {
                "name": (r.trade_area or r.district or "").strip() or "未知区域",
                "avg_longitude": r.avg_longitude,
                "avg_latitude": r.avg_latitude,
                "avg_price": float(r.avg_price or 0),
                "listing_count": lc,
                "avg_rating": ar,
                "avg_favorites": af,
                "raw": raw,
            }
        )
    _assign_rank_display_heat(rows)
    return rows


@router.get("/summary", response_model=schemas.DashboardSummaryResponse)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    获取Dashboard核心指标汇总
    """
    from app.db.database import Listing

    total_listings = db.query(Listing).count()
    avg_price = db.query(func.avg(Listing.final_price)).scalar() or 0
    avg_rating = db.query(func.avg(Listing.rating)).scalar() or 0
    district_count = db.query(func.count(func.distinct(Listing.district))).scalar() or 0

    return schemas.DashboardSummaryResponse(
        total_listings=total_listings,
        avg_price=round(float(avg_price), 2),
        avg_rating=round(float(avg_rating), 2),
        district_count=district_count,
        price_trend=None
    )


@router.get("/district-comparison", response_model=schemas.DashboardDistrictComparisonResponse)
async def get_district_comparison(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    获取商圈对比数据
    """
    from app.db.database import Listing

    results = db.query(
        Listing.district,
        Listing.trade_area,
        func.avg(Listing.final_price).label('avg_price'),
        func.count(Listing.unit_id).label('listing_count'),
        func.avg(Listing.rating).label('avg_rating')
    ).group_by(Listing.district, Listing.trade_area).limit(limit).all()

    items = []
    for r in results:
        items.append(schemas.DistrictComparisonItem(
            district=r.district or '',
            trade_area=r.trade_area or '',
            avg_price=round(float(r.avg_price or 0), 2),
            listing_count=r.listing_count or 0,
            avg_rating=round(float(r.avg_rating or 0), 2)
        ))

    return schemas.DashboardDistrictComparisonResponse(items=items)


def _compute_dashboard_kpi(db: Session) -> schemas.DashboardKPIResponse:
    """KPI 计算体（供进程内短缓存复用）。"""
    from app.db.database import Listing

    total_listings = db.query(Listing).count()
    avg_price_result = db.query(func.avg(Listing.final_price)).scalar()
    avg_price = float(avg_price_result) if avg_price_result else 0.0
    district_count = db.query(func.count(func.distinct(Listing.district))).scalar() or 0

    avg_rating_result = db.query(func.avg(Listing.rating)).scalar()
    avg_rating = float(avg_rating_result) if avg_rating_result else 0.0
    avg_favorites_result = db.query(func.avg(Listing.favorite_count)).scalar()
    avg_favorites = float(avg_favorites_result) if avg_favorites_result else 0.0

    occupancy_rate = occupancy_proxy(avg_rating, avg_favorites)
    avg_roi = market_return_index(
        avg_price, occupancy_rate, avg_rating, avg_favorites, total_listings
    )

    price_change_percent = 0.0
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        current_start = today.replace(day=1)
        prev_month_end = current_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        compare_day = min(
            today.day, calendar.monthrange(prev_month_end.year, prev_month_end.month)[1]
        )
        prev_period_end = prev_month_start.replace(day=compare_day)

        # 主口径：本月 1 日～今日 vs 上月 1 日～上月「同日」的日历日均价对比
        current_avg = _price_calendar_period_daily_avg(db, current_start, today)
        prev_avg = _price_calendar_period_daily_avg(db, prev_month_start, prev_period_end)
        if prev_avg > 0 and current_avg > 0:
            price_change_percent = round((current_avg - prev_avg) / prev_avg * 100, 1)
        else:
            # 回退：本月/上月窗口常因「新月初无日历」或库内仅有一段连续日期而为 0。
            # 用「最近 window 天」vs「再往前 window 天」的日历日均价环比（与 /trends 同源表）。
            for window in (14, 7):
                end_a = today
                start_a = today - timedelta(days=window - 1)
                end_b = start_a - timedelta(days=1)
                start_b = end_b - timedelta(days=window - 1)
                avg_a = _price_calendar_period_daily_avg(db, start_a, end_a)
                avg_b = _price_calendar_period_daily_avg(db, start_b, end_b)
                if avg_b > 0 and avg_a > 0:
                    price_change_percent = round((avg_a - avg_b) / avg_b * 100, 1)
                    logger.info(
                        "dashboard kpi price_change: used rolling %dd vs prior %dd (calendar)",
                        window,
                        window,
                    )
                    break
    except Exception as e:
        logger.warning("dashboard kpi price_change from calendar: %s", e)

    return schemas.DashboardKPIResponse(
        total_listings=total_listings,
        avg_price=round(avg_price, 1),
        price_change_percent=price_change_percent,
        district_count=district_count,
        occupancy_rate=occupancy_rate,
        avg_roi=avg_roi,
        kpi_definitions={
            "occupancy_rate": "需求热度指数（约50–92）：由全市平均评分与收藏数估算，非订单口径入住率。",
            "avg_roi": (
                "市场吸引力指数（约5–26，非财务ROI）：9+raw 后限制在5–26；"
                "raw=(评分/5)×10+min(收藏/150,1)×7+(需求热度−55)×0.12+min(房源/800,1)×6；"
                "需求热度=需求热度卡片同源（52+(评分/5)×24+min(收藏×0.07,14)，限制50–92）。"
            ),
            "price_change_percent": (
                "价格环比：优先「本月1日～今日」与「上月同期」价格日历日均价；"
                "若该窗口无数据则回退为「最近14天 vs 再前14天」（再试7天）；"
                "仍无有效日历则为 0。与首页曲线同源 price_calendars 表。"
            ),
        },
    )


@router.get("/kpi", response_model=schemas.DashboardKPIResponse)
async def get_dashboard_kpi(db: Session = Depends(get_db)):
    """
    获取 KPI 核心指标（确定性计算；价格环比基于本月截至今日与上月同期的价格日历日均值对比，无则 0）。
    """
    from app.core.config import settings
    from app.services.in_process_cache import get_or_set

    ttl = float(settings.API_IN_PROCESS_CACHE_TTL_SECONDS)
    return get_or_set("dashboard:kpi", ttl, lambda: _compute_dashboard_kpi(db))


@router.get("/heatmap", response_model=schemas.DashboardHeatmapResponse)
async def get_dashboard_heatmap(db: Session = Depends(get_db)):
    """
    商圈热力：展示热度为按 raw 全局排名映射（第 1 名 100，依次减 1，最低 20）；取点前按 raw 降序。
    """
    import hashlib

    rows = _trade_area_heat_rows(db)
    if not rows:
        return schemas.DashboardHeatmapResponse(
            data=[],
            series_note="无 listings 聚合结果，热力图为空。",
        )

    def _has_coords(r: dict) -> bool:
        lng, lat = r.get("avg_longitude"), r.get("avg_latitude")
        return lng is not None and lat is not None

    longitudes = [float(r["avg_longitude"]) for r in rows if _has_coords(r)]
    latitudes = [float(r["avg_latitude"]) for r in rows if _has_coords(r)]

    rows_by_raw = sorted(rows, key=_heat_row_sort_key)

    if not longitudes or not latitudes:
        fallback: list = []
        for row in rows_by_raw[:20]:
            name = row["name"]
            h = hashlib.md5(name.encode("utf-8")).hexdigest()
            x = 10 + int(h[:2], 16) % 80 + int(h[4:6], 16) / 255.0
            y = 10 + int(h[2:4], 16) % 80 + int(h[6:8], 16) / 255.0
            fallback.append(
                schemas.HeatmapPoint(
                    name=name,
                    x=round(min(100.0, x), 2),
                    y=round(min(100.0, y), 2),
                    value=row["heat"],
                )
            )
        return schemas.DashboardHeatmapResponse(
            data=fallback,
            series_note=(
                "当前样本缺少有效经纬度，点为按区域名称哈希的占位坐标；"
                "热度为按 raw 全局排名映射到 20–100（与「热门商圈」一致），非真实地图投影。"
            ),
        )

    min_lng = float(min(longitudes))
    max_lng = float(max(longitudes))
    min_lat = float(min(latitudes))
    max_lat = float(max(latitudes))

    lng_range = max_lng - min_lng if max_lng != min_lng else 1.0
    lat_range = max_lat - min_lat if max_lat != min_lat else 1.0

    heatmap_data: list = []
    used_positions: dict = {}

    coords_sorted = sorted(
        [r for r in rows if _has_coords(r)],
        key=_heat_row_sort_key,
    )

    for row in coords_sorted[:20]:
        r_lng = float(row["avg_longitude"])
        r_lat = float(row["avg_latitude"])
        x = float(round(((r_lng - min_lng) / lng_range) * 80 + 10, 1))
        y = float(round(((r_lat - min_lat) / lat_range) * 80 + 10, 1))

        pos_key = (x, y)
        if pos_key in used_positions:
            offset = used_positions[pos_key] * 2.5
            x = min(100.0, x + offset)
            used_positions[pos_key] += 1
        else:
            used_positions[pos_key] = 1

        xf = round(max(0.0, min(100.0, x)), 1)
        yf = round(max(0.0, min(100.0, y)), 1)

        heatmap_data.append(
            schemas.HeatmapPoint(
                name=row["name"],
                x=xf,
                y=yf,
                value=row["heat"],
            )
        )

    return schemas.DashboardHeatmapResponse(
        data=heatmap_data,
        series_note=(
            "热度为按 raw（log 供给+评分+log 收藏）全局排名映射到 20–100，"
            "与「热门商圈榜单」共用同一批数据；坐标由经纬度均值映射到展示网格。"
        ),
    )


@router.get("/top-districts", response_model=schemas.DashboardTopDistrictsResponse)
async def get_top_districts(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    热门商圈榜单。按 raw 降序（并列看房源数、名称）；heat 为全局名次映射 20–100（第 1 名 100，依次减 1）。
    price_trend 为相对全市均价的溢价率（%），非时间序列环比。
    """
    from app.db.database import Listing

    city_avg_result = db.query(func.avg(Listing.final_price)).scalar()
    city_avg = float(city_avg_result) if city_avg_result else 0.0

    rows = _trade_area_heat_rows(db)
    if not rows:
        return schemas.DashboardTopDistrictsResponse(items=[])

    district_items = []
    for row in sorted(rows, key=_heat_row_sort_key):
        avg_price = row["avg_price"]
        listing_count = row["listing_count"]
        if city_avg > 0:
            price_trend = round((avg_price - city_avg) / city_avg * 100, 1)
        else:
            price_trend = 0.0

        district_items.append({
            "name": row["name"],
            "heat": row["heat"],
            "avg_price": round(avg_price, 1),
            "price_trend": price_trend,
            "listing_count": listing_count,
        })

    return schemas.DashboardTopDistrictsResponse(items=[
        schemas.TopDistrictItem(
            name=item["name"],
            heat=item["heat"],
            avg_price=item["avg_price"],
            price_trend=item["price_trend"],
            listing_count=item["listing_count"],
        ) for item in district_items[:limit]
    ])


@router.get("/trends")
async def get_dashboard_trends(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    db: Session = Depends(get_db)
):
    """
    平台价格趋势：优先价格日历日均价；occupancy_rates 为当日可订比例映射的「供给可得性指数」。
    无日历数据时返回常数序列（基于 listings 截面），不含随机波动。
    """
    from app.db.database import Listing, PriceCalendar

    today = datetime.now()
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        results = db.query(
            PriceCalendar.date,
            func.avg(PriceCalendar.price).label('avg_price'),
            func.count(PriceCalendar.unit_id).label('listing_count'),
            func.avg(PriceCalendar.can_booking).label('book_ratio'),
        ).filter(
            PriceCalendar.date >= start_date
        ).group_by(
            PriceCalendar.date
        ).order_by(
            PriceCalendar.date
        ).all()

        if results:
            dates = [r.date for r in results]
            prices = [round(float(r.avg_price), 2) for r in results]
            listing_counts = [r.listing_count for r in results]
            occupancy_rates = []
            for r in results:
                br = float(r.book_ratio) if r.book_ratio is not None else 1.0
                # 可订比例 0~1 -> 45~88 的展示指数
                idx = 45.0 + max(0.0, min(1.0, br)) * 43.0
                occupancy_rates.append(round(idx, 1))

            return {
                "dates": dates,
                "prices": prices,
                "listing_counts": listing_counts,
                "occupancy_rates": occupancy_rates,
                "series_note": "occupancy_rates 为日历可订率映射指数，非真实入住率",
            }
    except Exception as e:
        logger.warning(f"Could not get trends from price_calendar: {e}")

    avg_price_result = db.query(func.avg(Listing.final_price)).scalar()
    base_price = float(avg_price_result) if avg_price_result else 250.0
    total_listings = db.query(Listing).count()
    avg_rating_result = db.query(func.avg(Listing.rating)).scalar()
    avg_rating = float(avg_rating_result) if avg_rating_result else 4.0
    avg_fav_result = db.query(func.avg(Listing.favorite_count)).scalar()
    avg_fav = float(avg_fav_result) if avg_fav_result else 0.0
    flat_occ = occupancy_proxy(avg_rating, avg_fav)

    dates = []
    prices = []
    listing_counts = []
    occupancy_rates = []

    for i in range(days):
        date = today - timedelta(days=days - i - 1)
        dates.append(date.strftime("%Y-%m-%d"))
        prices.append(round(base_price, 2))
        listing_counts.append(total_listings)
        occupancy_rates.append(flat_occ)

    return {
        "dates": dates,
        "prices": prices,
        "listing_counts": listing_counts,
        "occupancy_rates": occupancy_rates,
        "series_note": "无价格日历明细时为截面均价常数序列",
    }


@router.get("/alerts")
async def get_dashboard_alerts(
    db: Session = Depends(get_db)
):
    """
    基于 listings 聚合的预警（价格洼地、高性价比、高收藏行政区）。
    """
    from app.db.database import Listing
    from datetime import datetime

    alerts = []

    try:
        district_stats = db.query(
            Listing.district,
            func.avg(Listing.final_price).label('avg_price'),
            func.count(Listing.unit_id).label('count')
        ).filter(
            Listing.district.isnot(None)
        ).group_by(Listing.district).having(func.count(Listing.unit_id) > 10).all()

        if district_stats:
            prices = [float(s.avg_price or 0) for s in district_stats if s.avg_price]
            overall_avg = sum(prices) / len(prices) if prices else 0

            for stat in district_stats[:5]:
                if not stat.district or overall_avg <= 0:
                    continue
                avg_price = float(stat.avg_price or 0)
                if avg_price < overall_avg * 0.7 and stat.count >= 5:
                    alerts.append({
                        "type": "price_drop",
                        "title": f"{stat.district}价格洼地",
                        "message": (
                            f"{stat.district}均价{avg_price:.0f}元，低于样本均价"
                            f"{(1 - avg_price / overall_avg) * 100:.0f}%，可关注供给结构"
                        ),
                        "district": stat.district,
                        "severity": "medium",
                        "created_at": datetime.now().isoformat()
                    })
    except Exception as e:
        logger.warning(f"Could not analyze price anomalies: {e}")

    try:
        opportunities = db.query(Listing).filter(
            Listing.rating >= 4.5,
            Listing.final_price < 200
        ).limit(3).all()

        for listing in opportunities:
            alerts.append({
                "type": "high_opportunity",
                "title": "高性价比房源",
                "message": f"{listing.title[:20]}... 评分{listing.rating}，价格仅{listing.final_price}元",
                "district": listing.district,
                "unit_id": listing.unit_id,
                "severity": "low",
                "created_at": datetime.now().isoformat()
            })
    except Exception as e:
        logger.warning(f"Could not find opportunities: {e}")

    try:
        hot_districts = db.query(
            Listing.district,
            func.count(Listing.unit_id).label('count'),
            func.avg(Listing.favorite_count).label('avg_favorites')
        ).filter(
            Listing.district.isnot(None)
        ).group_by(Listing.district).order_by(
            desc(func.avg(Listing.favorite_count))
        ).limit(2).all()

        for row in hot_districts:
            if row.avg_favorites and float(row.avg_favorites) > 50:
                alerts.append({
                    "type": "price_surge",
                    "title": f"{row.district}热度较高",
                    "message": (
                        f"{row.district}平均收藏数{float(row.avg_favorites):.0f}，"
                        "反映平台侧关注度高（代理指标）"
                    ),
                    "district": row.district,
                    "severity": "low",
                    "created_at": datetime.now().isoformat()
                })
    except Exception as e:
        logger.warning(f"Could not analyze hot districts: {e}")

    return alerts[:5]
