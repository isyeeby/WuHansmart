#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
房源列表模块 API
基于真实Hive/MySQL数据
"""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, case
from typing import List, Optional, Tuple
import json

from app.models import schemas
from app.core.security import get_optional_user
from app.db.database import get_db, get_user_by_username, Listing, PriceCalendar, Favorite, UserViewHistory

router = APIRouter(tags=["房源列表"])


def _escape_like_pattern(s: str) -> str:
    """转义 LIKE 通配符，配合 escape='\\\\' 使用。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _user_preference_regions(db: Session, user_id: int, top_n: int = 5) -> Tuple[List[str], List[str]]:
    """根据收藏（权 3）与浏览历史（权 1）统计偏好行政区、商圈，各取 top_n。"""
    c_d: Counter = Counter()
    c_t: Counter = Counter()

    fav_q = (
        db.query(Listing.district, Listing.trade_area)
        .join(Favorite, Favorite.unit_id == Listing.unit_id)
        .filter(Favorite.user_id == user_id)
    )
    for d, ta in fav_q.all():
        if d:
            c_d[str(d).strip()] += 3
        if ta:
            c_t[str(ta).strip()] += 3

    hist_q = (
        db.query(Listing.district, Listing.trade_area)
        .join(UserViewHistory, UserViewHistory.unit_id == Listing.unit_id)
        .filter(UserViewHistory.user_id == user_id)
    )
    for d, ta in hist_q.all():
        if d:
            c_d[str(d).strip()] += 1
        if ta:
            c_t[str(ta).strip()] += 1

    top_d = [k for k, _ in c_d.most_common(top_n) if k]
    top_t = [k for k, _ in c_t.most_common(top_n) if k]
    return top_d, top_t


def _listing_to_detail_response(listing: Listing, db: Session) -> schemas.ListingDetailResponse:
    """拼装详情：解析三模块 JSON 字符串；展示价优先当日日历。"""
    from datetime import datetime

    base = schemas.ListingListItem.model_validate(listing)
    d = base.model_dump()
    d.pop("display_price", None)
    today_str = datetime.now().strftime("%Y-%m-%d")
    pc = (
        db.query(PriceCalendar)
        .filter(
            PriceCalendar.unit_id == listing.unit_id,
            PriceCalendar.date == today_str,
        )
        .first()
    )
    cal_p = float(pc.price or 0) if pc else 0.0
    d["display_price"] = cal_p if cal_p > 0 else float(listing.final_price or 0)
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
    keyword: Optional[str] = Query(None, max_length=120, description="关键词：标题/行政区/商圈模糊匹配"),
    sort_by: Optional[str] = Query(
        "favorite_count",
        description="排序: price_asc, price_desc, rating, favorite_count, personalized（登录后按收藏+浏览偏好）",
    ),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_username: Optional[str] = Depends(get_optional_user),
):
    """
    获取房源列表（分页、筛选、排序）
    """
    query = db.query(Listing)

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
        tag_list = tags.split(",")
        for tag in tag_list:
            query = query.filter(Listing.house_tags.contains(tag))
    if keyword and keyword.strip():
        pat = f"%{_escape_like_pattern(keyword.strip())}%"
        query = query.filter(
            or_(
                Listing.title.like(pat, escape="\\"),
                Listing.district.like(pat, escape="\\"),
                Listing.trade_area.like(pat, escape="\\"),
            )
        )

    sort_mapping = {
        "price_asc": asc(Listing.final_price),
        "price_desc": desc(Listing.final_price),
        "rating": desc(Listing.rating),
        "favorite_count": desc(Listing.favorite_count),
    }

    if sort_by == "personalized":
        user_row = None
        if current_username:
            user_row = get_user_by_username(db, username=current_username)
        if user_row:
            dlist, tlist = _user_preference_regions(db, user_row.id)
            whens = []
            if dlist:
                whens.append((Listing.district.in_(dlist), 2))
            if tlist:
                whens.append((Listing.trade_area.in_(tlist), 1))
            if whens:
                pref = case(*whens, else_=0)
                query = query.order_by(desc(pref), desc(Listing.favorite_count))
            else:
                query = query.order_by(desc(Listing.favorite_count))
        else:
            query = query.order_by(desc(Listing.favorite_count))
    else:
        query = query.order_by(sort_mapping.get(sort_by, desc(Listing.favorite_count)))

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")
    unit_ids = [row.unit_id for row in items]
    today_price_by_unit: dict = {}
    if unit_ids:
        for pc in (
            db.query(PriceCalendar)
            .filter(
                PriceCalendar.unit_id.in_(unit_ids),
                PriceCalendar.date == today_str,
            )
            .all()
        ):
            p = float(pc.price or 0)
            if p > 0:
                today_price_by_unit[pc.unit_id] = p

    list_items: List[schemas.ListingListItem] = []
    for row in items:
        base = schemas.ListingListItem.model_validate(row)
        disp = today_price_by_unit.get(row.unit_id)
        if disp is None:
            disp = float(row.final_price or 0)
        list_items.append(base.model_copy(update={"display_price": disp}))

    return schemas.ListingListResponse(
        total=total,
        page=page,
        size=size,
        items=list_items,
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

    return _listing_to_detail_response(listing, db)


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

    # PriceCalendarResponse.date_range 要求 start/end 均为 str，不能为 None
    if start_date is None or end_date is None:
        if calendars:
            start_date = str(calendars[0].date)
            end_date = str(calendars[-1].date)
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            start_date = start_date or today
            end_date = end_date or today
    else:
        start_date = str(start_date)
        end_date = str(end_date)
    
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
    ref = float(listing.final_price or 0)
    anchor = ref if ref > 0 else 1.0
    for item in similar:
        other = float(item.final_price or 0)
        rel = abs(other - ref) / anchor
        similarity = max(0.0, min(100.0, 100.0 * (1.0 - min(1.0, rel))))
        
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
