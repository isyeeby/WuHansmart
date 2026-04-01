#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标签库模块 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import json
import time
from functools import lru_cache

from app.models import schemas
from app.db.database import get_db

router = APIRouter(tags=["标签库"])

# 内存缓存存储
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 缓存5分钟

def _get_cache_key(prefix: str, *args) -> str:
    """生成缓存key"""
    return f"{prefix}:{':'.join(str(arg) for arg in args)}"

def _get_from_cache(key: str) -> Optional[Any]:
    """从缓存获取数据"""
    if key in _cache:
        data, timestamp = _cache[key]['data'], _cache[key]['timestamp']
        if time.time() - timestamp < CACHE_TTL:
            return data
        else:
            del _cache[key]
    return None

def _set_cache(key: str, data: Any):
    """设置缓存数据"""
    _cache[key] = {'data': data, 'timestamp': time.time()}


# 标签分类数据（与定价工作台 Prediction 映射、price_feature_config 关键词对齐，便于「我的房源」勾选后一键填充）
TAG_CATEGORIES = {
    "style": {
        "category_name": "风格标签",
        "tags": ["欧美风", "网红INS风", "现代风", "日式风", "中式风", "地中海风", "北欧风", "田园风"]
    },
    "facility": {
        "category_name": "设施标签",
        "tags": [
            "WiFi",
            "空调",
            "冷暖空调",
            "可做饭",
            "厨房",
            "投影",
            "巨幕投影",
            "洗衣机",
            "智能锁",
            "智能门锁",
            "电视",
            "暖气",
            "地暖",
            "冰箱",
            "电梯",
            "观景露台",
            "麻将机",
            "大客厅",
            "浴缸",
            "私家花园",
            "格调小院",
            "景观房",
            "全天热水",
            "停车位",
            "免费停车",
            "付费停车位",
            "吹风机",
        ]
    },
    "location": {
        "category_name": "位置与环境",
        "tags": [
            "近地铁",
            "近火车站",
            "近高校",
            "近滑雪场",
            "江景",
            "湖景",
            "山景",
            "江景房",
            "湖景房",
            "近景点",
            "近商圈",
            "近机场",
            "超市/菜场",
        ]
    },
    "service": {
        "category_name": "服务/人群",
        "tags": [
            "管家服务",
            "立即确认",
            "团建会议",
            "可带宠物",
            "允许宠物",
            "接待老人",
            "接待儿童",
            "亲子精选",
            "商务差旅",
        ]
    }
}


@router.get("/categories", response_model=List[schemas.TagCategoryResponse])
async def get_tag_categories():
    """
    获取标签分类
    返回所有标签分类及标签列表，用于房源上传时选择标签
    """
    result = []
    for category, data in TAG_CATEGORIES.items():
        result.append(schemas.TagCategoryResponse(
            category=category,
            tags=data["tags"]
        ))
    return result


@router.get("/popular", response_model=schemas.PopularTagsResponse)
async def get_popular_tags(
    district: Optional[str] = Query(None, description="行政区筛选"),
    limit: int = Query(20, ge=1, le=50, description="数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取热门标签
    统计各标签的使用频率和溢价情况（带缓存）
    """
    # 尝试从缓存获取
    cache_key = _get_cache_key('popular_tags', district, limit)
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    from app.db.database import Listing
    
    # 使用数据库聚合查询替代全表加载，提升性能
    query = db.query(Listing.house_tags, Listing.final_price, Listing.district)
    
    # 如果指定了行政区，添加筛选
    if district:
        query = query.filter(Listing.district == district)
    
    # 只获取有标签的房源，减少数据量
    query = query.filter(Listing.house_tags.isnot(None))
    
    listings = query.all()
    
    # 统计标签使用情况
    tag_stats = {}
    total_listings = 0
    
    for house_tags, final_price, listing_district in listings:
        total_listings += 1
        
        # 解析标签JSON
        try:
            if house_tags:
                tags_str = house_tags
                # 尝试解析JSON
                if tags_str.startswith('['):
                    tags_data = json.loads(tags_str.replace('""', '"'))
                    for tag in tags_data:
                        if isinstance(tag, dict) and 'text' in tag:
                            tag_text = tag['text']
                        elif isinstance(tag, dict) and 'tagText' in tag:
                            tag_text = tag['tagText'].get('text', '')
                        else:
                            continue
                        
                        if tag_text:
                            if tag_text not in tag_stats:
                                tag_stats[tag_text] = {
                                    'count': 0,
                                    'total_price': 0
                                }
                            tag_stats[tag_text]['count'] += 1
                            tag_stats[tag_text]['total_price'] += float(final_price or 0)
        except:
            pass
    
    # 计算平均价格和占比
    tags_list = []
    for tag_name, stats in tag_stats.items():
        avg_price = stats['total_price'] / stats['count'] if stats['count'] > 0 else 0
        percent = (stats['count'] / total_listings * 100) if total_listings > 0 else 0
        
        tags_list.append(schemas.PopularTagItem(
            tag_name=tag_name,
            usage_count=stats['count'],
            avg_price=round(avg_price, 2),
            percent=round(percent, 1)
        ))
    
    # 按使用次数排序
    tags_list.sort(key=lambda x: x.usage_count, reverse=True)
    
    result = schemas.PopularTagsResponse(
        district=district,
        tags=tags_list[:limit]
    )
    
    # 存入缓存
    _set_cache(cache_key, result)
    
    return result
