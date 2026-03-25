#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房源列表模块 API
基于真实Hive/MySQL数据
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import List, Optional
import json

from app.models import schemas
from app.db.database import get_db, Listing, PriceCalendar
# from app.core.security import get_current_user_id  # 暂时不需要

router = APIRouter(tags=["房源列表"])


def _listing_to_detail_response(listing: Listing) -> schemas.ListingDetailResponse:
    """拼装详情：解析三模块 JSON 字符串。"""
    base = schemas.ListingListItem.model_validate(listing)
    d = base.model_dump()
    for raw_field, out_field in (
        ("facility_module_json", "facility_module"),
        ("comment_module_json", "comment_module"),
        ("landlord_module_json", "landlord_module"),
    ):
        raw = getattr(listing, raw_field, None)
        if raw:
            try:
                d[out_field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[out_field] = None
        else:
            d[out_field] = None
    d.setdefault(
        "detail_modules_note",
        "以下为途家详情页 dynamicModule 快照（爬取时点）；评价与标签为平台展示口径，非订单验证数据。",
    )
    return schemas.ListingDetailResponse(**d)


@router.get("", response_model=schemas.ListingListResponse)
async def get_listings(
    district: Optional[str] = Query(None, description="行政区筛选"),
    business_circle: Optional[str] = Query(None, description="商圈筛选"),
    min_price: Optional[float] = Query(None, description="最低价格"),
    max_price: Optional[float] = Query(None, description="最高价格"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    bedroom_count: Optional[int] = Query(None, description="卧室数"),
    sort_by: Optional[str] = Query("favorite_count", description="排序方式: price_asc, price_desc, rating, favorite_count"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """
    获取房源列表（分页、筛选、排序）
    """
    # 构建查询
    query = db.query(Listing)
    
    # 筛选条件
    if district:
        query = query.filter(Listing.district == district)
    if business_circle:
        query = query.filter(Listing.trade_area == business_circle)
    if min_price:
        query = query.filter(Listing.final_price >= min_price)
    if max_price:
        query = query.filter(Listing.final_price <= max_price)
    if bedroom_count:
        query = query.filter(Listing.bedroom_count == bedroom_count)
    if tags:
        tag_list = tags.split(',')
        for tag in tag_list:
            query = query.filter(Listing.house_tags.contains(tag))
    
    # 排序
    sort_mapping = {
        "price_asc": asc(Listing.final_price),
        "price_desc": desc(Listing.final_price),
        "rating": desc(Listing.rating),
        "favorite_count": desc(Listing.favorite_count)
    }
    query = query.order_by(sort_mapping.get(sort_by, desc(Listing.favorite_count)))
    
    # 分页
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    
    return schemas.ListingListResponse(
        total=total,
        page=page,
        size=size,
        items=[schemas.ListingListItem.model_validate(item) for item in items]
    )


@router.get("/{unit_id}", response_model=schemas.ListingDetailResponse)
async def get_listing_detail(
    unit_id: str,
    db: Session = Depends(get_db)
):
    """
    获取房源详情
    """
    listing = db.query(Listing).filter(Listing.unit_id == unit_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")

    return _listing_to_detail_response(listing)


@router.get("/{unit_id}/gallery", response_model=schemas.ListingGalleryResponse)
async def get_listing_gallery(
    unit_id: str,
    db: Session = Depends(get_db)
):
    """
    获取房源图片画廊
    按类别分类：客厅、卧室、厨房、卫生间、阳台、外景
    """
    from app.db.database import Listing
    import json
    
    listing = db.query(Listing).filter(Listing.unit_id == unit_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    # 解析图片数据
    categories = {
        "客厅": [],
        "卧室": [],
        "厨房": [],
        "卫生间": [],
        "阳台": [],
        "外景": [],
        "休闲": [],
        "其他": []
    }
    
    # 从 house_pics 字段解析完整图片列表
    if listing.house_pics:
        try:
            pics = json.loads(listing.house_pics)
            # 将所有图片放入"客厅"类别（简化处理）
            # 后续可以根据图片标题或分类信息分配到不同类别
            categories["客厅"] = pics[:10]  # 最多返回10张
            categories["卧室"] = pics[10:20] if len(pics) > 10 else []
            categories["其他"] = pics[20:] if len(pics) > 20 else []
        except json.JSONDecodeError:
            # 如果解析失败，使用封面图
            if listing.cover_image:
                categories["客厅"].append(listing.cover_image)
    elif listing.cover_image:
        # 如果没有 house_pics，使用封面图
        categories["客厅"].append(listing.cover_image)
    
    return schemas.ListingGalleryResponse(
        unit_id=unit_id,
        title=listing.title,
        total_pics=listing.pic_count or 0,
        categories=categories
    )


@router.get("/{unit_id}/calendar", response_model=schemas.PriceCalendarResponse)
async def get_price_calendar(
    unit_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_history: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取房源价格日历
    
    - start_date: 开始日期 (YYYY-MM-DD)
    - end_date: 结束日期 (YYYY-MM-DD)
    - include_history: 是否包含历史价格，默认False（只返回今天及以后）
    
    如果不传日期参数:
    - include_history=false: 返回今天起30天
    - include_history=true: 返回所有可用数据（历史+未来）
    """
    from app.db.database import Listing, PriceCalendar
    from datetime import datetime, timedelta
    
    # 获取房源信息
    listing = db.query(Listing).filter(Listing.unit_id == unit_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    # 构建查询
    query = db.query(PriceCalendar).filter(PriceCalendar.unit_id == unit_id)
    
    # 设置日期范围
    if start_date and end_date:
        # 使用传入的日期范围
        query = query.filter(
            PriceCalendar.date >= start_date,
            PriceCalendar.date <= end_date
        )
    elif include_history:
        # 返回所有可用数据
        pass  # 不添加日期过滤
    else:
        # 默认：从今天起30天
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        query = query.filter(
            PriceCalendar.date >= today,
            PriceCalendar.date <= future
        )
        start_date = today
        end_date = future
    
    # 查询价格日历
    calendars = query.order_by(PriceCalendar.date).all()
    
    # 如果没有指定日期范围，从结果中推断
    if not start_date and calendars:
        start_date = calendars[0].date
        end_date = calendars[-1].date
    
    # 构建响应数据
    calendar_items = [
        schemas.PriceCalendarItem(
            date=c.date,
            price=float(c.price),
            can_booking=bool(c.can_booking)
        )
        for c in calendars
    ]
    
    # 计算价格统计
    prices = [float(c.price) for c in calendars]
    price_stats = {
        "min": min(prices) if prices else 0,
        "max": max(prices) if prices else 0,
        "avg": round(sum(prices) / len(prices), 2) if prices else 0
    }
    
    return schemas.PriceCalendarResponse(
        unit_id=unit_id,
        title=listing.title,
        date_range={"start": start_date, "end": end_date},
        calendar=calendar_items,
        price_stats=price_stats
    )


@router.get("/{unit_id}/similar", response_model=List[schemas.ListingSimilarResponse])
async def get_similar_listings(
    unit_id: str,
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    获取相似房源推荐
    基于同商圈、同户型、价格相近的房源
    """
    from app.db.database import Listing
    
    # 获取当前房源
    listing = db.query(Listing).filter(Listing.unit_id == unit_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    # 查找相似房源
    similar = db.query(Listing).filter(
        Listing.unit_id != unit_id,
        Listing.district == listing.district,
        Listing.bedroom_count == listing.bedroom_count
    ).order_by(
        func.abs(Listing.final_price - listing.final_price)
    ).limit(limit).all()
    
    result = []
    for item in similar:
        # 计算相似度分数
        price_diff = abs(item.final_price - listing.final_price)
        similarity = max(0, 100 - price_diff)
        
        result.append(schemas.ListingSimilarResponse(
            unit_id=item.unit_id,
            title=item.title,
            district=item.district,
            final_price=float(item.final_price or 0),
            rating=float(item.rating or 0),
            similarity_score=similarity,
            cover_image=item.cover_image,
        ))
    
    return result


@router.get("/hot/ranking", response_model=List[schemas.ListingResponse])
async def get_hot_listings(
    district: Optional[str] = Query(None, description="行政区筛选"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    获取热门房源排行
    按收藏数排序
    """
    from app.db.database import Listing
    
    query = db.query(Listing)
    if district:
        query = query.filter(Listing.district == district)
    
    items = query.order_by(desc(Listing.favorite_count)).limit(limit).all()
    
    return [schemas.ListingResponse.model_validate(item) for item in items]
