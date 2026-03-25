"""
Recommendation API endpoints for personalized homestay suggestions.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    UserResponse
)
from app.services.recommender import recommendation_service
from app.core.security import get_current_user_id, get_optional_user
from app.core.recommend_travel import travel_purpose_for_condition_recommend
from app.db.database import get_db, get_user_by_username

router = APIRouter()


@router.get("/", response_model=RecommendationResponse)
def get_recommendations(
    district: Optional[str] = Query(None, description="行政区筛选"),
    trade_area: Optional[str] = Query(None, description="商圈筛选（需与行政区同时选用）"),
    price_min: Optional[float] = Query(None, description="最低价格"),
    price_max: Optional[float] = Query(None, description="最高价格"),
    capacity: Optional[int] = Query(None, description="容纳人数"),
    travel_purpose: Optional[str] = Query(
        None,
        description=(
            "出行目的英文 key: couple/family/business/exam/team_party/medical/pet_friendly/long_stay"
        ),
    ),
    facilities: Optional[str] = Query(
        None,
        description="核心设施需求, 逗号分隔: subway,projector,bathtub,cooking,pet 等",
    ),
    bedroom_count: Optional[int] = Query(None, description="卧室数"),
    top_k: int = Query(10, ge=1, le=50, description="返回数量"),
    current_username: Optional[str] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    智能推荐接口。

    用户选择出行目的、价格范围、核心设施等条件后，
    系统根据条件匹配度 + 相似度矩阵综合评分，返回最匹配的房源。
    """
    user_id = None
    facility_list: Optional[List[str]] = None
    if facilities:
        facility_list = [f.strip() for f in facilities.split(",") if f.strip()]

    if current_username:
        user = get_user_by_username(db, username=current_username)
        if user:
            user_id = str(user.id)
            if district is None and user.preferred_district:
                district = user.preferred_district
            if price_min is None and user.preferred_price_min:
                price_min = user.preferred_price_min
            if price_max is None and user.preferred_price_max:
                price_max = user.preferred_price_max
            if travel_purpose is None and user.travel_purpose:
                travel_purpose = travel_purpose_for_condition_recommend(user.travel_purpose)
            if facility_list is None and isinstance(user.required_facilities, list):
                mapped = recommendation_service.map_user_facilities_to_api_keys(
                    user.required_facilities
                )
                if mapped:
                    facility_list = mapped

    try:
        if travel_purpose or facility_list:
            return recommendation_service.get_condition_based_recommendations(
                travel_purpose=travel_purpose,
                facilities=facility_list,
                district=district,
                trade_area=trade_area,
                price_min=price_min,
                price_max=price_max,
                bedroom_count=bedroom_count,
                capacity=capacity,
                top_k=top_k,
            )

        return recommendation_service.get_recommendations(
            user_id=user_id,
            district=district,
            price_min=price_min,
            price_max=price_max,
            capacity=capacity,
            top_k=top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


@router.post("/", response_model=RecommendationResponse)
def post_recommendations(
    request: RecommendationRequest,
    current_username: Optional[str] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Get recommendations using POST request with body parameters."""
    user_id = request.user_id
    if current_username:
        user = get_user_by_username(db, username=current_username)
        if user:
            user_id = str(user.id)

    try:
        result = recommendation_service.get_recommendations(
            user_id=user_id,
            district=request.district,
            price_min=request.price_min,
            price_max=request.price_max,
            capacity=request.capacity,
            top_k=request.top_k,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


@router.get("/similar/{homestay_id}", response_model=RecommendationResponse)
def get_similar_homestays(
    homestay_id: str,
    top_k: int = Query(5, ge=1, le=20)
):
    """获取相似房源（基于预计算相似度矩阵）"""
    return recommendation_service.get_similar_homestays(homestay_id, top_k)


@router.get("/popular", response_model=RecommendationResponse)
def get_popular_homestays(
    district: Optional[str] = Query(None),
    days: int = Query(30, description="统计天数"),
    top_k: int = Query(10, ge=1, le=50)
):
    """获取热门房源"""
    return recommendation_service.get_popular_homestays(
        district=district, days=days, top_k=top_k
    )


@router.get("/personalized", response_model=RecommendationResponse)
def get_personalized_recommendations(
    current_username: Optional[str] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """个性化推荐 - 基于用户偏好设置"""
    user_prefs = {}
    if current_username:
        user = get_user_by_username(db, username=current_username)
        if user:
            user_prefs = {
                'preferred_district': user.preferred_district,
                'preferred_price_min': float(user.preferred_price_min) if user.preferred_price_min else None,
                'preferred_price_max': float(user.preferred_price_max) if user.preferred_price_max else None,
                'required_facilities': user.required_facilities,
                'travel_purpose': user.travel_purpose,
            }

    return recommendation_service.get_personalized_recommendations(
        user_preferences=user_prefs, top_k=10
    )
