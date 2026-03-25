"""
房源对比服务 - 多房源对比、雷达图、性价比评分
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.services.hive_service import hive_service
from app.db.database import get_db
from app.core.security import get_current_user_id as get_current_user

router = APIRouter()


class ComparisonRequest(BaseModel):
    """对比请求"""
    unit_ids: List[str]  # 要对比的房源ID列表
    comparison_type: str = "full"  # 对比类型: full/price/facility/location


class CompareListingScores(BaseModel):
    """房源各维度评分

    评分说明：
    - price: 价格优势分，价格越低得分越高
    - location: 位置便利分，基于评分作为商圈热度代理
    - facility: 设施完备分，设施数量越多得分越高
    - rating: 评分口碑分，评分越高得分越高
    - size: 面积大小分，面积越大得分越高
    """
    price: int      # 价格优势分 0-100，价格越低得分越高
    location: int   # 位置便利分 0-100，基于评分作为商圈热度代理
    facility: int   # 设施完备分 0-100，设施数量越多得分越高
    rating: int     # 评分口碑分 0-100，评分越高得分越高
    size: int       # 面积大小分 0-100，面积越大得分越高


class CompareListingResponse(BaseModel):
    """对比房源详情响应

    性价比(value_score)计算说明：
    性价比 = (评分 × 面积 × (1 + 设施数 × 0.1)) / 价格 × 10
    综合考虑房源质量(评分)、空间大小(面积)、设施配置(设施数)与成本(价格)的比值
    """
    unit_id: str
    title: str
    price: float
    rating: float
    total_reviews: int
    district: str
    bedrooms: int
    bathrooms: int
    area: Optional[float]
    image_url: Optional[str]
    facilities: List[str]
    scores: CompareListingScores
    value_score: int  # 综合性价比分 0-100，计算公式见上方说明


@router.post("/")
def compare_listings(request: ComparisonRequest):
    """
    房源对比
    对比多个房源的多维度指标

    评分逻辑：
    1. 各维度评分基于对比房源集合的区间归一化计算
    2. 价格评分：越低越好，使用反转归一化
    3. 其他评分：越高越好，使用正向归一化
    4. 综合性价比：综合考虑评分、面积、设施与价格的比值

    计算公式：
    - 价格分 = 100 - ((价格 - 最低价) / (最高价 - 最低价)) × 100
    - 评分分 = ((评分 - 最低分) / (最高分 - 最低分)) × 100
    - 面积分 = ((面积 - 最小面积) / (最大面积 - 最小面积)) × 100
    - 设施分 = ((设施数 - 最少设施) / (最多设施 - 最少设施)) × 100
    - 性价比 = (评分 × 面积 × (1 + 设施数 × 0.1)) / 价格 × 10
    """
    if len(request.unit_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要选择2个房源进行对比",
        )

    if len(request.unit_ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="最多只能对比5个房源",
        )
    
    # 获取房源详情
    listings = []
    for unit_id in request.unit_ids:
        listing = hive_service.get_listing_detail(unit_id)
        if listing:
            listings.append(listing)
    
    if len(listings) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="有效房源不足，无法对比",
        )
    
    # 构建对比数据
    comparison_result = {
        "unit_ids": request.unit_ids,
        "comparison_type": request.comparison_type,
        "listings": [],
        "summary": {},
        "radar_chart": generate_radar_chart(listings),
        "winner": determine_winner(listings),
        "scoring_methodology": {
            "description": "各维度评分以本次选中的房源集合为基线做区间归一化：价格反向归一化，其它维度正向归一化；分数只用于本次对比，不代表全市绝对排名。",
            "price_score": {
                "description": "价格优势分",
                "calculation": "100 - ((价格 - 最低价) / (最高价 - 最低价)) × 100",
                "note": "价格越低得分越高"
            },
            "rating_score": {
                "description": "评分口碑分",
                "calculation": "((评分 - 最低分) / (最高分 - 最低分)) × 100",
                "note": "评分越高得分越高"
            },
            "size_score": {
                "description": "空间大小分",
                "calculation": "((面积 - 最小面积) / (最大面积 - 最小面积)) × 100",
                "note": "面积越大得分越高"
            },
            "facility_score": {
                "description": "设施完备分",
                "calculation": "((设施数 - 最少设施) / (最多设施 - 最少设施)) × 100",
                "note": "设施越多得分越高"
            },
            "location_score": {
                "description": "位置便利分",
                "note": "基于评分口碑分作为商圈热度代理"
            },
            "value_score": {
                "description": "综合性价比分",
                "calculation": "(评分 × 面积 × (1 + 设施数 × 0.1)) / 价格 × 10",
                "note": "综合考虑质量、面积、设施与价格的比值，标准化到0-100"
            }
        }
    }
    
    # 计算所有房源的统计数据用于评分
    all_prices = [l.get('price', 0) for l in listings]
    all_ratings = [l.get('rating', 0) for l in listings]
    all_areas = [l.get('area_sqm', 0) or 0 for l in listings]
    all_facilities = [l.get('facility_count', 0) for l in listings]
    
    min_price, max_price = min(all_prices), max(all_prices)
    min_rating, max_rating = min(all_ratings), max(all_ratings)
    min_area, max_area = min(all_areas), max(all_areas)
    min_facility, max_facility = min(all_facilities), max(all_facilities)
    
    # 每个房源的详细数据
    for listing in listings:
        # 计算各维度评分
        scores = calculate_listing_scores(
            listing, 
            min_price, max_price,
            min_rating, max_rating,
            min_area, max_area,
            min_facility, max_facility
        )
        
        # 提取设施列表
        facilities = []
        facility_mapping = {
            'has_projector': '投影',
            'has_kitchen': '厨房',
            'has_washer': '洗衣机',
            'has_aircon': '空调',
            'has_wifi': 'WiFi',
            'has_tv': '电视',
            'has_bathtub': '浴缸',
            'has_balcony': '阳台',
            'has_parking': '停车位',
            'has_elevator': '电梯',
            'has_smart_lock': '智能门锁',
            'has_floor_window': '落地窗',
            'has_mahjong': '麻将桌'
        }
        for key, name in facility_mapping.items():
            if listing.get(key):
                facilities.append(name)
        
        comparison_result["listings"].append({
            "unit_id": str(listing.get('unit_id')),
            "title": listing.get('title', ''),
            "price": listing.get('price', 0),
            "rating": listing.get('rating', 0),
            "total_reviews": listing.get('comment_count', 0),
            "district": listing.get('district', ''),
            "bedrooms": listing.get('bedroom_count', 0),
            "bathrooms": listing.get('bathroom_count', 0),
            "area": listing.get('area_sqm'),
            "image_url": listing.get('cover_image'),
            "facilities": facilities,
            "scores": scores,
            "value_score": calculate_value_score(listing)
        })
    
    # 汇总统计
    prices = [l.get('price', 0) for l in listings]
    ratings = [l.get('rating', 0) for l in listings]
    areas = [l.get('area_sqm', 0) for l in listings]
    
    comparison_result["summary"] = {
        "price_range": {
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices), 2)
        },
        "rating_range": {
            "min": min(ratings),
            "max": max(ratings),
            "avg": round(sum(ratings) / len(ratings), 2)
        },
        "area_range": {
            "min": min(areas),
            "max": max(areas),
            "avg": round(sum(areas) / len(areas), 2)
        }
    }
    
    return comparison_result


def generate_radar_chart(listings):
    """生成雷达图数据"""
    dimensions = ["价格性价比", "评分口碑", "空间大小", "地理位置", "设施配套"]
    
    # 找出最大值用于标准化
    max_price = max(l.get('price', 1) for l in listings)
    max_rating = 5.0
    max_area = max(l.get('area_sqm', 1) for l in listings)
    max_heat = max(l.get('heat_score', 0) or 0 for l in listings) or 100
    max_facility = max(l.get('facility_count', 0) for l in listings) or 10
    
    datasets = []
    for listing in listings:
        # 提取简短名称（取标题前 10 个字）
        title = listing.get('title', '')
        short_name = title[:10] + '...' if len(title) > 10 else title
        
        values = [
            100 - (listing.get('price', 0) / max_price * 100),  # 价格越低越好
            (listing.get('rating', 0) / max_rating * 100),
            (listing.get('area_sqm', 0) / max_area * 100),
            (listing.get('heat_score', 0) or 0) / max_heat * 100,  # 热度/收藏数
            (listing.get('facility_count', 0) / max_facility * 100)
        ]
        
        datasets.append({
            "name": short_name,
            "values": [round(v, 1) for v in values]
        })
    
    return {
        "dimensions": dimensions,
        "datasets": datasets
    }


def calculate_listing_scores(listing, min_price, max_price, min_rating, max_rating, 
                              min_area, max_area, min_facility, max_facility):
    """计算房源各维度评分 (0-100)"""
    price = listing.get('price', 0)
    rating = listing.get('rating', 0)
    area = listing.get('area_sqm') or 0
    facility_count = listing.get('facility_count', 0)
    
    # 价格评分：越低越好，反转标准化
    if max_price > min_price:
        price_score = int(100 - ((price - min_price) / (max_price - min_price)) * 100)
    else:
        price_score = 50
    
    # 评分评分：越高越好
    if max_rating > min_rating:
        rating_score = int(((rating - min_rating) / (max_rating - min_rating)) * 100)
    else:
        rating_score = int(rating / 5.0 * 100)
    
    # 面积评分：越大越好
    if max_area > min_area:
        size_score = int(((area - min_area) / (max_area - min_area)) * 100)
    else:
        size_score = 50
    
    # 设施评分：越多越好
    if max_facility > min_facility:
        facility_score = int(((facility_count - min_facility) / (max_facility - min_facility)) * 100)
    else:
        facility_score = 50
    
    # 位置评分：基于商圈热度（使用评分作为代理）
    location_score = rating_score
    
    return {
        "price": max(0, min(100, price_score)),
        "location": max(0, min(100, location_score)),
        "facility": max(0, min(100, facility_score)),
        "rating": max(0, min(100, rating_score)),
        "size": max(0, min(100, size_score))
    }


def calculate_value_score(listing):
    """计算性价比评分 (0-100整数)"""
    price = listing.get('price', 1)
    rating = listing.get('rating', 0)
    area = listing.get('area_sqm') or 30  # 默认30平米
    facility_count = listing.get('facility_count', 0)
    
    # 性价比 = (评分 * 面积 * 设施数) / 价格
    value = (rating * area * (1 + facility_count * 0.1)) / price
    
    # 标准化到0-100
    score = min(100, int(value * 10))
    return score


def determine_winner(listings):
    """确定最佳房源"""
    if not listings:
        return None
    
    # 综合评分
    best_listing = max(listings, key=lambda l: calculate_value_score(l))
    
    # 提取简短名称
    title = best_listing.get('title', '')
    short_title = title[:15] + '...' if len(title) > 15 else title
    
    return {
        "unit_id": best_listing.get('unit_id'),
        "title": short_title,  # 房源简称
        "district": best_listing.get('district'),  # 行政区
        "value_score": calculate_value_score(best_listing),
        "reason": "综合性价比最高",
        # 详细原因
        "highlights": generate_winner_highlights(best_listing, listings)
    }


def generate_winner_highlights(winner, all_listings):
    """生成获胜房源的优势说明"""
    highlights = []
    
    # 价格优势
    winner_price = winner.get('price', 0)
    avg_price = sum(l.get('price', 0) for l in all_listings) / len(all_listings)
    if winner_price < avg_price * 0.9:
        highlights.append(f"价格低于平均{round((avg_price - winner_price) / avg_price * 100)}%")
    
    # 评分优势
    winner_rating = winner.get('rating', 0)
    if winner_rating >= 4.8:
        highlights.append(f"高评分{winner_rating}")
    
    # 面积优势
    winner_area = winner.get('area_sqm') or 0
    avg_area = sum(l.get('area_sqm') or 0 for l in all_listings) / len(all_listings)
    if winner_area > avg_area * 1.2:
        highlights.append(f"面积大于平均{round((winner_area - avg_area) / avg_area * 100)}%")
    
    # 设施优势
    winner_facility = winner.get('facility_count', 0)
    max_facility = max(l.get('facility_count', 0) for l in all_listings)
    if winner_facility == max_facility and max_facility > 3:
        highlights.append("设施最齐全")
    
    return highlights if highlights else ["各项指标均衡"]


@router.get("/quick/{unit_id1}/{unit_id2}")
def quick_compare(
    unit_id1: str,
    unit_id2: str
):
    """
    快速对比两个房源
    """
    listing1 = hive_service.get_listing_detail(unit_id1)
    listing2 = hive_service.get_listing_detail(unit_id2)

    if not listing1 or not listing2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房源不存在或无法加载",
        )
    
    # 逐项对比
    comparisons = []
    
    # 价格对比
    price1, price2 = listing1.get('price', 0), listing2.get('price', 0)
    comparisons.append({
        "dimension": "价格",
        "unit1_value": price1,
        "unit2_value": price2,
        "difference": round(price1 - price2, 2),
        "winner": 1 if price1 < price2 else 2 if price2 < price1 else 0,
        "note": "越低越好"
    })
    
    # 评分对比
    rating1, rating2 = listing1.get('rating', 0), listing2.get('rating', 0)
    comparisons.append({
        "dimension": "评分",
        "unit1_value": rating1,
        "unit2_value": rating2,
        "difference": round(rating1 - rating2, 2),
        "winner": 1 if rating1 > rating2 else 2 if rating2 > rating1 else 0,
        "note": "越高越好"
    })
    
    # 面积对比
    area1, area2 = listing1.get('area_sqm', 0), listing2.get('area_sqm', 0)
    comparisons.append({
        "dimension": "面积",
        "unit1_value": area1,
        "unit2_value": area2,
        "difference": round(area1 - area2, 2),
        "winner": 1 if area1 > area2 else 2 if area2 > area1 else 0,
        "note": "越大越好"
    })
    
    # 设施对比
    facility1, facility2 = listing1.get('facility_count', 0), listing2.get('facility_count', 0)
    comparisons.append({
        "dimension": "设施数量",
        "unit1_value": facility1,
        "unit2_value": facility2,
        "difference": facility1 - facility2,
        "winner": 1 if facility1 > facility2 else 2 if facility2 > facility1 else 0,
        "note": "越多越好"
    })
    
    # 统计胜负
    unit1_wins = sum(1 for c in comparisons if c["winner"] == 1)
    unit2_wins = sum(1 for c in comparisons if c["winner"] == 2)
    
    return {
        "unit_id1": unit_id1,
        "unit_id2": unit_id2,
        "comparisons": comparisons,
        "summary": {
            "unit1_wins": unit1_wins,
            "unit2_wins": unit2_wins,
            "overall_winner": 1 if unit1_wins > unit2_wins else 2 if unit2_wins > unit1_wins else 0
        }
    }


@router.post("/save")
def save_comparison(
    request: ComparisonRequest,
    name: str = "未命名对比",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    保存对比方案（简化版，仅记录到浏览历史）
    """
    from app.db.database import add_view_history
    
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    
    # 根据用户名获取用户ID
    from app.db.database import get_user_by_username
    user = get_user_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_id = user.id
    
    # 将对比的房源记录到浏览历史
    for unit_id in request.unit_ids:
        add_view_history(db, user_id, unit_id, duration=0)
    
    return {
        "success": True,
        "comparison_id": f"comp_{user_id}_{hash(str(request.unit_ids))}",
        "name": name,
        "unit_ids": request.unit_ids,
        "saved_at": datetime.utcnow().isoformat()
    }


@router.get("/list")
def get_comparison_list(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户对比历史列表
    
    从浏览历史中筛选出对比操作记录
    """
    from app.db.database import get_user_by_username, get_user_view_history
    
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    
    user = get_user_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取浏览历史作为对比记录
    history = get_user_view_history(db, user.id, limit=50)
    
    # 按时间分组，将同一时段的浏览记录作为一次对比
    comparisons = []
    current_time = datetime.utcnow()
    
    # 简化为返回最近浏览的房源作为对比候选
    recent_items = []
    for h in history[:10]:  # 最近10条
        recent_items.append({
            "unit_id": h.unit_id,
            "viewed_at": h.last_viewed_at.isoformat() if h.last_viewed_at else None,
            "listing_data": h.listing_data
        })
    
    return {
        "comparisons": [
            {
                "comparison_id": f"recent_{user.id}",
                "name": "最近对比",
                "unit_count": len(recent_items),
                "items": recent_items,
                "created_at": current_time.isoformat()
            }
        ]
    }
