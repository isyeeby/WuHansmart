"""
溢价因子统计服务

从价格日历数据统计真实的溢价因子：
- 周末/工作日溢价
- 季节性溢价（按月）
- 节假日溢价（可选）
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import numpy as np
from sqlalchemy import func, extract, case, literal_column
from sqlalchemy.orm import Session

from app.db.database import PriceCalendar, Listing

logger = logging.getLogger(__name__)


def calculate_premium_factors(db: Session, district: str = None) -> dict:
    """
    从价格日历统计真实溢价因子

    Args:
        db: 数据库会话
        district: 商圈名称，为None时统计全市

    Returns:
        {
            "weekend": 周末溢价因子,
            "holiday": 节假日溢价因子,
            "seasonal": {月份: 溢价因子},
            "is_default": 是否使用默认值,
            "sample_count": 样本数量
        }
    """
    # 构建基础查询
    query = db.query(
        PriceCalendar.date,
        PriceCalendar.price
    )

    # 如果指定商圈，需要JOIN listings表
    if district:
        query = query.join(
            Listing,
            PriceCalendar.unit_id == Listing.unit_id
        ).filter(Listing.district == district)

    # 获取价格日历数据
    records = query.limit(20000).all()

    if not records or len(records) < 30:
        # 数据不足时返回默认值
        logger.warning(f"价格日历数据不足({len(records) if records else 0}条)，使用默认溢价因子")
        return {
            "weekend": 1.15,
            "holiday": 1.25,
            "seasonal": _get_default_seasonal_factors(),
            "is_default": True,
            "sample_count": len(records) if records else 0
        }

    # 解析日期并分类统计
    weekday_prices = []  # 工作日价格
    weekend_prices = []  # 周末价格
    monthly_prices = defaultdict(list)  # 月度价格

    for record in records:
        if record.price is None:
            continue

        price = float(record.price)

        # 解析日期
        try:
            if isinstance(record.date, str):
                date_obj = datetime.strptime(record.date, "%Y-%m-%d")
            else:
                date_obj = record.date
        except (ValueError, TypeError):
            continue

        # 判断周末 (周六=5, 周日=6)
        weekday = date_obj.weekday()
        if weekday >= 5:  # 周末
            weekend_prices.append(price)
        else:  # 工作日
            weekday_prices.append(price)

        # 按月统计
        month = date_obj.month
        monthly_prices[month].append(price)

    # 计算周末溢价
    weekend_premium = 1.0
    if weekday_prices and weekend_prices:
        avg_weekday = np.mean(weekday_prices)
        avg_weekend = np.mean(weekend_prices)
        if avg_weekday > 0:
            weekend_premium = round(avg_weekend / avg_weekday, 2)

    # 计算季节性溢价
    all_prices = weekday_prices + weekend_prices
    overall_avg = np.mean(all_prices) if all_prices else 1

    seasonal_factors = {}
    for month, prices in monthly_prices.items():
        if prices and overall_avg > 0:
            month_avg = np.mean(prices)
            seasonal_factors[month] = round(month_avg / overall_avg, 2)

    # 如果某些月份没有数据，填充默认值
    for month in range(1, 13):
        if month not in seasonal_factors:
            seasonal_factors[month] = 1.0

    return {
        "weekend": weekend_premium,
        "holiday": 1.25,  # 节假日溢价需要节假日表，暂用默认值
        "seasonal": seasonal_factors,
        "is_default": False,
        "sample_count": len(all_prices)
    }


def _get_default_seasonal_factors() -> Dict[int, float]:
    """获取默认季节性溢价因子"""
    return {
        1: 1.20,   # 春节
        2: 1.15,   # 春节后
        3: 1.00,   # 淡季
        4: 1.00,   # 淡季
        5: 1.05,   # 五一
        6: 1.00,   # 淡季
        7: 1.15,   # 暑期
        8: 1.15,   # 暑期
        9: 1.00,   # 淡季
        10: 1.18,  # 国庆
        11: 1.00,  # 淡季
        12: 1.05   # 年末
    }


def get_seasonal_factor(db: Session, date: datetime, district: str = None) -> float:
    """
    获取指定日期的季节性因子

    Args:
        db: 数据库会话
        date: 目标日期
        district: 商圈名称

    Returns:
        季节性溢价因子
    """
    factors = calculate_premium_factors(db, district)

    if factors.get("is_default"):
        # 使用默认季节性规则
        return _get_default_seasonal_factors().get(date.month, 1.0)

    seasonal = factors.get("seasonal", {})
    return seasonal.get(date.month, 1.0)


def get_weekend_premium(db: Session, district: str = None) -> float:
    """
    获取周末溢价因子

    Args:
        db: 数据库会话
        district: 商圈名称

    Returns:
        周末溢价因子
    """
    factors = calculate_premium_factors(db, district)
    return factors.get("weekend", 1.15)


def calculate_occupancy_rate(db: Session, district: str = None) -> float:
    """
    基于价格日历计算入住率代理

    逻辑：不可预订日期占比（can_booking=0 表示已被预订）

    Args:
        db: 数据库会话
        district: 商圈名称

    Returns:
        入住率百分比 (0-100)
    """
    # 构建查询
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
        {
            "roi_percent": 年化收益率,
            "annual_revenue": 年收入,
            "annual_cost": 年成本,
            "investment_cost": 投资成本,
            "occupancy_rate": 入住率,
            "avg_daily_price": 日均价格
        }
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
    # 年收入 = 日均价格 * 入住率 * 365
    annual_revenue = avg_price * occupancy * 365

    # 运营成本占比（可配置，假设20%）
    operating_cost_rate = 0.20
    annual_cost = annual_revenue * operating_cost_rate

    # 投资成本假设：日均价格 * 100（约等于年租金等价）
    investment_cost = avg_price * 100

    # ROI计算
    roi_percent = (annual_revenue - annual_cost) / investment_cost * 100 if investment_cost > 0 else 0

    return {
        "roi_percent": round(roi_percent, 2),
        "annual_revenue": round(annual_revenue, 2),
        "annual_cost": round(annual_cost, 2),
        "investment_cost": round(investment_cost, 2),
        "occupancy_rate": round(occupancy * 100, 1),
        "avg_daily_price": round(avg_price, 2)
    }