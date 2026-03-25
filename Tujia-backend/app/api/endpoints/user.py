"""
User management endpoints.
提供用户偏好设置、收藏夹管理、浏览历史等功能。
"""
from typing import Optional, Any, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.security import get_current_user_id
from app.db.database import (
    get_db,
    get_user_by_username,
    update_user_preferences,
    refresh_user_persona_summary,
    User,
    Favorite,
    UserViewHistory,
)
from app.models.schemas import (
    UserResponse,
    UserUpdate,
    UserPreferences,
    OnboardingComplete,
    FavoriteCreate,
    FavoriteResponse,
    FavoriteFolder,
    ViewHistoryCreate,
    ViewHistoryResponse,
)

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_user_profile(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get current user profile information.
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/me", response_model=UserResponse)
def update_user_profile(
    user_update: UserUpdate,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update current user profile and preferences.
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user_update.phone is not None:
        user.phone = user_update.phone
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.email is not None:
        user.email = user_update.email

    updated_user = update_user_preferences(
        db=db,
        user_id=user.id,
        preferred_district=user_update.preferred_district,
        preferred_price_min=user_update.preferred_price_min,
        preferred_price_max=user_update.preferred_price_max,
        travel_purpose=user_update.travel_purpose,
        required_facilities=user_update.required_facilities,
        user_role=user_update.user_role,
        persona_answers=user_update.persona_answers,
    )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )

    return updated_user


@router.post("/me/onboarding", response_model=UserResponse)
def complete_onboarding(
    payload: OnboardingComplete,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Any:
    """
    提交首登调研：写入身份、问卷 JSON、普通用户偏好列，并生成画像摘要。
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.user_role = payload.user_role
    user.persona_answers = dict(payload.persona_answers or {})
    user.onboarding_completed = True
    user.onboarding_skipped_at = None

    if payload.user_role == "guest":
        if payload.travel_purpose is not None:
            user.travel_purpose = payload.travel_purpose
        if payload.preferred_district is not None:
            user.preferred_district = payload.preferred_district
        if payload.preferred_price_min is not None:
            user.preferred_price_min = payload.preferred_price_min
        if payload.preferred_price_max is not None:
            user.preferred_price_max = payload.preferred_price_max
        if payload.required_facilities is not None:
            user.required_facilities = payload.required_facilities
    elif payload.user_role == "operator":
        city = (user.persona_answers or {}).get("primary_city")
        if city and not user.preferred_district:
            user.preferred_district = str(city)[:50]

    refresh_user_persona_summary(user)
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/onboarding/skip", response_model=UserResponse)
def skip_onboarding(
    user_role: Optional[str] = Query(
        None,
        description="可选：operator / investor / guest，便于未填问卷时仍做分流",
    ),
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Any:
    """跳过首登调研；可选传 user_role。"""
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user_role is not None and user_role not in ("operator", "investor", "guest"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_role must be operator, investor, or guest",
        )
    user.onboarding_completed = True
    user.onboarding_skipped_at = datetime.utcnow()
    if user_role is not None:
        user.user_role = user_role
    refresh_user_persona_summary(user)
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/preferences")
def get_user_preferences(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user recommendation preferences.
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "preferred_district": user.preferred_district,
        "preferred_price_min": user.preferred_price_min,
        "preferred_price_max": user.preferred_price_max,
        "full_name": user.full_name,
        "email": user.email
    }


@router.put("/preferences", response_model=UserPreferences)
def update_preferences_alias(
    prefs: UserPreferences,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    更新用户偏好设置（别名）
    """
    return update_preferences(prefs, current_username, db)


@router.put("/me/preferences", response_model=UserPreferences)
def update_preferences(
    prefs: UserPreferences,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    更新用户偏好设置（完整版）
    
    支持设置：
    - 偏好商圈
    - 价格区间
    - 出行目的（情侣/家庭/商务/考研/休闲）
    - 必带设施列表
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # 更新所有偏好字段
    user.preferred_district = prefs.preferred_district
    user.preferred_price_min = prefs.preferred_price_min
    user.preferred_price_max = prefs.preferred_price_max
    user.travel_purpose = prefs.travel_purpose
    user.required_facilities = prefs.required_facilities
    user.updated_at = datetime.utcnow()
    refresh_user_persona_summary(user)

    db.commit()
    db.refresh(user)

    return UserPreferences(
        preferred_district=user.preferred_district,
        preferred_price_min=float(user.preferred_price_min) if user.preferred_price_min else None,
        preferred_price_max=float(user.preferred_price_max) if user.preferred_price_max else None,
        travel_purpose=user.travel_purpose,
        required_facilities=user.required_facilities
    )


# =============================================================================
# 收藏夹管理接口
# =============================================================================

@router.get("/me/favorites", response_model=List[FavoriteResponse])
def get_favorites(
    folder: Optional[str] = Query(None, description="按收藏夹筛选"),
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取用户收藏列表
    
    可选参数：
    - folder: 筛选特定收藏夹
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Favorite).filter(Favorite.user_id == user.id)
    if folder:
        query = query.filter(Favorite.folder_name == folder)

    favorites = query.order_by(Favorite.created_at.desc()).all()
    return favorites


@router.post("/me/favorites", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    fav: FavoriteCreate,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    添加房源到收藏夹
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 检查是否已收藏
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == fav.unit_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already in favorites")

    # 创建新收藏
    new_fav = Favorite(
        user_id=user.id,
        unit_id=fav.unit_id,
        folder_name=fav.folder_name or "默认收藏夹",
        price_alert_enabled=fav.price_alert_enabled or False,
        alert_threshold=fav.alert_threshold or 0.10,
        created_at=datetime.utcnow()
    )

    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)

    return new_fav


@router.delete("/me/favorites/{unit_id}")
def remove_favorite(
    unit_id: str,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    取消收藏
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()

    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(fav)
    db.commit()

    return {"message": "Removed from favorites", "unit_id": unit_id}


@router.get("/me/favorites/folders", response_model=List[FavoriteFolder])
def get_favorite_folders(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取收藏夹分类列表
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 按folder_name分组统计
    from sqlalchemy import func
    results = db.query(
        Favorite.folder_name,
        func.count(Favorite.id).label('count')
    ).filter(Favorite.user_id == user.id).group_by(Favorite.folder_name).all()

    return [FavoriteFolder(name=r[0], count=r[1]) for r in results]


class FavoriteFolderCreate(BaseModel):
    name: str


@router.post("/me/favorites/folders", response_model=FavoriteFolder)
def create_favorite_folder_placeholder(
    body: FavoriteFolderCreate,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Any:
    """
    登记收藏夹名称。空收藏夹无独立表记录，首次将房源「移动」到该名称后即出现在分组统计中。
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="收藏夹名称不能为空")
    return FavoriteFolder(name=name, count=0)


@router.put("/me/favorites/{unit_id}/folder")
def move_favorite_folder(
    unit_id: str,
    folder_name: str,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    移动收藏到指定收藏夹
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()

    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    fav.folder_name = folder_name
    db.commit()

    return {"message": "Moved to folder", "unit_id": unit_id, "folder": folder_name}


# =============================================================================
# 浏览历史接口
# =============================================================================

@router.get("/me/history", response_model=List[ViewHistoryResponse])
def get_view_history(
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取用户浏览历史
    
    按最后浏览时间倒序排列
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from sqlalchemy import func

    history = (
        db.query(UserViewHistory)
        .filter(UserViewHistory.user_id == user.id)
        .order_by(func.coalesce(UserViewHistory.last_viewed_at, UserViewHistory.created_at).desc())
        .limit(limit)
        .all()
    )

    return history


@router.post("/me/history", status_code=status.HTTP_201_CREATED)
def add_view_history(
    view: ViewHistoryCreate,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    记录浏览历史
    
    如果已浏览过，更新浏览次数和时间
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 检查是否已有记录
    existing = db.query(UserViewHistory).filter(
        UserViewHistory.user_id == user.id,
        UserViewHistory.unit_id == view.unit_id
    ).first()

    if existing:
        # 更新浏览次数和时间
        existing.view_count += 1
        existing.last_viewed_at = datetime.utcnow()
        if view.listing_data:
            existing.listing_data = view.listing_data
    else:
        # 创建新记录
        new_history = UserViewHistory(
            user_id=user.id,
            unit_id=view.unit_id,
            listing_data=view.listing_data,
            view_count=1,
            last_viewed_at=datetime.utcnow()
        )
        db.add(new_history)

    db.commit()

    return {"message": "View recorded", "unit_id": view.unit_id}


@router.delete("/me/history/{unit_id}")
def remove_view_history(
    unit_id: str,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    删除单条浏览历史
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    history = db.query(UserViewHistory).filter(
        UserViewHistory.user_id == user.id,
        UserViewHistory.unit_id == unit_id
    ).first()

    if history:
        db.delete(history)
        db.commit()

    return {"message": "History removed", "unit_id": unit_id}


@router.delete("/me/history")
def clear_view_history(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    清空所有浏览历史
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(UserViewHistory).filter(UserViewHistory.user_id == user.id).delete()
    db.commit()

    return {"message": "All history cleared"}


# =============================================================================
# 价格提醒接口
# =============================================================================

@router.get("/me/favorites/alerts")
def get_favorite_alerts(
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取收藏房源的价格提醒设置
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
                "current_price": alert.listing_data.get('price') if alert.listing_data else None,
                "created_at": alert.created_at.isoformat() if alert.created_at else None
            }
            for alert in alerts
        ],
        "total_enabled": len(alerts)
    }


@router.put("/me/favorites/{unit_id}/alert")
def update_favorite_alert(
    unit_id: str,
    enabled: bool = True,
    threshold: float = 0.10,
    current_username: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Any:
    """
    更新收藏房源的价格提醒设置
    
    - enabled: 是否启用价格提醒
    - threshold: 价格变动阈值 (0.1 = 10%)
    """
    user = get_user_by_username(db, username=current_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.unit_id == unit_id
    ).first()
    
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    fav.price_alert_enabled = enabled
    fav.alert_threshold = threshold
    db.commit()
    
    return {
        "message": "Alert settings updated",
        "unit_id": unit_id,
        "price_alert_enabled": enabled,
        "alert_threshold": threshold
    }
