"""
竞品情报服务 - 监测、雷达图、经营诊断
"""
from typing import List, Optional
from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.services.hive_service import hive_service
from app.db.database import get_db, Listing
from app.core.security import get_current_user_id as get_current_user
import numpy as np

router = APIRouter()


def _get_district_baselines(db: Session, district: str) -> dict:
    """
    从数据库计算商圈真实基准线

    Returns:
        {
            "avg_values": [价格分, 评分分, 热度分, 设施分, 面积分],
            "best_values": [价格分, 评分分, 热度分, 设施分, 面积分]
        }
    """
    # 查询同商圈所有房源
    listings = db.query(Listing).filter(Listing.district == district).limit(500).all()

    if not listings:
        # 无数据时返回默认基准
        return {
            "avg_values": [50, 50, 50, 50, 50],
            "best_values": [70, 70, 70, 70, 70]
        }

    # 收集各维度数据
    prices = [float(l.final_price) for l in listings if l.final_price]
    ratings = [float(l.rating) for l in listings if l.rating]
    favorites = [int(l.favorite_count) for l in listings if l.favorite_count]
    # 设施数量从house_tags解析
    facility_counts = []
    for l in listings:
        if l.house_tags:
            # 简单统计标签数量作为设施代理
            facility_counts.append(len(l.house_tags.split(',')) if isinstance(l.house_tags, str) else 0)
        else:
            facility_counts.append(0)

    # 面积数据（可能没有，用默认值）
    areas = [float(l.area) if l.area else 50 for l in listings]

    # 计算各维度平均值和最佳值
    def calc_stats(values, reverse=False):
        if not values:
            return 50, 70
        avg = np.mean(values)
        best = np.max(values) if not reverse else np.min(values)
        max_val = max(values) if values else 1
        # 归一化到0-100
        avg_score = min(100, (avg / max_val) * 100) if max_val > 0 else 50
        best_score = min(100, (best / max_val) * 100) if max_val > 0 else 70
        return round(avg_score, 1), round(best_score, 1)

    # 价格（越低越好，reverse=True）
    price_avg, price_best = calc_stats(prices, reverse=True) if prices else (50, 70)
    # 评分
    rating_avg, rating_best = calc_stats(ratings) if ratings else (50, 70)
    # 热度（收藏数）
    heat_avg, heat_best = calc_stats(favorites) if favorites else (50, 70)
    # 设施
    facility_avg, facility_best = calc_stats(facility_counts) if facility_counts else (50, 70)
    # 面积
    area_avg, area_best = calc_stats(areas) if areas else (50, 70)

    return {
        "avg_values": [price_avg, rating_avg, heat_avg, facility_avg, area_avg],
        "best_values": [price_best, rating_best, heat_best, facility_best, area_best]
    }


@router.get("/monitoring/{my_listing_id}")
def get_competitor_monitoring(
    my_listing_id: str,
    radius: float = Query(
        1.0,
        ge=0.5,
        le=5.0,
        description="预留参数；当前实现为同行政区竞品，未按球面距离过滤",
    )
):
    """
    竞品监测列表。

    路径参数 ``my_listing_id`` 须为**平台房源 unit_id**（与途家房源 ID 一致），
    非「我的房源」表自增主键。实现上按同 district 拉取可比房源并按价差排序。
    """
    # 获取我的房源信息
    my_listing = hive_service.get_listing_detail(my_listing_id)
    
    if not my_listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房源不存在")

    district = my_listing.get('district')
    my_price = my_listing.get('price', 0)
    
    # 获取同商圈房源作为竞品
    competitors = hive_service.get_listings_by_district(district, limit=20)
    
    # 过滤掉自己，并按价格相近排序
    competitors = [c for c in competitors if c.get('unit_id') != my_listing_id]
    competitors.sort(key=lambda x: abs(x.get('price', 0) - my_price))
    
    result = []
    for i, comp in enumerate(competitors[:10], 1):
        comp_price = comp.get('price', 0)
        price_diff = ((comp_price - my_price) / my_price * 100) if my_price > 0 else 0

        # 处理标签数据
        house_tags = comp.get('house_tags', '')
        tag_list = []
        if house_tags:
            try:
                import json
                tags_data = json.loads(house_tags)
                if isinstance(tags_data, list):
                    for tag_item in tags_data:
                        if isinstance(tag_item, dict):
                            if 'text' in tag_item:
                                tag_list.append(tag_item['text'])
                            elif 'tagText' in tag_item and isinstance(tag_item['tagText'], dict):
                                tag_list.append(tag_item['tagText'].get('text', ''))
            except (json.JSONDecodeError, TypeError):
                if isinstance(house_tags, str):
                    tag_list = [t.strip() for t in house_tags.split(',') if t.strip()]

        result.append({
            "rank": i,
            "unit_id": comp.get('unit_id'),
            "district": comp.get('district'),
            "price": comp_price,
            "price_diff_percent": round(price_diff, 2),
            "rating": comp.get('rating', 0),
            "comment_count": comp.get('comment_count', 0),
            "heat_score": comp.get('heat_score', 0),
            "bedroom_count": comp.get('bedroom_count', 0),
            "area_sqm": comp.get('area_sqm', 0),
            "facility_count": comp.get('facility_count', 0),
            "house_tags": house_tags,
            "tag_list": tag_list
        })
    
    return {
        "my_listing_id": my_listing_id,
        "my_price": my_price,
        "district": district,
        "competitor_count": len(result),
        "competitors": result
    }


@router.get("/radar/{my_listing_id}")
def get_competitiveness_radar(
    my_listing_id: str,
    db: Session = Depends(get_db)
):
    """
    竞争力雷达图数据
    多维度对比我的房源与商圈平均水平
    """
    # 获取我的房源
    my_listing = hive_service.get_listing_detail(my_listing_id)

    if not my_listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房源不存在")

    district = my_listing.get('district')

    # 从数据库获取商圈真实基准线
    baselines = _get_district_baselines(db, district)

    # 获取商圈统计（用于原始值显示）
    district_stats = hive_service.get_district_stats(limit=100)
    district_avg = next((d for d in district_stats if d.get('district') == district), {})

    # 构建雷达图数据
    radar_data = {
        "dimensions": ["价格", "评分", "热度", "设施", "面积"],
        "my_listing": {
            "name": "我的房源",
            "values": [
                normalize_score(my_listing.get('price', 0), district_avg.get('avg_price', 1), reverse=True),
                normalize_score(my_listing.get('rating', 0), 5.0),
                normalize_score(my_listing.get('heat_score', 0), 100),
                normalize_score(my_listing.get('facility_count', 0), 10),
                normalize_score(my_listing.get('area_sqm', 0), 100)
            ]
        },
        "district_average": {
            "name": "商圈平均",
            "values": baselines["avg_values"]  # 真实商圈平均基准
        },
        "district_best": {
            "name": "商圈最佳",
            "values": baselines["best_values"]  # 真实商圈最佳基准
        }
    }
    
    return {
        "my_listing_id": my_listing_id,
        "district": district,
        "radar_data": radar_data,
        "raw_values": {
            "my_price": my_listing.get('price', 0),
            "avg_price": district_avg.get('avg_price', 0),
            "my_rating": my_listing.get('rating', 0),
            "avg_rating": district_avg.get('avg_rating', 0)
        }
    }


def normalize_score(value, max_value, reverse=False):
    """标准化分数到0-100"""
    if max_value == 0:
        return 50
    score = (value / max_value) * 100
    if reverse:
        score = 100 - score  # 价格越低越好
    return min(100, max(0, round(score, 1)))


@router.get("/diagnosis/{my_listing_id}")
def get_business_diagnosis(
    my_listing_id: str
):
    """
    经营诊断建议
    分析房源优劣势并给出优化建议
    """
    # 获取我的房源和竞品
    my_listing = hive_service.get_listing_detail(my_listing_id)
    
    if not my_listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房源不存在")

    district = my_listing.get('district')
    district_stats = hive_service.get_district_stats(limit=100)
    district_avg = next((d for d in district_stats if d.get('district') == district), {})
    
    my_price = my_listing.get('price', 0)
    avg_price = district_avg.get('avg_price', 0)
    my_rating = my_listing.get('rating', 0)
    avg_rating = district_avg.get('avg_rating', 0)
    
    # 生成诊断
    strengths = []
    weaknesses = []
    suggestions = []
    
    # 价格诊断
    if my_price < avg_price * 0.9:
        strengths.append("价格具有竞争力，低于商圈均价")
    elif my_price > avg_price * 1.1:
        weaknesses.append("价格偏高，高于商圈均价")
        suggestions.append("建议适当降价或提升设施/服务品质以支撑价格")
    else:
        strengths.append("定价合理，符合商圈水平")
    
    # 评分诊断
    if my_rating >= 4.7:
        strengths.append("评分优秀，用户满意度高")
    elif my_rating < 4.5:
        weaknesses.append("评分偏低，存在改进空间")
        suggestions.append("关注用户评价，改善卫生、设施或服务态度")
    
    # 设施诊断
    my_facilities = my_listing.get('facility_count', 0)
    if my_facilities >= 8:
        strengths.append("设施配置完善")
    elif my_facilities < 5:
        weaknesses.append("设施配置较少")
        suggestions.append("考虑增加投影、智能锁等热门设施提升竞争力")
    
    overall, breakdown = compute_overall_score_detail(my_listing, district_avg)
    return {
        "my_listing_id": my_listing_id,
        "district": district,
        "overall_score": overall,
        "grade": calculate_grade_from_score(overall),
        "score_breakdown": breakdown,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "priority_actions": suggestions[:3] if suggestions else ["保持当前运营状态"],
    }


def compute_overall_score_detail(listing, district_avg):
    """
    综合得分 + 分项；价格带区分「显著低于 / 合理带 / 溢价 / 显著高于」均价。
    """
    ap = float(district_avg.get("avg_price") or 0)
    price = float(listing.get("price") or 0)
    price_ratio = (price / ap) if ap > 0 else 1.0

    if 0.9 <= price_ratio <= 1.1:
        price_score = 85
        price_note = "价格接近商圈均价的合理带"
    elif price_ratio < 0.8:
        price_score = 78
        price_note = "价格显著低于商圈均价（性价比向）"
    elif price_ratio < 0.9:
        price_score = 75
        price_note = "价格略低于商圈均价"
    elif price_ratio <= 1.15:
        price_score = 58
        price_note = "价格高于商圈均价（溢价向，需差异化支撑）"
    else:
        price_score = 45
        price_note = "价格显著高于商圈均价（溢价风险）"

    rating = float(listing.get("rating") or 0)
    rating_score = min(100, rating * 20)

    heat = float(listing.get("heat_score") or 0)
    heat_score = min(100, heat)

    overall = round((price_score + rating_score + heat_score) / 3, 1)
    breakdown = {
        "price_score": price_score,
        "rating_score": round(rating_score, 1),
        "heat_score": round(heat_score, 1),
        "price_ratio_vs_district_avg": round(price_ratio, 3),
        "price_band_note": price_note,
    }
    return overall, breakdown


def calculate_overall_score(listing, district_avg):
    """计算综合得分（兼容旧调用）。"""
    return compute_overall_score_detail(listing, district_avg)[0]


def calculate_grade_from_score(score: float) -> str:
    """由分数计算等级。"""
    if score >= 90:
        return "S"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    else:
        return "D"


def calculate_grade(listing, district_avg):
    """计算等级"""
    return calculate_grade_from_score(calculate_overall_score(listing, district_avg))


@router.get("/alerts/{my_listing_id}")
def get_competitor_alerts(
    my_listing_id: str,
    days: int = Query(7, ge=1, le=30, description="最近N天"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    竞品动态预警（从数据库获取）
    """
    from app.db.database import get_user_alerts
    
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    
    # 根据用户名获取用户ID
    from app.db.database import get_user_by_username
    user = get_user_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_id = user.id
    
    # 从数据库获取真实预警数据
    alerts = get_user_alerts(db, user_id, is_read=False, limit=10)
    
    # 转换为响应格式
    alert_list = []
    for alert in alerts:
        alert_list.append({
            "type": alert.alert_type,
            "level": "warning" if alert.alert_type == "price_change" else "info",
            "message": alert.alert_title,
            "detail": alert.alert_detail,
            "date": alert.created_at.strftime("%Y-%m-%d") if alert.created_at else ""
        })
    
    return {
        "my_listing_id": my_listing_id,
        "alert_count": len(alert_list),
        "alerts": alert_list
    }


@router.post("/add-monitor")
def add_competitor_monitor(
    my_listing_id: str,
    competitor_id: str
):
    """
    手动添加竞品监测
    """
    return {
        "success": True,
        "message": "已添加竞品监测",
        "my_listing_id": my_listing_id,
        "competitor_id": competitor_id
    }
