#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard模块 API

KPI 中「入住率」「平台 ROI」为基于评分/收藏/供给的启发式代理指标，非订单口径。
"""
from __future__ import annotations

import logging
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


def _spread_heatmap_display_values(
    points: list[schemas.HeatmapPoint],
) -> list[schemas.HeatmapPoint]:
    """按当前顺序（已按原始热度降序）拉开 value，避免散点图「全是 100」。"""
    if not points:
        return []
    k = len(points)
    out: list[schemas.HeatmapPoint] = []
    for i, p in enumerate(points):
        if k <= 1:
            v = 80
        else:
            v = int(round(100 - i * (85 / (k - 1))))
        v = max(18, min(100, v))
        out.append(
            schemas.HeatmapPoint(name=p.name, x=p.x, y=p.y, value=v)
        )
    return out


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
    from app.db.database import Listing, PriceCalendar

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
        today = datetime.now()
        current_start = today.replace(day=1)
        prev_month_end = current_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        compare_day = min(today.day, calendar.monthrange(prev_month_end.year, prev_month_end.month)[1])
        prev_period_end = prev_month_start.replace(day=compare_day)

        def _period_avg(start_dt: datetime, end_dt: datetime) -> float:
            rows = (
                db.query(
                    PriceCalendar.date,
                    func.avg(PriceCalendar.price).label("daily_avg")
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

        current_avg = _period_avg(current_start, today)
        prev_avg = _period_avg(prev_month_start, prev_period_end)
        if prev_avg > 0:
            price_change_percent = round((current_avg - prev_avg) / prev_avg * 100, 1)
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
            "avg_roi": "市场吸引力指数（约5–26）：综合评分、收藏、供给等多因素的展示指数，非财务投资回报率。",
            "price_change_percent": "价格环比：价格日历中「本月1日至今日」与「上月同期」的日均价对比；无日历数据时为 0。",
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
    获取商圈热力图数据
    基于真实地理坐标映射到 0-100 的网格
    """
    from app.db.database import Listing

    results = db.query(
        Listing.district,
        Listing.trade_area,
        func.avg(Listing.longitude).label('avg_longitude'),
        func.avg(Listing.latitude).label('avg_latitude'),
        func.avg(Listing.final_price).label('avg_price'),
        func.count(Listing.unit_id).label('listing_count'),
        func.avg(Listing.rating).label('avg_rating'),
        func.avg(Listing.favorite_count).label('avg_favorites')
    ).group_by(Listing.district, Listing.trade_area).all()

    if not results:
        return schemas.DashboardHeatmapResponse(
            data=[],
            series_note="无 listings 聚合结果，热力图为空。",
        )

    longitudes = [r.avg_longitude for r in results if r.avg_longitude]
    latitudes = [r.avg_latitude for r in results if r.avg_latitude]

    if not longitudes or not latitudes:
        # 房源缺经纬度：按行政区/商圈名生成确定性网格占位，避免前端空白
        import hashlib

        fallback: list = []
        for r in results:
            name = (r.trade_area or r.district or "").strip() or "未知区域"
            h = hashlib.md5(name.encode("utf-8")).hexdigest()
            x = 10 + int(h[:2], 16) % 80 + int(h[4:6], 16) / 255.0
            y = 10 + int(h[2:4], 16) % 80 + int(h[6:8], 16) / 255.0
            listing_count = r.listing_count or 0
            avg_rating = float(r.avg_rating) if r.avg_rating else 0
            avg_favorites = float(r.avg_favorites) if r.avg_favorites else 0
            heat_score = (
                min(listing_count * 2, 40)
                + min(avg_rating * 8, 30)
                + min(avg_favorites * 0.5, 30)
            )
            value = int(min(100, max(20, heat_score)))
            fallback.append(
                schemas.HeatmapPoint(
                    name=name,
                    x=round(min(100.0, x), 2),
                    y=round(min(100.0, y), 2),
                    value=value,
                )
            )
        fallback.sort(key=lambda p: p.value, reverse=True)
        return schemas.DashboardHeatmapResponse(
            data=_spread_heatmap_display_values(fallback[:20]),
            series_note=(
                "当前样本缺少有效经纬度，热力点坐标为按区域名称哈希的占位网格，"
                "仅反映相对热度排序，非真实地图投影。"
            ),
        )

    min_lng = float(min(longitudes))
    max_lng = float(max(longitudes))
    min_lat = float(min(latitudes))
    max_lat = float(max(latitudes))

    lng_range = max_lng - min_lng if max_lng != min_lng else 1.0
    lat_range = max_lat - min_lat if max_lat != min_lat else 1.0

    heatmap_data = []
    used_positions = {}  # 记录已使用的位置，避免重叠

    for r in results:
        if not r.avg_longitude or not r.avg_latitude:
            continue

        # 提高精度，保留1位小数（SQL 聚合可能为 Decimal，统一 float 避免与 float 运算报错）
        x = float(
            round(
                ((float(r.avg_longitude) - min_lng) / lng_range) * 80 + 10,
                1,
            )
        )
        y = float(
            round(
                ((float(r.avg_latitude) - min_lat) / lat_range) * 80 + 10,
                1,
            )
        )

        # 处理位置重叠：如果位置已被使用，添加微小偏移（输出保留小数，避免 int 截断后多点重合）
        pos_key = (x, y)
        if pos_key in used_positions:
            offset = used_positions[pos_key] * 2.5
            x = min(100.0, x + offset)
            used_positions[pos_key] += 1
        else:
            used_positions[pos_key] = 1

        xf = round(max(0.0, min(100.0, x)), 1)
        yf = round(max(0.0, min(100.0, y)), 1)

        listing_count = r.listing_count or 0
        avg_rating = float(r.avg_rating) if r.avg_rating else 0
        avg_favorites = float(r.avg_favorites) if r.avg_favorites else 0

        heat_score = (
            min(listing_count * 2, 40)
            + min(avg_rating * 8, 30)
            + min(avg_favorites * 0.5, 30)
        )
        value = int(min(100, max(20, heat_score)))

        name = r.trade_area if r.trade_area else r.district

        heatmap_data.append(schemas.HeatmapPoint(
            name=name,
            x=xf,
            y=yf,
            value=value
        ))

    heatmap_data.sort(key=lambda x: x.value, reverse=True)

    return schemas.DashboardHeatmapResponse(
        data=_spread_heatmap_display_values(heatmap_data[:20]),
        series_note="坐标由 listings 中经纬度均值映射到 0–100 展示网格，点为商圈/商圈片聚合中心。",
    )


@router.get("/top-districts", response_model=schemas.DashboardTopDistrictsResponse)
async def get_top_districts(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    热门商圈排行。price_trend 为相对全市均价的溢价率（%），非时间序列环比。
    """
    from app.db.database import Listing

    city_avg_result = db.query(func.avg(Listing.final_price)).scalar()
    city_avg = float(city_avg_result) if city_avg_result else 0.0

    results = db.query(
        Listing.district,
        Listing.trade_area,
        func.avg(Listing.final_price).label('avg_price'),
        func.count(Listing.unit_id).label('listing_count'),
        func.avg(Listing.rating).label('avg_rating'),
        func.avg(Listing.favorite_count).label('avg_favorites'),
    ).group_by(Listing.district, Listing.trade_area).all()

    if not results:
        return schemas.DashboardTopDistrictsResponse(items=[])

    district_items = []
    raw_heat_scores = []  # 先收集所有原始分数

    for r in results:
        listing_count = r.listing_count or 0
        avg_price = float(r.avg_price or 0)
        avg_rating = float(r.avg_rating or 0)
        avg_favorites = float(r.avg_favorites or 0)

        # 计算原始热度分数
        raw_heat = (
            listing_count * 1.5
            + avg_rating * 10
            + avg_favorites * 0.3
        )
        raw_heat_scores.append(raw_heat)

        if city_avg > 0:
            price_trend = round((avg_price - city_avg) / city_avg * 100, 1)
        else:
            price_trend = 0.0

        name = r.trade_area if r.trade_area else r.district

        district_items.append({
            'name': name,
            'raw_heat': raw_heat,
            'avg_price': round(avg_price, 1),
            'price_trend': price_trend,
            'listing_count': listing_count
        })

    # 使用分位数归一化计算最终热度值
    sorted_scores = sorted(raw_heat_scores)
    n = len(sorted_scores)

    for item in district_items:
        raw = item['raw_heat']
        # 计算百分位排名（避免截断到100）
        rank = sum(1 for s in sorted_scores if s < raw)
        heat = int(rank / n * 100) if n > 0 else 50
        item['heat'] = heat

    district_items.sort(key=lambda x: x['heat'], reverse=True)

    return schemas.DashboardTopDistrictsResponse(items=[
        schemas.TopDistrictItem(
            name=item['name'],
            heat=item['heat'],
            avg_price=item['avg_price'],
            price_trend=item['price_trend'],
            listing_count=item['listing_count']
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
