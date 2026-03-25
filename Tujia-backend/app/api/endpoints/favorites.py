#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏模块 API
提供独立的收藏管理接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.models import schemas
from app.db.database import get_db, get_user_by_username
from app.core.security import get_current_user_id
from app.db.database import Favorite

router = APIRouter(tags=["收藏"])


@router.get("", response_model=List[schemas.FavoriteResponse])
async def get_favorites(
    folder: Optional[str] = None,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取收藏列表
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    query = db.query(Favorite).filter(Favorite.user_id == user.id)
    if folder:
        query = query.filter(Favorite.folder_name == folder)
    
    favorites = query.order_by(Favorite.created_at.desc()).all()
    return favorites


@router.post("/{unit_id}", response_model=schemas.FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    unit_id: str,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    添加收藏
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 检查是否已收藏
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="已收藏")
    
    # 创建新收藏
    new_fav = Favorite(
        user_id=user.id,
        unit_id=unit_id,
        folder_name="默认收藏夹",
        price_alert_enabled=False,
        created_at=datetime.utcnow()
    )
    
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    
    return new_fav


@router.delete("/{unit_id}")
async def remove_favorite(
    unit_id: str,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    取消收藏
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()
    
    if not fav:
        raise HTTPException(status_code=404, detail="收藏不存在")
    
    db.delete(fav)
    db.commit()
    
    return {"message": "取消收藏成功", "unit_id": unit_id}


@router.get("/folders")
async def get_favorite_folders(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取收藏夹分类列表
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 按folder_name分组统计
    from sqlalchemy import func
    results = db.query(
        Favorite.folder_name,
        func.count(Favorite.id).label('count')
    ).filter(Favorite.user_id == user.id).group_by(Favorite.folder_name).all()
    
    return [{"name": r[0] or "默认收藏夹", "count": r[1]} for r in results]


@router.get("/alerts")
async def get_favorite_alerts(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    获取收藏房源的价格提醒设置
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取启用了价格提醒的收藏
    alerts = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.price_alert_enabled == True
    ).all()
    
    return {
        "alerts": [
            {
                "unit_id": alert.unit_id,
                "folder_name": alert.folder_name,
                "alert_threshold": alert.alert_threshold,
                "created_at": alert.created_at.isoformat() if alert.created_at else None
            }
            for alert in alerts
        ],
        "total_enabled": len(alerts)
    }


@router.put("/{unit_id}/alert")
async def update_favorite_alert(
    unit_id: str,
    enabled: bool = True,
    threshold: float = 0.10,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    更新收藏房源的价格提醒设置
    
    - enabled: 是否启用价格提醒
    - threshold: 价格变动阈值 (0.1 = 10%)
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()
    
    if not fav:
        raise HTTPException(status_code=404, detail="收藏不存在")
    
    fav.price_alert_enabled = enabled
    fav.alert_threshold = threshold
    db.commit()
    
    return {
        "message": "Alert settings updated",
        "unit_id": unit_id,
        "price_alert_enabled": enabled,
        "alert_threshold": threshold
    }
