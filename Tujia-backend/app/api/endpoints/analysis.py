#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商圈分析模块 API
"""
import logging
from statistics import median

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from app.models import schemas
from app.db.database import get_db
from app.services.listing_price_bridge import listing_to_prediction_request
from app.services.price_opportunity_filters import is_eligible_price_opportunity_listing
from app.services.price_predictor import model_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["商圈分析"])

# 单次请求内模型调用上限，避免全表预测拖垮接口
_MAX_PRICE_OPPORTUNITY_MODEL_CALLS = 120


@router.get("/districts", response_model=List[schemas.DistrictStatsResponse])
async def get_districts(
    district: Optional[str] = Query(None, description="行政区筛选"),
    db: Session = Depends(get_db)
):
    """
    获取商圈列表及统计
    """
    from app.db.database import Listing
    from sqlalchemy import func
    
    query = db.query(
        Listing.district,
        Listing.trade_area,
        func.count(Listing.unit_id).label('listing_count'),
        func.avg(Listing.final_price).label('avg_price'),
        func.avg(Listing.rating).label('avg_rating'),
        func.avg(Listing.favorite_count).label('avg_favorite_count'),
        func.avg(Listing.bedroom_count).label('avg_bedroom_count'),
        func.min(Listing.final_price).label('min_price'),
        func.max(Listing.final_price).label('max_price')
    ).group_by(Listing.district, Listing.trade_area)
    
    if district:
        query = query.filter(Listing.district == district)
    
    results = query.all()
    
    return [
        schemas.DistrictStatsResponse(
            district=r.district or '',
            trade_area=r.trade_area or '',
            listing_count=r.listing_count or 0,
            avg_price=round(float(r.avg_price or 0), 2),
            avg_rating=round(float(r.avg_rating or 0), 2),
            avg_favorite_count=round(float(r.avg_favorite_count or 0), 2),
            avg_comment_count=0,
            avg_bedroom_count=round(float(r.avg_bedroom_count or 0), 1),
            min_price=round(float(r.min_price or 0), 2),
            max_price=round(float(r.max_price or 0), 2)
        )
        for r in results
    ]


@router.get("/facility-premium", response_model=schemas.FacilityPremiumResponse)
async def get_facility_premium(
    district: Optional[str] = Query(None, description="行政区筛选"),
    db: Session = Depends(get_db)
):
    """
    获取设施溢价分析
    
    分析各设施对价格的影响程度，计算有此设施 vs 无此设施的平均价格差异
    """
    from app.db.database import Listing
    from sqlalchemy import func
    import json
    
    # 定义要分析的设施标签列表
    FACILITY_TAGS = [
        "投影", "洗衣机", "空调", "智能门锁", "浴缸", "冰箱", 
        "吹风机", "全天热水", "有麻将机", "停车位", "阳台", 
        "WiFi", "厨房", "电视机", "近地铁", "可做饭"
    ]
    
    # 获取所有房源
    query = db.query(Listing)
    if district:
        query = query.filter(Listing.district == district)
    
    listings = query.all()
    
    if not listings:
        return schemas.FacilityPremiumResponse(facilities=[])
    
    # 统计每个设施的溢价数据
    facility_stats = {}
    
    for tag in FACILITY_TAGS:
        facility_stats[tag] = {
            'with_facility': [],
            'without_facility': []
        }
    
    # 遍历所有房源，分类统计
    total_listings = len(listings)
    
    for listing in listings:
        price = float(listing.final_price) if listing.final_price else 0
        if price <= 0:
            continue
            
        # 解析标签
        tags_in_listing = set()
        if listing.house_tags:
            try:
                tags_data = json.loads(listing.house_tags)
                if isinstance(tags_data, list):
                    for tag_item in tags_data:
                        if isinstance(tag_item, dict):
                            if 'text' in tag_item:
                                tags_in_listing.add(tag_item['text'])
                            elif 'tagText' in tag_item and isinstance(tag_item['tagText'], dict):
                                tags_in_listing.add(tag_item['tagText'].get('text', ''))
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 将房源价格分类到各个设施
        for tag in FACILITY_TAGS:
            if tag in tags_in_listing:
                facility_stats[tag]['with_facility'].append(price)
            else:
                facility_stats[tag]['without_facility'].append(price)
    
    # 计算每个设施的溢价
    facilities = []
    
    for tag, stats in facility_stats.items():
        with_prices = stats['with_facility']
        without_prices = stats['without_facility']
        
        # 需要有足够样本才计算
        if len(with_prices) < 3 or len(without_prices) < 3:
            continue
        
        avg_with = sum(with_prices) / len(with_prices)
        avg_without = sum(without_prices) / len(without_prices)
        
        # 计算溢价
        premium_amount = avg_with - avg_without
        premium_percent = (premium_amount / avg_without * 100) if avg_without > 0 else 0
        
        facilities.append(schemas.FacilityPremiumItem(
            facility_name=tag,
            avg_price_with=round(avg_with, 2),
            avg_price_without=round(avg_without, 2),
            premium_amount=round(premium_amount, 2),
            premium_percent=round(premium_percent, 1),
            listing_count=len(with_prices)
        ))
    
    # 按溢价比例排序
    facilities.sort(key=lambda x: abs(x.premium_percent), reverse=True)
    
    return schemas.FacilityPremiumResponse(facilities=facilities)


@router.get("/price-distribution")
async def get_price_distribution(
    district: Optional[str] = Query(None, description="行政区筛选"),
):
    """
    获取价格区间分布（与 hive_service 一致：优先 Hive DWS `dws_price_distribution`，否则 MySQL 现场分桶）。
    """
    from collections import defaultdict

    from app.services.hive_service import hive_service

    rows = hive_service.get_price_distribution(district=district)
    if not rows:
        return []

    # Hive 未指定 district 时按「区 × 区间」多行返回，需按区间汇总
    by_label: Dict[str, int] = defaultdict(int)
    for r in rows:
        label = r.get("price_range") or ""
        by_label[label] += int(r.get("listing_count") or 0)

    total = sum(by_label.values())
    if total <= 0:
        return []

    out = []
    for label in sorted(by_label.keys()):
        count = by_label[label]
        if count > 0:
            out.append(
                {
                    "price_range": label,
                    "count": count,
                    "percent": round(count / total * 100, 1),
                }
            )
    return out


@router.get("/price-opportunities")
async def get_price_opportunities(
    min_gap_rate: float = Query(
        20,
        description="最小价差率(%)，(预测价−挂牌价)/挂牌价×100",
        ge=5,
        le=50,
    ),
    limit: int = Query(20, description="返回数量", ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    获取价格洼地房源：当前挂牌价相对 XGBoost 模型预测价（或行政区中位数兜底）显著偏低。

    价差率 gap_rate = (预测价 - 挂牌价) / 挂牌价 × 100%，与 Hive ADS、投资模块 MySQL 路径一致，
    表示相对现价的「低估幅度」；若用预测价作分母会得到更小的百分比，易与直觉及其他接口不一致。

    排除：挂牌价不在 [80,500] 元/晚（与可比民宿带一致）、标题/类型/标签含青旅床位等共享住宿关键词，
    避免床位价与整套模型预测混算导致虚高价差率。
    """
    from app.db.database import Listing
    from sqlalchemy import func

    listings_raw = db.query(Listing).filter(
        Listing.final_price > 0,
        Listing.rating > 0
    ).all()

    listings = [row for row in listings_raw if is_eligible_price_opportunity_listing(row)]

    if not listings:
        return []

    by_district: dict = {}
    for row in listings:
        d = row.district
        if not d:
            continue
        by_district.setdefault(d, []).append(float(row.final_price))

    district_median: dict = {}
    for d, prices in by_district.items():
        if len(prices) >= 3:
            district_median[d] = float(median(prices))

    # 优先对「低于行政区中位数」的房源跑模型，控制调用次数
    scored = []
    for row in listings:
        cp = float(row.final_price or 0)
        d = row.district
        med = district_median.get(d)
        if med and med > 0 and cp < med:
            scored.append((row, (med - cp) / med))
    scored.sort(key=lambda x: x[1], reverse=True)
    candidates = [x[0] for x in scored[:_MAX_PRICE_OPPORTUNITY_MODEL_CALLS]]
    if len(candidates) < _MAX_PRICE_OPPORTUNITY_MODEL_CALLS // 2:
        seen = {id(x) for x in candidates}
        rest = sorted(
            [l for l in listings if id(l) not in seen],
            key=lambda l: (-float(l.rating or 0), float(l.final_price or 0)),
        )
        for row in rest:
            candidates.append(row)
            if len(candidates) >= _MAX_PRICE_OPPORTUNITY_MODEL_CALLS:
                break

    opportunities = []
    for listing in candidates:
        current_price = float(listing.final_price or 0)
        district = listing.district
        rating = float(listing.rating or 0)

        prediction_source = "xgboost"
        try:
            pred_req = listing_to_prediction_request(listing)
            predicted_price = model_service.predict(pred_req)
        except Exception as e:
            logger.warning("price-opportunities predict failed for %s: %s", listing.unit_id, e)
            predicted_price = None

        if predicted_price is None or predicted_price <= 0:
            med = district_median.get(district)
            if not med or med <= 0:
                continue
            predicted_price = float(med)
            prediction_source = "district_median"

        gap_rate = (
            (predicted_price - current_price) / current_price * 100
            if current_price > 0
            else 0.0
        )
        if gap_rate >= min_gap_rate:
            opportunities.append({
                "unit_id": listing.unit_id,
                "title": listing.title,
                "district": district,
                "current_price": current_price,
                "predicted_price": round(float(predicted_price), 2),
                "gap_rate": round(gap_rate, 1),
                "rating": rating,
                "prediction_source": prediction_source,
            })

    opportunities.sort(key=lambda x: x["gap_rate"], reverse=True)
    return opportunities[:limit]


@router.get("/roi-ranking")
async def get_roi_ranking(
    limit: int = Query(50, description="返回数量", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    各行政区综合排名（MySQL）：优先用价格日历不可订天次占比作需求代理，与评分、均价带、供给规模加权；
    日历样本不足的区用评分+收藏启发式兜底（见返回字段 occupancy_basis）。

    返回体为 `{ "data": [...], "field_glossary": {...} }`，与旧版「纯数组」相比多一层包装；`data` 每行含
    calendar_unavailable_share_pct、estimated_roi、revenue_intensity_ratio 等显义字段。
    """
    from app.services.district_ranking_service import (
        DISTRICT_ROI_RANKING_FIELD_GLOSSARY,
        build_analysis_roi_ranking_rows,
    )

    return {
        "data": build_analysis_roi_ranking_rows(db, limit),
        "field_glossary": DISTRICT_ROI_RANKING_FIELD_GLOSSARY,
    }
