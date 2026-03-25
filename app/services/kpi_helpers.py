# -*- coding: utf-8 -*-
"""
大屏与首页共用的 KPI 指标计算

注意：
- occupancy_proxy 和 market_return_index 是启发式代理指标，非真实业务数据
- calculate_occupancy_rate 和 calculate_roi 是基于数据库的真实计算函数
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.db.database import PriceCalendar, Listing
import numpy as np


# =============================================================================
# 启发式代理指标（保留用于向后兼容）
# =============================================================================

def demand_heat_index(avg_rating: float, avg_favorites: float) -> float:
    """
    需求热度指数（%）- 基于评分和收藏的启发式代理

    注意：这不是真实的入住率，仅作为需求热度的参考指标。

    Args:
        avg_rating: 平均评分 (0-5)
        avg_favorites: 平均收藏数

    Returns:
        热度指数 (50-92)
    """
    base = 52.0
    rating_part = (avg_rating / 5.0) * 24.0 if avg_rating else 0.0
    fav_part = min(avg_favorites * 0.07, 14.0)
    return round(max(50.0, min(92.0, base + rating_part + fav_part)), 1)


# 保留旧函数名作为别名，用于向后兼容
def occupancy_proxy(avg_rating: float, avg_favorites: float) -> float:
    """需求热度代理（%）- 保留用于向后兼容"""
    return demand_heat_index(avg_rating, avg_favorites)


def market_attractiveness_index(
    avg_price: float,
    occ_proxy: float,
    avg_rating: float,
    avg_favorites: float,
    total_listings: int,
) -> float:
    """
    市场吸引力指数（%）- 基于多因素的综合指数

    注意：这不是财务ROI，仅作为市场吸引力的参考指标。

    Args:
        avg_price: 平均价格
        occ_proxy: 入住率代理值
        avg_rating: 平均评分
        avg_favorites: 平均收藏数
        total_listings: 房源总数

    Returns:
        吸引力指数 (5-26)
    """
    if avg_price <= 0:
        return 10.0
    supply_factor = min(total_listings / 800.0, 1.0) * 6.0
    raw = (
        (avg_rating / 5.0) * 10.0
        + min(avg_favorites / 150.0, 1.0) * 7.0
        + (occ_proxy - 55.0) * 0.12
        + supply_factor
    )
    return round(max(5.0, min(26.0, 9.0 + raw)), 1)


# 保留旧函数名作为别名
def market_return_index(
    avg_price: float,
    occ_proxy: float,
    avg_rating: float,
    avg_favorites: float,
    total_listings: int,
) -> float:
    """综合回报展示指数（%）- 保留用于向后兼容"""
    return market_attractiveness_index(avg_price, occ_proxy, avg_rating, avg_favorites, total_listings)


# =============================================================================
# 真实计算函数（基于数据库）
# =============================================================================

def calculate_occupancy_rate(db: Session, district: str = None) -> float:
    """
    基于价格日历计算真实入住率代理

    逻辑：不可预订日期占比（can_booking=0 表示已被预订）

    Args:
        db: 数据库会话
        district: 商圈名称，为None时统计全市

    Returns:
        入住率百分比 (0-100)
    """
    query = db.query(
        func.count(PriceCalendar.id).label('total'),
        func.sum(case(
            (PriceCalendar.can_booking == 0, 1),
            else_=0
        )).label('booked')
    )

    if district:
        query = query.join(
            Listing,
            PriceCalendar.unit_id == Listing.unit_id
        ).filter(Listing.district == district)

    result = query.first()

    if not result or result.total == 0 or result.total is None:
        return 0.0

    occupancy = (result.booked or 0) / result.total * 100
    return round(occupancy, 1)


def calculate_roi(db: Session, district: str) -> dict:
    """
    计算投资回报率

    公式：年化收益率 = (年收入 - 年成本) / 投资成本

    Args:
        db: 数据库会话
        district: 商圈名称

    Returns:
        ROI详细数据字典
    """
    # 获取商圈均价
    stats = db.query(
        func.avg(Listing.final_price).label('avg_price'),
        func.count(Listing.id).label('count')
    ).filter(Listing.district == district).first()

    if not stats or stats.avg_price is None:
        return {
            "roi_percent": 0,
            "annual_revenue": 0,
            "annual_cost": 0,
            "investment_cost": 0,
            "occupancy_rate": 0,
            "avg_daily_price": 0
        }

    avg_price = float(stats.avg_price)

    # 获取入住率
    occupancy = calculate_occupancy_rate(db, district) / 100

    # 计算年度数据
    annual_revenue = avg_price * occupancy * 365
    operating_cost_rate = 0.20  # 运营成本占比
    annual_cost = annual_revenue * operating_cost_rate
    investment_cost = avg_price * 100  # 投资成本假设

    roi_percent = (annual_revenue - annual_cost) / investment_cost * 100 if investment_cost > 0 else 0

    return {
        "roi_percent": round(roi_percent, 2),
        "annual_revenue": round(annual_revenue, 2),
        "annual_cost": round(annual_cost, 2),
        "investment_cost": round(investment_cost, 2),
        "occupancy_rate": round(occupancy * 100, 1),
        "avg_daily_price": round(avg_price, 2)
    }
