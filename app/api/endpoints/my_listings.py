#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
我的房源模块 API
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models import schemas
from app.db.database import get_db, get_user_by_username
from app.core.security import get_current_user_id

router = APIRouter(tags=["我的房源"])


def _resolve_db_user_id(db: Session, current_username: str) -> int:
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.id


def _coords_valid(lat, lon) -> bool:
    try:
        la = float(lat) if lat is not None else None
        lo = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        return False
    if la is None or lo is None:
        return False
    if abs(la) < 1e-9 and abs(lo) < 1e-9:
        return False
    return True


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """球面大圆距离（公里）。"""
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    h = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * r * asin(sqrt(min(1.0, h)))


def _house_tags_to_list(raw: Optional[str], limit: int = 5) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out: List[str] = []
            for item in data[:limit]:
                if isinstance(item, dict):
                    t = item.get("text") or (item.get("tagText") or {}).get("text")
                    if isinstance(t, str) and t.strip():
                        out.append(t.strip())
                elif isinstance(item, str) and item.strip():
                    out.append(item.strip())
            return out
    except (json.JSONDecodeError, TypeError):
        pass
    return [t.strip() for t in str(raw).split(",") if t.strip()][:limit]


@router.post("", response_model=schemas.MyListingResponse)
async def create_my_listing(
    listing: schemas.MyListingCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    创建我的房源
    """
    from app.db.database import MyListing

    uid = _resolve_db_user_id(db, current_user_id)
    db_listing = MyListing(
        user_id=uid,
        title=listing.title,
        district=listing.district,
        business_circle=listing.business_circle,
        address=listing.address,
        longitude=listing.longitude,
        latitude=listing.latitude,
        bedroom_count=listing.bedroom_count,
        bed_count=listing.bed_count,
        bathroom_count=listing.bathroom_count,
        max_guests=listing.max_guests,
        area=listing.area,
        current_price=listing.current_price,
        facility_tags=listing.facility_tags or [],
        status="active"
    )
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)
    
    return schemas.MyListingResponse(
        id=db_listing.id,
        user_id=db_listing.user_id,
        title=db_listing.title,
        district=db_listing.district,
        business_circle=db_listing.business_circle,
        address=db_listing.address,
        longitude=db_listing.longitude,
        latitude=db_listing.latitude,
        bedroom_count=db_listing.bedroom_count,
        bed_count=db_listing.bed_count,
        bathroom_count=db_listing.bathroom_count,
        max_guests=db_listing.max_guests,
        area=db_listing.area,
        current_price=float(db_listing.current_price),
        style_tags=db_listing.style_tags or [],
        facility_tags=db_listing.facility_tags or [],
        location_tags=db_listing.location_tags or [],
        crowd_tags=db_listing.crowd_tags or [],
        cover_image=db_listing.cover_image,
        images=db_listing.images or [],
        status=db_listing.status,
        created_at=db_listing.created_at,
        updated_at=db_listing.updated_at
    )


@router.get("", response_model=List[schemas.MyListingResponse])
async def get_my_listings(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取我的房源列表
    """
    from app.db.database import get_my_listings

    uid = _resolve_db_user_id(db, current_user_id)
    listings = get_my_listings(db, uid)
    
    return [
        schemas.MyListingResponse(
            id=l.id,
            user_id=l.user_id,
            title=l.title,
            district=l.district,
            business_circle=l.business_circle,
            address=l.address,
            longitude=l.longitude,
            latitude=l.latitude,
            bedroom_count=l.bedroom_count,
            bed_count=l.bed_count,
            bathroom_count=l.bathroom_count,
            max_guests=l.max_guests,
            area=l.area,
            current_price=float(l.current_price),
            style_tags=l.style_tags or [],
            facility_tags=l.facility_tags or [],
            location_tags=l.location_tags or [],
            crowd_tags=l.crowd_tags or [],
            cover_image=l.cover_image,
            images=l.images or [],
            status=l.status,
            created_at=l.created_at,
            updated_at=l.updated_at
        )
        for l in listings
    ]


@router.get("/{listing_id}", response_model=schemas.MyListingResponse)
async def get_my_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取单个房源详情
    """
    from app.db.database import get_my_listing_by_id

    uid = _resolve_db_user_id(db, current_user_id)
    listing = get_my_listing_by_id(db, listing_id, uid)
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    return schemas.MyListingResponse(
        id=listing.id,
        user_id=listing.user_id,
        title=listing.title,
        district=listing.district,
        business_circle=listing.business_circle,
        address=listing.address,
        longitude=listing.longitude,
        latitude=listing.latitude,
        bedroom_count=listing.bedroom_count,
        bed_count=listing.bed_count,
        bathroom_count=listing.bathroom_count,
        max_guests=listing.max_guests,
        area=listing.area,
        current_price=float(listing.current_price),
        style_tags=listing.style_tags or [],
        facility_tags=listing.facility_tags or [],
        location_tags=listing.location_tags or [],
        crowd_tags=listing.crowd_tags or [],
        cover_image=listing.cover_image,
        images=listing.images or [],
        status=listing.status,
        created_at=listing.created_at,
        updated_at=listing.updated_at
    )


@router.put("/{listing_id}", response_model=schemas.MyListingResponse)
async def update_my_listing(
    listing_id: int,
    listing_update: schemas.MyListingUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    更新房源信息
    """
    from app.db.database import get_my_listing_by_id, MyListing

    uid = _resolve_db_user_id(db, current_user_id)
    db_listing = get_my_listing_by_id(db, listing_id, uid)
    if not db_listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    # 更新字段
    update_data = listing_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_listing, field, value)
    
    db.commit()
    db.refresh(db_listing)
    
    return schemas.MyListingResponse(
        id=db_listing.id,
        user_id=db_listing.user_id,
        title=db_listing.title,
        district=db_listing.district,
        business_circle=db_listing.business_circle,
        address=db_listing.address,
        longitude=db_listing.longitude,
        latitude=db_listing.latitude,
        bedroom_count=db_listing.bedroom_count,
        bed_count=db_listing.bed_count,
        bathroom_count=db_listing.bathroom_count,
        max_guests=db_listing.max_guests,
        area=db_listing.area,
        current_price=float(db_listing.current_price),
        style_tags=db_listing.style_tags or [],
        facility_tags=db_listing.facility_tags or [],
        location_tags=db_listing.location_tags or [],
        crowd_tags=db_listing.crowd_tags or [],
        cover_image=db_listing.cover_image,
        images=db_listing.images or [],
        status=db_listing.status,
        created_at=db_listing.created_at,
        updated_at=db_listing.updated_at
    )


@router.delete("/{listing_id}", response_model=schemas.MessageResponse)
async def delete_my_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    删除房源
    """
    from app.db.database import get_my_listing_by_id

    uid = _resolve_db_user_id(db, current_user_id)
    db_listing = get_my_listing_by_id(db, listing_id, uid)
    if not db_listing:
        raise HTTPException(status_code=404, detail="房源不存在")

    db.delete(db_listing)
    db.commit()
    
    return schemas.MessageResponse(message="房源删除成功")


@router.get("/{listing_id}/competitors", response_model=schemas.ComparisonReport)
async def get_competitors(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取竞品对比分析
    """
    from app.db.database import get_my_listing_by_id, Listing

    uid = _resolve_db_user_id(db, current_user_id)
    my_listing = get_my_listing_by_id(db, listing_id, uid)
    if not my_listing:
        raise HTTPException(status_code=404, detail="房源不存在")

    my_lat = my_listing.latitude
    my_lon = my_listing.longitude
    my_geo = _coords_valid(my_lat, my_lon)

    pool = db.query(Listing).filter(Listing.district == my_listing.district).all()
    geo_ranking_used = False

    if my_geo:
        with_coords = []
        for c in pool:
            if not _coords_valid(c.latitude, c.longitude):
                continue
            dist = _haversine_km(
                float(my_lat), float(my_lon), float(c.latitude), float(c.longitude)
            )
            with_coords.append((dist, c))
        if with_coords:
            with_coords.sort(key=lambda x: x[0])
            competitors = [c for _, c in with_coords[:10]]
            geo_ranking_used = True
            selection_note = (
                "已按与「我的房源」直线距离（公里）在同一行政区内选取最近的平台房源作为竞品。"
            )
        else:
            competitors = pool[:10]
            selection_note = (
                "您的房源已填坐标，但同行政区平台房源暂无坐标；已按行政区展示，请先运行 "
                "scripts/backfill_listing_coordinates.py 回填 listings。"
            )
    else:
        competitors = pool[:10]
        selection_note = (
            "「我的房源」未填写经纬度，已按同行政区展示；填写坐标后可按距离选取最近竞品。"
        )

    my_price = float(my_listing.current_price)
    competitor_items = []
    for c in competitors:
        cp = float(c.final_price) if c.final_price else 0.0
        if my_price > 0 and cp > 0:
            sim = max(0.0, min(100.0, 100.0 - abs(cp - my_price) / my_price * 100.0))
        else:
            sim = 50.0
        tl = _house_tags_to_list(c.house_tags)
        dist_km = None
        if my_geo and _coords_valid(c.latitude, c.longitude):
            dist_km = round(
                _haversine_km(
                    float(my_lat), float(my_lon), float(c.latitude), float(c.longitude)
                ),
                2,
            )
        competitor_items.append(
            schemas.CompetitorItem(
                unit_id=c.unit_id,
                title=c.title or "",
                district=c.district or "",
                final_price=cp,
                rating=float(c.rating) if c.rating else 0.0,
                favorite_count=c.favorite_count or 0,
                house_tags=c.house_tags,
                tag_list=tl if tl else None,
                similarity_score=round(sim, 1),
                distance_km=dist_km,
            )
        )
    
    # 计算市场定位
    competitor_prices = [float(c.final_price or 0) for c in competitors if c.final_price]
    all_prices = competitor_prices + [my_price]
    
    # 价格排名（从低到高）
    sorted_prices = sorted(all_prices)
    my_price_rank = sorted_prices.index(my_price) + 1 if my_price in sorted_prices else len(all_prices)
    
    # 价格分位（百分比）
    price_percentile = (my_price_rank / len(all_prices) * 100) if all_prices else 50
    
    # 商圈均价
    avg_price = sum(competitor_prices) / len(competitor_prices) if competitor_prices else my_price
    
    return schemas.ComparisonReport(
        my_listing=schemas.MyListingResponse(
            id=my_listing.id,
            user_id=my_listing.user_id,
            title=my_listing.title,
            district=my_listing.district,
            business_circle=my_listing.business_circle,
            address=my_listing.address,
            longitude=my_listing.longitude,
            latitude=my_listing.latitude,
            bedroom_count=my_listing.bedroom_count,
            bed_count=my_listing.bed_count,
            bathroom_count=my_listing.bathroom_count,
            max_guests=my_listing.max_guests,
            area=my_listing.area,
            current_price=float(my_listing.current_price),
            style_tags=my_listing.style_tags or [],
            facility_tags=my_listing.facility_tags or [],
            location_tags=my_listing.location_tags or [],
            crowd_tags=my_listing.crowd_tags or [],
            cover_image=my_listing.cover_image,
            images=my_listing.images or [],
            status=my_listing.status,
            created_at=my_listing.created_at,
            updated_at=my_listing.updated_at
        ),
        market_position={
            "avg_price": round(avg_price, 2),
            "my_price_rank": my_price_rank,
            "price_percentile": round(price_percentile, 1),
            "total_competitors": len(competitors),
            "geo_ranking_used": geo_ranking_used,
            "selection_note": selection_note,
        },
        competitors=competitor_items,
        analysis=_build_comparison_analysis(my_price, avg_price, competitor_prices),
    )


def _build_comparison_analysis(
    my_price: float, avg_price: float, competitor_prices: list
) -> dict:
    """
    竞品对比文案：均价为「本次拉取的竞品」样本均值，非全市口径；
    避免「价低却建议优化设施、价高却建议提价」等误导。
    """
    advantages: list = []
    disadvantages: list = []
    suggestions: list = []

    if competitor_prices and avg_price > 0:
        r = my_price / avg_price
        if r < 0.9:
            advantages.append("定价低于本次对比竞品均价，在价格带上有优势")
            suggestions.append("若入住稳定，可侧重设施与服务体验，再试探合理提价空间")
        elif r <= 1.1:
            advantages.append("定价与本次对比竞品均价接近")
            suggestions.append("建议强化标题、首图与核心卖点，提升与邻房的差异化感知")
        else:
            disadvantages.append("定价高于本次对比竞品均价")
            suggestions.append("建议核实品质与评分是否支撑溢价；必要时微调定价或补强设施与口碑")
    else:
        suggestions.append("有效竞品样本较少，结论仅供参考，可扩大筛选范围后再次对比")

    if not advantages and not disadvantages:
        advantages.append("请结合下表价格、距离与相似度综合判断")

    return {
        "advantages": advantages,
        "disadvantages": disadvantages,
        "suggestions": suggestions[:2] if suggestions else ["持续跟踪竞品价格与上架动态"],
    }


@router.post("/{listing_id}/price-suggestion", response_model=schemas.PriceSuggestionResponse)
async def get_price_suggestion(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """
    获取定价建议
    
    基于XGBoost模型预测最优定价，给出调价建议
    """
    from app.db.database import get_my_listing_by_id, Listing
    from app.services.price_predictor import model_service

    uid = _resolve_db_user_id(db, current_user_id)
    my_listing = get_my_listing_by_id(db, listing_id, uid)
    if not my_listing:
        raise HTTPException(status_code=404, detail="房源不存在")

    current_price = float(my_listing.current_price)
    
    # 解析设施标签
    facilities = my_listing.facility_tags or []
    
    # 高溢价设施识别
    has_mahjong = 1 if any('麻将' in str(f) for f in facilities) else 0
    has_bathtub = 1 if any('浴缸' in str(f) for f in facilities) else 0
    has_kitchen = 1 if any('厨房' in str(f) for f in facilities) else 0
    
    # 其他设施识别
    has_projector = 1 if any('投影' in str(f) for f in facilities) else 0
    has_washer = 1 if any('洗衣' in str(f) for f in facilities) else 0
    has_smart_lock = 1 if any('智能锁' in str(f) for f in facilities) else 0
    has_view = 1 if any('江景' in str(f) or '湖景' in str(f) or '景观' in str(f) for f in facilities) else 0
    has_tv = 1 if any('电视' in str(f) for f in facilities) else 0
    has_fridge = 1 if any('冰箱' in str(f) for f in facilities) else 0
    has_elevator = 1 if any('电梯' in str(f) for f in facilities) else 0
    near_metro = 1 if any('地铁' in str(f) for f in facilities) else 0
    has_terrace = 1 if any('露台' in str(f) or '阳台' in str(f) for f in facilities) else 0
    
    # 构建模型预测特征
    predict_features = {
        'district': my_listing.district,
        'trade_area': my_listing.business_circle or my_listing.district,
        'bedroom_count': my_listing.bedroom_count,
        'bed_count': my_listing.bed_count,
        'bathroom_count': my_listing.bathroom_count,
        'area': my_listing.area or 50,
        'capacity': my_listing.max_guests,
        # 高溢价设施
        'has_mahjong': has_mahjong,
        'has_bathtub': has_bathtub,
        'has_kitchen': has_kitchen,
        # 其他设施
        'has_projector': has_projector,
        'has_washer': has_washer,
        'has_smart_lock': has_smart_lock,
        'has_view': has_view,
        'has_tv': has_tv,
        'has_fridge': has_fridge,
        'has_elevator': has_elevator,
        'near_metro': near_metro,
        'has_terrace': has_terrace,
        'has_air_conditioning': 1,  # 默认有空调
        'has_wifi': 1,  # 默认有WiFi
        'has_heater': 1,  # 默认有热水器
        # 默认值
        'rating': 4.85,
        'favorite_count': 100,
        'pic_count': 30,
    }
    
    # 使用XGBoost模型预测
    suggested_price = model_service.manager.predict_price(predict_features)
    
    reasoning = []
    
    # 分析设施优势
    if has_mahjong:
        reasoning.append("麻将机带来约16元溢价")
    if has_bathtub:
        reasoning.append("浴缸带来约13元溢价")
    if has_kitchen:
        reasoning.append("厨房设施增加实用性")
    if has_projector:
        reasoning.append("投影设施提升娱乐体验")
    if has_view:
        reasoning.append("景观房具有位置优势")
    if near_metro:
        reasoning.append("近地铁交通便利")
    
    # 如果模型预测失败，使用市场均价
    if suggested_price is None:
        competitors = db.query(Listing).filter(
            Listing.district == my_listing.district
        ).limit(50).all()
        
        if competitors:
            suggested_price = sum([float(c.final_price or 0) for c in competitors]) / len(competitors)
        else:
            suggested_price = current_price
        reasoning.append("基于市场均价计算")
    else:
        reasoning.append("基于AI模型预测")
    
    # 根据卧室数量调整
    if my_listing.bedroom_count >= 2:
        reasoning.append(f"{my_listing.bedroom_count}室房源有溢价潜力")
    
    # 生成建议
    if suggested_price > current_price * 1.1:
        suggestion = "建议涨价"
        reasoning.append("您的房源价格低于市场水平，有较大提价空间")
    elif suggested_price < current_price * 0.9:
        suggestion = "建议降价"
        reasoning.append("当前价格偏高，可能影响入住率")
    else:
        suggestion = "建议保持"
        reasoning.append("当前定价合理，符合市场水平")
    
    # 置信度：与建议价相对当前价的偏离负相关（启发式，非统计置信区间）
    diff_ratio = abs(suggested_price - current_price) / current_price if current_price > 0 else 0.0
    confidence = round(min(0.95, max(0.58, 0.93 - diff_ratio * 0.85)), 2)

    return schemas.PriceSuggestionResponse(
        current_price=current_price,
        suggested_price=round(suggested_price, 2),
        price_difference=round(suggested_price - current_price, 2),
        difference_percent=round((suggested_price - current_price) / current_price * 100, 1),
        suggestion=suggestion,
        reasoning=reasoning,
        confidence=round(confidence, 2)
    )
