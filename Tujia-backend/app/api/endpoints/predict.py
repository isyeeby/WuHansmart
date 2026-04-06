"""
Price prediction endpoints：线上定价锚点与 14 天曲线仅使用日级 XGBoost。
提供价格预测、14 天预测、因子分解、特征重要性等功能。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Any, Optional, List
from datetime import datetime, timedelta
from bisect import bisect_left

DAILY_PRICING_UNAVAILABLE_DETAIL = (
    "日级定价模型未就绪：请部署 xgboost_price_daily_model.pkl 与 feature_names_daily.json，"
    "并运行 scripts/train_model_daily_mysql.py 生成完整产物（含 encoder 与统计文件）。"
)
from app.models.schemas import PredictionRequest, PredictionResponse
from app.db.hive import execute_query_to_df
from app.db.database import get_db, SessionLocal
import logging
import pandas as pd
import numpy as np
import math

router = APIRouter()
logger = logging.getLogger(__name__)

# 特征名称中英文映射
FEATURE_NAME_MAP = {
    # 房源基本属性
    "bedrooms": "卧室数",
    "bed_count": "床位数",
    "capacity": "可住人数",
    "area": "面积",
    "bathrooms": "卫生间数",
    "bedroom_count": "卧室数",
    "area_sqm": "面积",
    "room_type": "房型",
    "house_type": "房屋类型",
    # 位置特征
    "district": "行政区",
    "trade_area": "商圈",
    "longitude": "经度",
    "latitude": "纬度",
    "district_encoded": "行政区编码",
    "trade_area_encoded": "商圈编码",
    # 评分与热度
    "rating": "评分",
    "favorite_count": "收藏数",
    "heat_score": "热度",
    "comment_count": "评论数",
    # 设施特征 - 布尔型
    "has_projector": "投影",
    "projector": "投影",
    "has_bathtub": "浴缸",
    "bathtub": "浴缸",
    "near_metro": "近地铁",
    "near_subway": "近地铁",
    "has_kitchen": "厨房",
    "kitchen": "厨房",
    "has_smart_lock": "智能锁",
    "smart_lock": "智能锁",
    "has_wifi": "WiFi",
    "wifi": "WiFi",
    "has_air_conditioning": "空调",
    "ac": "空调",
    "has_washer": "洗衣机",
    "washer": "洗衣机",
    "has_tv": "电视",
    "tv": "电视",
    "has_fridge": "冰箱",
    "fridge": "冰箱",
    "has_elevator": "电梯",
    "elevator": "电梯",
    "has_parking": "停车位",
    "free_parking": "免费停车",
    "paid_parking": "收费停车",
    "has_view": "景观",
    "view_type": "景观类型",
    "has_terrace": "露台",
    "terrace": "露台",
    "has_mahjong": "麻将机",
    "mahjong": "麻将机",
    "has_gym": "健身房",
    "has_pool": "游泳池",
    "has_breakfast": "早餐",
    "has_heater": "暖气",
    "hot_water": "热水",
    "has_tv": "电视",
    "dry_wet_sep": "干湿分离",
    "smart_toilet": "智能马桶",
    "pet_friendly": "可带宠物",
    "front_desk": "前台",
    "butler": "管家服务",
    "luggage": "行李寄存",
    "instant_confirm": "即时确认",
    "family_friendly": "亲子友好",
    "business": "商务型",
    # 景观细分
    "river_view": "江景",
    "lake_view": "湖景",
    "mountain_view": "山景",
    "city_view": "城市景观",
    "garden": "花园",
    "sunroom": "阳光房",
    # 派生特征
    "area_per_bedroom": "卧室平均面积",
    "facility_count": "设施数量",
    "is_large": "大户型",
    "is_budget": "经济型",
    "capacity_bedroom_ratio": "人均卧室数",
    "has_luxury_amenities": "豪华设施",
    # 目标编码特征
    "dist_mean": "行政区均价",
    "dist_median": "行政区中位数",
    "dist_std": "行政区价格波动",
    "dist_count": "行政区房源数",
    # 时间特征
    "is_weekend": "周末",
    "is_holiday": "节假日",
    "is_weekday": "工作日",
    "distance_to_metro": "距地铁距离",
    "distance_to_center": "距市中心距离",
    # 编码特征前缀
    "dist_": "商圈位置",
    "room_": "房型类型",
    "trade_": "商圈编码",
    "style_": "装修风格",
    "near_station": "近车站",
    "near_university": "近高校",
    "near_ski": "近滑雪",
    "big_projector": "大屏投影",
    "view_bathtub": "观景浴缸",
    "karaoke": "K歌设备",
    "oven": "烤箱",
    "free_water": "免费饮水",
    "style_modern": "现代风装修",
    "style_ins": "Ins风装修",
    "style_western": "西式装修",
    "style_chinese": "中式装修",
    "style_japanese": "日式装修",
    "real_photo": "实拍验真",
    "house_type_encoded": "房屋类型编码",
    "cal_n_days": "日历覆盖天数",
    "cal_mean": "日历均价",
    "cal_std": "日历价格波动",
    "cal_min": "日历最低价",
    "cal_max": "日历最高价",
    "cal_median": "日历价格中位数",
    "cal_cv": "日历价格变异系数",
    "cal_range_ratio": "日历价差比",
    "cal_bookable_ratio": "日历可订比例",
    "cal_weekend_premium": "日历周末溢价",
}

# 设施特征列表（用于相似度计算）
FACILITY_FEATURES = [
    "has_projector", "has_bathtub", "near_metro", "has_kitchen",
    "has_smart_lock", "has_wifi", "has_air_conditioning", "has_washer",
    "has_tv", "has_fridge", "has_elevator", "has_parking",
    "has_view", "has_terrace", "has_mahjong"
]


def _get_feature_display_name(feature: str) -> str:
    """
    获取特征的中文名称

    Args:
        feature: 英文特征名

    Returns:
        中文显示名称
    """
    # 直接匹配
    if feature in FEATURE_NAME_MAP:
        return FEATURE_NAME_MAP[feature]

    # 前缀匹配（如 dist_朝阳, room_entire）
    for prefix, name in FEATURE_NAME_MAP.items():
        if feature.startswith(prefix):
            if prefix.endswith("_") and len(feature) > len(prefix):
                suffix = feature[len(prefix) :]
                return f"{name}（{suffix}）"
            return name

    # 未收录：避免裸英文轴标签
    if feature.startswith("cal_"):
        return f"日历特征·{feature[4:].replace('_', ' ')}"
    if feature.startswith("style_"):
        return f"装修风格·{feature[6:].replace('_', ' ')}"
    return f"模型特征（{feature}）"


def _daily_base_price_optional(req: PredictionRequest) -> Optional[float]:
    """日级锚定日基准价；模型未部署或预测无 base_price 时返回 None（不抛 HTTP）。"""
    from app.services.daily_price_service import daily_forecast_service

    if not daily_forecast_service.available():
        return None
    daily_out = daily_forecast_service.predict_forecast_14(req, n_days=14)
    if daily_out is None or daily_out.get("base_price") is None:
        return None
    return float(daily_out["base_price"])


def _require_daily_base_price(req: PredictionRequest) -> float:
    """定价锚点：仅日级 XGBoost；不可用时 HTTP 503。"""
    p = _daily_base_price_optional(req)
    if p is None:
        raise HTTPException(status_code=503, detail=DAILY_PRICING_UNAVAILABLE_DETAIL)
    return p


def _calculate_confidence(predicted_price: float, district_avg: float, sample_count: int = 100) -> float:
    """
    计算预测置信度

    基于以下因素计算：
    1. 预测价格与商圈均价的偏差（偏差越小置信度越高）
    2. 样本数量（样本越多置信度越高）

    Args:
        predicted_price: 预测价格
        district_avg: 商圈均价
        sample_count: 训练样本数量

    Returns:
        置信度 (0.5-0.95)
    """
    # 基于样本量的置信度分量
    sample_confidence = min(1.0, sample_count / 500.0) * 0.3

    # 基于预测偏差的置信度分量
    if district_avg > 0:
        deviation = abs(predicted_price - district_avg) / district_avg
        deviation_confidence = max(0, 1.0 - deviation) * 0.5
    else:
        deviation_confidence = 0.3

    # 基础置信度
    base_confidence = 0.2

    total = base_confidence + sample_confidence + deviation_confidence
    return round(min(0.95, max(0.5, total)), 2)


def _calculate_similarity(target: dict, competitor: dict) -> float:
    """
    计算两个房源的相似度（加权余弦相似度）

    基于价格、评分、收藏数、面积、卧室数、床位数计算

    Args:
        target: 目标房源特征
        competitor: 竞品房源特征

    Returns:
        相似度分数 (0-100)
    """
    # 特征及权重配置
    # 价格和房型特征权重较高，收藏数和评分权重适中
    feature_weights = {
        'price': 0.25,           # 价格权重最高
        'rating': 0.15,          # 评分
        'favorite_count': 0.10,  # 收藏数
        'area': 0.15,            # 面积
        'bedroom_count': 0.15,   # 卧室数
        'bed_count': 0.10,       # 床位数
        'capacity': 0.10,        # 可住人数
    }

    vec1 = []
    vec2 = []
    weights = []

    for f, w in feature_weights.items():
        v1 = target.get(f, 0) or 0
        v2 = competitor.get(f, 0) or 0
        vec1.append(float(v1))
        vec2.append(float(v2))
        weights.append(w)

    # 归一化向量
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    weights = np.array(weights)

    # 加权归一化
    vec1_weighted = vec1 * weights
    vec2_weighted = vec2 * weights

    norm1 = np.linalg.norm(vec1_weighted)
    norm2 = np.linalg.norm(vec2_weighted)

    if norm1 == 0 or norm2 == 0:
        return 50.0  # 无法计算时返回中等相似度

    # 加权余弦：点积与范数均基于 vec * weights，与 norm1/norm2 一致
    cosine_sim = float(np.dot(vec1_weighted, vec2_weighted) / (norm1 * norm2))

    # 转换为0-100分数
    similarity_score = (cosine_sim + 1) / 2 * 100

    return round(max(0, min(100, similarity_score)), 1)


@router.post("/reload-model")
def reload_model():
    """
    重新加载模型（热重载）：推荐相似度矩阵（ModelManager）与日级定价 pkl/编码器。
    """
    try:
        from app.services.daily_price_service import daily_forecast_service
        from app.services.model_manager import model_manager

        model_manager.reload_models()
        daily_forecast_service.reload_from_disk()
        return {
            "status": "success",
            "message": "推荐矩阵与日级定价模型已从磁盘重新加载",
        }
    except Exception as e:
        logger.error(f"Failed to reload models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload models: {str(e)}")


# =============================================================================
# 新增：价格预测接口（文档定义）
# =============================================================================

@router.post("/price")
def predict_listing_price(request: dict):
    """
    价格预测：仅日级锚定日基准价；模型未就绪时 HTTP 503。返回区间与简要因子说明。
    """
    try:
        # 从请求中提取特征
        district = request.get("district", "")
        trade_area = request.get("trade_area") or district  # 商圈（如果没有则使用行政区）
        bedroom_count = request.get("bedroom_count", 1)
        bed_count = request.get("bed_count", bedroom_count)  # 默认用卧室数
        bathroom_count = request.get("bathroom_count", 1)
        area = request.get("area", 50)
        capacity = request.get("capacity", bed_count * 2)  # 默认床位数*2

        # 设施标签
        has_metro = request.get("has_metro", False)
        has_kitchen = request.get("has_kitchen", False)
        has_projector = request.get("has_projector", False)
        has_washer = request.get("has_washer", False)
        has_smart_lock = request.get("has_smart_lock", False)
        has_air_conditioner = request.get("has_air_conditioner", True)
        has_bathtub = request.get("has_bathtub", False)
        has_tv = request.get("has_tv", False)
        has_heater = request.get("has_heater", False)
        near_metro = request.get("near_metro", False)
        has_elevator = request.get("has_elevator", False)
        has_fridge = request.get("has_fridge", False)
        has_view = request.get("has_view", False)
        has_terrace = request.get("has_terrace", False)
        has_mahjong = request.get("has_mahjong", False)
        has_big_living_room = request.get("has_big_living_room", False)
        has_parking = request.get("has_parking", False)
        pet_friendly = request.get("pet_friendly", False)

        # 景观特色
        view_type = request.get("view_type", "")
        river_view = request.get("river_view", False) or ("江景" in view_type)
        lake_view = request.get("lake_view", False) or ("湖景" in view_type)
        mountain_view = request.get("mountain_view", False) or ("山景" in view_type)
        garden = request.get("garden", False)

        # 构建预测请求
        pred_request = PredictionRequest(
            district=district,
            trade_area=trade_area,  # 商圈特征
            unit_id=request.get("unit_id") or request.get("unitId"),
            room_type="整套房源" if bedroom_count >= 1 else "独立房间",
            capacity=capacity,
            bedrooms=bedroom_count,
            bed_count=bed_count,
            bathrooms=bathroom_count,
            area=area,
            has_wifi=True,
            has_kitchen=has_kitchen,
            has_air_conditioning=has_air_conditioner,
            has_projector=has_projector,
            has_bathtub=has_bathtub,
            has_washer=has_washer,
            has_smart_lock=has_smart_lock,
            has_tv=has_tv,
            has_heater=has_heater,
            near_metro=near_metro or has_metro,
            near_station=request.get("near_station", False),
            near_university=request.get("near_university", False),
            near_ski=request.get("near_ski", False),
            has_elevator=has_elevator,
            has_fridge=has_fridge,
            has_view=has_view or river_view or lake_view or mountain_view,
            view_type=view_type,
            has_terrace=has_terrace,
            has_mahjong=has_mahjong,
            has_big_living_room=has_big_living_room,
            has_parking=has_parking,
            pet_friendly=pet_friendly,
            garden=garden,
        )

        predicted_price = _require_daily_base_price(pred_request)
        pred_src = "xgboost_daily"
        logger.info(
            "预测结果 - district: %s, area: %s, bedroom_count: %s, predicted_price: %s, model: %s",
            district,
            area,
            bedroom_count,
            predicted_price,
            pred_src,
        )

        # 计算价格区间
        lower = round(predicted_price * 0.88, 2)
        upper = round(predicted_price * 1.12, 2)

        # 获取商圈均价
        district_avg = _get_district_average(district) or 200

        # 计算影响因素（仅用于展示，不再修改预测价格）
        factors = []

        if district:
            factors.append({
                "feature": "行政区",
                "impact": f"+{round((district_avg - 200) / 200 * 100, 0)}%" if district_avg > 200 else f"{round((district_avg - 200) / 200 * 100, 0)}%",
                "detail": f"{district}均价{'较高' if district_avg > 200 else '适中'}"
            })

        if near_metro or has_metro:
            factors.append({
                "feature": "近地铁",
                "impact": "已计入",
                "detail": "交通便利溢价已包含在预测价格中"
            })

        if has_projector:
            factors.append({
                "feature": "投影",
                "impact": "已计入",
                "detail": "热门设施溢价已包含在预测价格中"
            })

        if has_bathtub:
            factors.append({
                "feature": "浴缸",
                "impact": "已计入",
                "detail": "品质设施溢价已包含在预测价格中"
            })

        if river_view or lake_view:
            factors.append({
                "feature": "景观房",
                "impact": "已计入",
                "detail": "景观溢价已包含在预测价格中"
            })

        if has_terrace:
            factors.append({
                "feature": "观景露台",
                "impact": "已计入",
                "detail": "露台溢价已包含在预测价格中"
            })

        return {
            "predicted_price": round(predicted_price, 2),
            "prediction_model": pred_src,
            "price_range": {
                "lower": lower,
                "upper": upper
            },
            "confidence": _calculate_confidence(predicted_price, district_avg),
            "factors": factors[:5],
            "district_avg_price": district_avg
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in predict_listing_price: {e}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.get("/competitors/{unit_id}")
def get_competitors_analysis(
    unit_id: str,
    limit: int = Query(10, ge=1, le=20, description="数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取竞品分析
    
    获取指定房源的同商圈竞品分析
    """
    from app.db.database import Listing
    
    # 获取目标房源
    target = db.query(Listing).filter(Listing.unit_id == unit_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="房源不存在")
    
    # 获取同商圈房源作为竞品
    competitors_query = db.query(Listing).filter(
        Listing.district == target.district,
        Listing.unit_id != unit_id
    ).order_by(Listing.favorite_count.desc()).limit(limit)
    
    competitors = competitors_query.all()
    
    # 获取市场分析
    all_prices = [float(c.final_price) if c.final_price is not None else 0.0 for c in competitors]  # type: ignore
    all_ratings = [float(c.rating) if c.rating is not None else 0.0 for c in competitors]  # type: ignore

    target_price = float(target.final_price) if target.final_price is not None else 0.0  # type: ignore
    merged_prices = sorted(all_prices + [target_price])
    price_rank = bisect_left(merged_prices, target_price) + 1 if merged_prices else 1

    def _listing_feature_dict(row: Any) -> dict:
        return {
            "price": float(row.final_price) if row.final_price is not None else 0.0,
            "rating": float(row.rating) if row.rating is not None else 0.0,
            "favorite_count": int(row.favorite_count) if row.favorite_count is not None else 0,
            "area": float(row.area) if row.area is not None else 0.0,
            "bedroom_count": int(row.bedroom_count) if row.bedroom_count is not None else 0,
            "bed_count": int(row.bed_count) if row.bed_count is not None else 0,
            "capacity": int(row.capacity) if row.capacity is not None else 0,
        }

    # 构建竞品列表
    competitors_list = []
    target_features = _listing_feature_dict(target)

    for c in competitors:
        c_price = float(c.final_price) if c.final_price is not None else 0.0  # type: ignore
        c_rating = float(c.rating) if c.rating is not None else 0.0  # type: ignore
        c_fav = int(c.favorite_count) if c.favorite_count is not None else 0  # type: ignore

        competitor_features = _listing_feature_dict(c)

        competitors_list.append({
            "unit_id": c.unit_id,
            "title": c.title,
            "price": c_price,
            "rating": c_rating,
            "favorite_count": c_fav,
            "house_tags": c.house_tags,
            "similarity_score": _calculate_similarity(target_features, competitor_features),
            "price_diff": round(c_price - target_price, 2)
        })

    return {
        "target_listing": {
            "unit_id": target.unit_id,
            "title": target.title,
            "price": target_price,
            "rating": float(target.rating) if target.rating is not None else 0.0  # type: ignore
        },
        "competitors": competitors_list,
        "market_analysis": {
            "avg_price": round(sum(all_prices) / len(all_prices), 2) if all_prices else 0,
            "min_price": min(all_prices) if all_prices else 0,
            "max_price": max(all_prices) if all_prices else 0,
            "avg_rating": round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else 0,
            "total_competitors": len(competitors)
        },
        "position": {
            "price_rank": price_rank,
            "price_percentile": round(
                price_rank / len(merged_prices) * 100, 1
            )
            if merged_prices
            else 50,
            "rating_rank": 0,
            "methodology": (
                "similarity_score：对 price/rating/favorite_count/area/bedroom_count/bed_count/capacity "
                "做逐维标量后按固定权重 w 计算加权余弦，再线性映射到 0–100；缺失维在向量中为 0。"
                " price_rank / price_percentile：将目标价与当前返回的竞品价合并排序后取名次（bisect_left+1）"
                " / 总数×100；与 GET /api/my-listings/{id}/competitors 的选池与加权算法不同，勿横向对比相似度。"
            ),
        },
    }


@router.post("/", response_model=PredictionResponse)
def predict_price(request: PredictionRequest):
    """
    单点定价预测：仅日级 XGBoost 锚定日基准价；模型未就绪时 HTTP 503。
    """
    try:
        predicted_price = _require_daily_base_price(request)
        pred_src = "xgboost_daily"

        # Calculate confidence interval (e.g., +/- 15%)
        lower_bound = round(predicted_price * 0.85, 2)
        upper_bound = round(predicted_price * 1.15, 2)

        # Get district average for context
        district_avg = _get_district_average(request.district)

        # Generate pricing suggestion
        suggestion = _generate_suggestion(predicted_price, district_avg, request)

        return PredictionResponse(
            predicted_price=predicted_price,
            confidence_interval=[lower_bound, upper_bound],
            features_used=request.model_dump(),
            district_avg=district_avg,
            suggestion=suggestion,
            prediction_model=pred_src,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting price: {e}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.get("/quick")
def quick_predict(
    district: str = Query(..., description="商圈"),
    room_type: str = Query(..., description="房型"),
    capacity: int = Query(..., ge=1, le=20, description="可住人数"),
    bedrooms: int = Query(..., ge=0, description="卧室数"),
    has_wifi: bool = Query(True, description="是否有WiFi"),
    is_weekend: bool = Query(False, description="是否周末"),
    unit_id: Optional[str] = Query(
        None, description="可选；定价不读库，不因 unit_id 拉取 price_calendars"
    ),
):
    """
    Quick price prediction using query parameters (GET method).
    仅日级锚定日基准价；模型未就绪时 HTTP 503。
    """
    request = PredictionRequest(
        district=district,
        room_type=room_type,
        capacity=capacity,
        bedrooms=bedrooms,
        bed_count=1,
        bathrooms=1,
        area=50,
        has_wifi=has_wifi,
        is_weekend=is_weekend,
        unit_id=unit_id,
    )

    try:
        predicted_price = _require_daily_base_price(request)
        return {
            "predicted_price": predicted_price,
            "prediction_model": "xgboost_daily",
            "district": district,
            "currency": "CNY"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in quick predict: {e}")
        raise HTTPException(status_code=500, detail="预测失败")


@router.get("/district-average/{district}")
def get_district_average_price(district: str):
    """
    Get average price for a specific district.
    """
    avg_price = _get_district_average(district)
    if avg_price is None:
        raise HTTPException(status_code=404, detail=f"未找到行政区: {district}")

    return {
        "district": district,
        "average_price": avg_price,
        "sample_size": 100  # Would come from actual query
    }


def _get_district_average(district: str) -> Optional[float]:
    """
    Helper function to get district average price from MySQL (真实数据).
    """
    from app.db.database import SessionLocal, Listing
    
    db = SessionLocal()
    try:
        # 从MySQL获取真实数据
        result = db.query(Listing).filter(
            Listing.district == district,
            Listing.final_price.isnot(None)
        ).all()
        
        if result:
            prices = [float(l.final_price) for l in result if l.final_price is not None]  # type: ignore
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"从MySQL获取{district}均价: {avg_price:.2f}元 (样本数: {len(prices)})")
                return round(avg_price, 2)
        
        logger.warning(f"MySQL中未找到商圈 {district} 的价格数据")
        return None
        
    except Exception as e:
        logger.error(f"获取商圈均价失败: {e}")
        return None
    finally:
        db.close()


def _generate_suggestion(predicted_price: float,
                         district_avg: Optional[float],
                         request: PredictionRequest) -> str:
    """
    Generate a pricing suggestion based on prediction and market context.
    """
    if district_avg is None:
        return "建议参考周边同类房源定价"

    diff_percent = (predicted_price - district_avg) / district_avg

    if diff_percent > 0.2:
        return f"预测价格高于{district_avg:.0f}元商圈均价{diff_percent*100:.0f}%，建议确认房源特色是否支撑这一定价"
    elif diff_percent > 0.05:
        return f"预测价格略高于商圈均价，适合有特色的精品房源"
    elif diff_percent > -0.05:
        return "预测价格与商圈均价持平，具有竞争力"
    elif diff_percent > -0.2:
        return f"预测价格低于商圈均价，可考虑适当提价或检查房源条件"
    else:
        return f"预测价格显著低于商圈均价，建议检查是否有未录入的房源优势"


@router.post("/batch")
def batch_predict(requests: List[PredictionRequest]):
    """
    批量定价预测：每条仅日级锚定日基准价；单条模型不可用时标记 failed（不中断整批）。
    """
    results = []
    for request in requests:
        try:
            p = _daily_base_price_optional(request)
            if p is None:
                results.append({
                    "district": request.district,
                    "error": DAILY_PRICING_UNAVAILABLE_DETAIL,
                    "status": "failed",
                })
            else:
                results.append({
                    "district": request.district,
                    "predicted_price": p,
                    "prediction_model": "xgboost_daily",
                    "status": "success",
                })
        except Exception as e:
            results.append({
                "district": request.district,
                "error": str(e),
                "status": "failed"
            })

    return {"results": results, "total": len(results), "successful": sum(1 for r in results if r["status"] == "success")}


# =============================================================================
# 新增：14天价格预测
# =============================================================================

@router.get("/forecast")
def price_forecast(
    district: str = Query(..., description="行政区"),
    trade_area: str = Query(None, description="商圈（更精细的位置）"),
    room_type: str = Query(..., description="房型"),
    capacity: int = Query(..., ge=1, le=20, description="可住人数"),
    bedrooms: int = Query(..., ge=0, description="卧室数"),
    bed_count: int = Query(1, ge=1, description="床位数"),
    area: int = Query(50, ge=10, le=500, description="面积"),
    has_wifi: bool = Query(True, description="WiFi"),
    has_air_conditioning: bool = Query(True, description="空调"),
    has_kitchen: bool = Query(False, description="厨房"),
    has_projector: bool = Query(False, description="投影"),
    has_bathtub: bool = Query(False, description="浴缸"),
    has_washer: bool = Query(False, description="洗衣机"),
    has_smart_lock: bool = Query(False, description="智能锁"),
    has_tv: bool = Query(False, description="电视"),
    has_heater: bool = Query(False, description="暖气"),
    near_metro: bool = Query(False, description="近地铁"),
    has_elevator: bool = Query(False, description="电梯"),
    has_fridge: bool = Query(False, description="冰箱"),
    has_view: bool = Query(False, description="景观房"),
    view_type: Optional[str] = Query(None, description="景观类型，如 江景/湖景/山景，可多选逗号拼接"),
    has_terrace: bool = Query(False, description="观景露台"),
    has_mahjong: bool = Query(False, description="麻将机"),
    has_big_living_room: bool = Query(False, description="大客厅"),
    pet_friendly: bool = Query(False, description="可带宠物"),
    has_parking: bool = Query(False, description="停车位/免费停车"),
    near_station: bool = Query(False, description="近火车站"),
    near_university: bool = Query(False, description="近高校"),
    near_ski: bool = Query(False, description="近滑雪场"),
    garden: bool = Query(False, description="私家花园/小院"),
    base_price: Optional[float] = Query(None, description="当前定价（可选；仅作查询参数记录）"),
    unit_id: Optional[str] = Query(None, description="平台房源ID；日级模型路径下仍不读 price_calendars"),
):
    """
    14 天价格预测：仅日级 XGBoost（逐日预测与区间）。模型未部署或推理失败时 HTTP 503。
    """
    try:
        from app.services.daily_price_service import daily_forecast_service

        base_request = PredictionRequest(
            district=district,
            trade_area=trade_area or district,
            room_type=room_type,
            capacity=capacity,
            bedrooms=bedrooms,
            bed_count=bed_count,
            bathrooms=1,
            area=area,
            has_wifi=has_wifi,
            has_air_conditioning=has_air_conditioning,
            has_kitchen=has_kitchen,
            has_projector=has_projector,
            has_bathtub=has_bathtub,
            has_washer=has_washer,
            has_smart_lock=has_smart_lock,
            has_tv=has_tv,
            has_heater=has_heater,
            near_metro=near_metro,
            has_elevator=has_elevator,
            has_fridge=has_fridge,
            has_view=has_view,
            view_type=view_type,
            has_terrace=has_terrace,
            has_mahjong=has_mahjong,
            has_big_living_room=has_big_living_room,
            pet_friendly=pet_friendly,
            has_parking=has_parking,
            near_station=near_station,
            near_university=near_university,
            near_ski=near_ski,
            garden=garden,
            unit_id=unit_id,
        )
        if not daily_forecast_service.available():
            raise HTTPException(status_code=503, detail=DAILY_PRICING_UNAVAILABLE_DETAIL)
        daily_out = daily_forecast_service.predict_forecast_14(base_request, n_days=14)
        if daily_out is None:
            raise HTTPException(status_code=503, detail=DAILY_PRICING_UNAVAILABLE_DETAIL)
        return daily_out

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in price forecast: {e}")
        raise HTTPException(status_code=500, detail=f"价格预测失败: {str(e)}")


# =============================================================================
# 新增：定价因子分解
# =============================================================================

@router.post("/factor-decomposition")
def factor_decomposition(request: dict):
    """
    定价因子敏感度分析（Leave-One-Out Sensitivity）

    对用户提交的房源特征，逐项「关闭 / 降级」并重新预测，
    测量每项特征被移除后价格的变化量（即该项对最终定价的边际贡献）。
    设施逐项独立展示，不合并，不保留残差项。
    仅使用日级 XGBoost 锚定日基准价与 Gain 重要性；模型未就绪时 HTTP 503。
    """
    try:
        from app.models.schemas import PredictionRequest
        from app.services.daily_price_service import daily_forecast_service

        def build_request(**overrides):
            base = {
                'district': request.get('district', '武昌区'),
                'trade_area': request.get('trade_area'),
                'room_type': request.get('room_type', '整套'),
                'capacity': request.get('capacity', 4),
                'bedrooms': request.get('bedrooms', 2),
                'bed_count': request.get('bed_count', 2),
                'bathrooms': request.get('bathrooms', 1),
                'area': request.get('area', 80),
                'has_wifi': request.get('has_wifi', True),
                'has_kitchen': request.get('has_kitchen', False),
                'has_air_conditioning': request.get('has_air_conditioning', True),
                'has_projector': request.get('has_projector', False),
                'has_bathtub': request.get('has_bathtub', False),
                'has_washer': request.get('has_washer', False),
                'has_smart_lock': request.get('has_smart_lock', False),
                'has_tv': request.get('has_tv', False),
                'has_heater': request.get('has_heater', False),
                'near_metro': request.get('near_metro', False),
                'near_station': request.get('near_station', False),
                'near_university': request.get('near_university', False),
                'near_ski': request.get('near_ski', False),
                'has_elevator': request.get('has_elevator', False),
                'has_fridge': request.get('has_fridge', False),
                'has_view': request.get('has_view', False),
                'view_type': request.get('view_type'),
                'has_terrace': request.get('has_terrace', False),
                'has_mahjong': request.get('has_mahjong', False),
                'has_big_living_room': request.get('has_big_living_room', False),
                'has_parking': request.get('has_parking', False),
                'pet_friendly': request.get('pet_friendly', False),
                'garden': request.get('garden', False),
            }
            base.update(overrides)
            return PredictionRequest(**base)

        current_price = _require_daily_base_price(build_request())
        ref_src = "xgboost_daily"
        district_avg = _get_district_average(request.get('district', '武昌区')) or 200

        factors = []

        def _add(label: str, value_desc: str, counterfactual_desc: str, **overrides):
            cf_price = _require_daily_base_price(build_request(**overrides))
            delta = round(current_price - cf_price, 1)
            if abs(delta) < 0.5:
                return
            pct = round(delta / current_price * 100, 1) if current_price > 0 else 0
            factors.append({
                "factor": label,
                "your_value": value_desc,
                "baseline": counterfactual_desc,
                "delta": delta,
                "pct": pct,
                "direction": "up" if delta > 0 else "down",
            })

        # 数值特征：逐项降为市场常见基线
        user_area = request.get('area', 80)
        user_bedrooms = request.get('bedrooms', 2)
        user_bed_count = request.get('bed_count', user_bedrooms)
        user_capacity = request.get('capacity', 4)

        _add("面积", f"{user_area}㎡", "50㎡", area=50)
        if user_bedrooms > 1:
            _add("卧室数", f"{user_bedrooms}间", "1间", bedrooms=1, bed_count=1)
        if user_bed_count > 1 and user_bed_count != user_bedrooms:
            _add("床位数", f"{user_bed_count}张", "1张", bed_count=1)
        if user_capacity > 2:
            _add("可住人数", f"{user_capacity}人", "2人", capacity=2)

        # 设施：每项独立 leave-one-out
        facility_items = [
            ('has_wifi', 'WiFi'), ('has_air_conditioning', '空调'),
            ('has_kitchen', '厨房'), ('has_projector', '投影'),
            ('has_bathtub', '浴缸'), ('has_washer', '洗衣机'),
            ('has_smart_lock', '智能锁'), ('has_tv', '电视'),
            ('has_heater', '暖气'), ('near_metro', '近地铁'),
            ('near_station', '近火车站'), ('near_university', '近高校'),
            ('near_ski', '近滑雪场'),
            ('has_elevator', '电梯'), ('has_fridge', '冰箱'),
            ('has_terrace', '露台'), ('has_mahjong', '麻将机'),
            ('has_parking', '停车位'), ('pet_friendly', '可带宠物'),
            ('has_big_living_room', '大客厅'), ('garden', '私家花园'),
        ]
        for attr, label in facility_items:
            if request.get(attr, False):
                _add(label, "有", "无", **{attr: False})

        # 景观
        if request.get('has_view', False):
            vt = request.get('view_type', '景观')
            _add(f"景观({vt})", "有", "无", has_view=False, view_type=None)

        # 按绝对影响排序
        factors.sort(key=lambda f: abs(f["delta"]), reverse=True)

        # 全局特征重要性：与日级基准价同源
        global_importance = []
        raw_importance = daily_forecast_service.get_feature_importance_gain()
        if raw_importance:
            total = sum(raw_importance.values())
            if total > 0:
                for feat, score in sorted(raw_importance.items(), key=lambda x: x[1], reverse=True)[:10]:
                    display_name = _get_feature_display_name(feat)
                    global_importance.append({
                        "feature": feat,
                        "display_name": display_name if display_name != feat else feat,
                        "importance": round(score / total * 100, 1),
                    })

        dm = daily_forecast_service.get_meta()
        vmae = dm.get("val_mae_price")
        model_info = {
            "r2": None,
            "mae": round(float(vmae), 2) if vmae is not None else None,
            "mape": None,
            "sample_count": None,
            "feature_count": None,
            "trained_at": None,
        }

        methodology = {
            "name": "逐项敏感度分析（日级 XGBoost · 锚定日基准价）",
            "description": (
                "基于日级定价模型对「今日起第 1 天」的模型基准价：保持其他特征不变，将目标特征恢复为市场常见基线后重算基准价，"
                "得到各因素对锚定日建议价的边际贡献；与顶部价格日历同源。"
            ),
        }

        return {
            "predicted_price": round(current_price, 2),
            "district_avg_price": round(district_avg, 2),
            "reference_model": ref_src,
            "factors": factors,
            "global_importance": global_importance,
            "model_info": model_info,
            "methodology": methodology,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in factor decomposition: {e}")
        raise HTTPException(status_code=500, detail=f"因子分解失败: {str(e)}")


# =============================================================================
# 新增：特征重要性
# =============================================================================

@router.get("/feature-importance")
def get_feature_importance():
    """
    特征重要性：日级 XGBoost 的 Gain；日级未部署或无法提取重要性时返回业务占位。
    """
    from app.services.daily_price_service import daily_forecast_service

    daily_imp = daily_forecast_service.get_feature_importance_gain() if daily_forecast_service.available() else None
    if daily_imp:
        total_importance = sum(daily_imp.values())
        if total_importance > 0:
            formatted_features = []
            for feature, score in sorted(daily_imp.items(), key=lambda x: x[1], reverse=True):
                formatted_features.append({
                    "feature": feature,
                    "display_name": _get_feature_display_name(feature),
                    "importance": round(score / total_importance, 4),
                    "raw_score": round(score, 2)
                })
            return {
                "source": "xgboost_daily",
                "is_model_derived": True,
                "features": formatted_features[:10],
                "total_features": len(daily_imp),
                "note": "日级定价模型的 Gain 重要性，与智能定价锚定日预测同源",
            }

    return {
        "source": "business_logic",
        "is_model_derived": False,
        "features": [
            {"feature": "商圈位置", "importance": 0.35, "description": "不同商圈价格差异显著"},
            {"feature": "房型类型", "importance": 0.25, "description": "整套/独立房间/合住价格差异"},
            {"feature": "容纳人数", "importance": 0.15, "description": "可住人数直接影响定价"},
            {"feature": "卧室数量", "importance": 0.10, "description": "卧室数影响舒适度"},
            {"feature": "停车位", "importance": 0.08, "description": "停车位是稀缺资源"},
            {"feature": "厨房设施", "importance": 0.04, "description": "可做饭提升长住价值"},
            {"feature": "WiFi", "importance": 0.03, "description": "基础必备设施"}
        ],
        "note": (
            "日级模型未部署或无法读取 Gain 时使用业务占位；部署 xgboost_price_daily_model.pkl 后"
            "将显示与定价同源的特征重要性"
        ),
    }


# =============================================================================
# 新增：竞争力评估
# =============================================================================

@router.post("/competitiveness")
def competitiveness_assessment(request: dict):
    """
    竞争力评估

    核心逻辑：
    1. 用户提交房源特征和当前定价
    2. 使用日级模型锚定日「模型基准价」作为合理价（模型未就绪时 HTTP 503）
    3. 对比用户定价与合理价格，评估定价竞争力

    竞争力定义：
    - 用户定价 < 合理价格 → 高竞争力（性价比高，对租客有吸引力）
    - 用户定价 ≈ 合理价格 → 适中竞争力（定价合理）
    - 用户定价 > 合理价格 → 低竞争力（可能定价过高）
    """
    try:
        from app.models.schemas import PredictionRequest

        # 获取用户当前定价（必需参数）
        user_price = request.get("current_price") or request.get("user_price")
        if not user_price:
            raise HTTPException(
                status_code=400,
                detail="请提供当前定价(current_price)以评估竞争力"
            )

        user_price = float(user_price)

        # 构建预测请求
        pred_request = PredictionRequest(
            district=request.get('district', '武昌区'),
            trade_area=request.get('trade_area'),
            unit_id=request.get('unit_id') or request.get('unitId'),
            room_type=request.get('room_type', '整套'),
            capacity=request.get('capacity', 4),
            bedrooms=request.get('bedrooms', 2),
            bed_count=request.get('bed_count', 2),
            bathrooms=request.get('bathrooms', 1),
            area=request.get('area', 80),
            has_wifi=request.get('has_wifi', True),
            has_kitchen=request.get('has_kitchen', False),
            has_air_conditioning=request.get('has_air_conditioning', True),
            has_projector=request.get('has_projector', False),
            has_bathtub=request.get('has_bathtub', False),
            has_washer=request.get('has_washer', False),
            has_smart_lock=request.get('has_smart_lock', False),
            has_tv=request.get('has_tv', False),
            has_heater=request.get('has_heater', False),
            near_metro=request.get('near_metro', False),
            near_station=request.get('near_station', False),
            near_university=request.get('near_university', False),
            near_ski=request.get('near_ski', False),
            has_elevator=request.get('has_elevator', False),
            has_fridge=request.get('has_fridge', False),
            has_view=request.get('has_view', False),
            view_type=request.get('view_type'),
            has_terrace=request.get('has_terrace', False),
            has_mahjong=request.get('has_mahjong', False),
            has_big_living_room=request.get('has_big_living_room', False),
            has_parking=request.get('has_parking', False),
            pet_friendly=request.get('pet_friendly', False),
            garden=request.get('garden', False),
        )

        # 合理价格：与日级日历「模型基准价」同源
        predicted_price = _require_daily_base_price(pred_request)
        fair_src = "xgboost_daily"

        # 获取商圈均价作为参考
        district_avg = _get_district_average(request.get('district', '武昌区')) or 200

        # ========== 核心竞争力计算 ==========
        # 价格比率 = 用户定价 / 合理价格
        price_ratio = user_price / predicted_price if predicted_price > 0 else 1.0

        # 竞争力评分（0-100分）
        # 价格比率越低（性价比越高），竞争力越强
        if price_ratio <= 0.80:
            # 用户定价远低于合理价格，极具竞争力
            competitiveness_score = 95
            competitiveness_level = "极具竞争力"
            price_comment = f"定价{user_price}元，低于合理价{round((1-price_ratio)*100)}%，性价比极高"
        elif price_ratio <= 0.90:
            competitiveness_score = 80
            competitiveness_level = "高竞争力"
            price_comment = f"定价{user_price}元，略低于合理价，有价格优势"
        elif price_ratio <= 1.00:
            competitiveness_score = 65
            competitiveness_level = "竞争力适中"
            price_comment = f"定价{user_price}元，与合理价基本持平，定价合理"
        elif price_ratio <= 1.10:
            competitiveness_score = 50
            competitiveness_level = "竞争力偏弱"
            price_comment = f"定价{user_price}元，略高于合理价{round((price_ratio-1)*100)}%，建议优化"
        elif price_ratio <= 1.20:
            competitiveness_score = 35
            competitiveness_level = "竞争力较弱"
            price_comment = f"定价{user_price}元，高于合理价{round((price_ratio-1)*100)}%，需增强特色"
        else:
            competitiveness_score = 20
            competitiveness_level = "缺乏竞争力"
            price_comment = f"定价{user_price}元，显著高于合理价{round((price_ratio-1)*100)}%，建议重新定价"

        # ========== 设施配置评分 ==========
        facility_score = 0
        facilities = []

        if request.get('has_projector'):
            facilities.append("投影")
            facility_score += 5
        if request.get('has_bathtub'):
            facilities.append("浴缸")
            facility_score += 5
        if request.get('near_metro'):
            facilities.append("近地铁")
            facility_score += 6
        if request.get('has_terrace'):
            facilities.append("露台")
            facility_score += 4
        if request.get('has_mahjong'):
            facilities.append("麻将机")
            facility_score += 4
        if request.get('has_kitchen'):
            facilities.append("厨房")
            facility_score += 3
        if request.get('has_washer'):
            facilities.append("洗衣机")
            facility_score += 2
        if request.get('has_smart_lock'):
            facilities.append("智能锁")
            facility_score += 2
        if request.get('has_elevator'):
            facilities.append("电梯")
            facility_score += 2
        if request.get('has_fridge'):
            facilities.append("冰箱")
            facility_score += 2
        if request.get('has_view'):
            facilities.append(request.get('view_type', '景观'))
            facility_score += 5
        if request.get('has_parking'):
            facilities.append("停车位")
            facility_score += 4

        # 综合得分 = 价格竞争力(70%) + 设施配置(30%)
        final_score = competitiveness_score * 0.7 + min(facility_score, 40) * 0.3

        # ========== 市场定位分析 ==========
        if user_price < district_avg * 0.85:
            market_position = "低价策略"
            position_detail = f"定价低于商圈均价{round((1-user_price/district_avg)*100)}%，适合快速获客"
        elif user_price < district_avg * 1.15:
            market_position = "市场均价"
            position_detail = f"定价接近商圈均价({round(district_avg)}元)，竞争激烈"
        else:
            market_position = "高端定位"
            position_detail = f"定价高于商圈均价{round((user_price/district_avg-1)*100)}%，需突出特色"

        # ========== 优化建议 ==========
        suggestions = []

        # 价格建议
        # 模型「合理价」与「商圈均价」口径不同：可能出现定价已明显低于商圈均价，
        # 却仍高于模型估算合理价。此时不应再建议「继续降价」，避免与低价策略文案矛盾。
        discount_vs_district = (user_price / district_avg) if district_avg > 0 else 1.0
        already_low_vs_district_avg = discount_vs_district < 0.85  # 与上方「低价策略」阈值一致

        if price_ratio > 1.1:
            if already_low_vs_district_avg:
                suggestions.append(
                    "当前定价已明显低于商圈均价；模型估算合理价仅供参考。若转化仍不理想，建议优先完善设施、照片与描述，而非继续降价"
                )
            else:
                suggestions.append(f"建议降价至{round(predicted_price)}元左右以提升竞争力")
        elif price_ratio < 0.85:
            suggestions.append(f"当前定价偏低，可考虑提价至{round(predicted_price * 0.95)}元")

        # 设施建议
        if facility_score < 15:
            suggestions.append("设施配置较少，建议增加投影、浴缸等特色设施")
        if not request.get('near_metro') and not request.get('has_elevator'):
            suggestions.append("交通便利性一般，可在描述中突出其他优势")

        if not suggestions:
            suggestions.append("当前配置和定价较为合理，保持现状即可")

        return {
            "competitiveness_score": round(final_score, 1),
            "competitiveness_level": competitiveness_level,
            "pricing_analysis": {
                "user_price": round(user_price, 2),
                "fair_price": round(predicted_price, 2),
                "fair_price_model": fair_src,
                "price_ratio": round(price_ratio, 2),
                "price_difference": round(user_price - predicted_price, 2),
                "evaluation": price_comment,
                "district_avg_scope": "district_all_listings",
            },
            "market_position": {
                "position": market_position,
                "district_avg_price": round(district_avg, 2),
                "detail": position_detail,
                "district_avg_scope": "district_all_listings",
            },
            "facility_analysis": {
                "score": facility_score,
                "facilities": facilities,
                "count": len(facilities)
            },
            "suggestions": suggestions[:4]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in competitiveness assessment: {e}")
        raise HTTPException(status_code=500, detail=f"竞争力评估失败: {str(e)}")




# =============================================================================
# 获取行政区和商圈映射数据
# =============================================================================

@router.get("/district-trade-areas")
def get_district_trade_areas():
    """
    获取所有行政区和对应的商圈列表
    
    返回格式:
    {
        "districts": ["江汉区", "武昌区", ...],
        "trade_areas": {
            "江汉区": ["江汉路/中山公园", "武汉国际博览中心/王家湾", ...],
            "武昌区": ["光谷广场/武昌高校区", ...],
            ...
        }
    }
    """
    from sqlalchemy import text

    db = None
    try:
        db = SessionLocal()
        query = text("""
            SELECT DISTINCT district, trade_area 
            FROM listings 
            WHERE district IS NOT NULL AND district != ''
            ORDER BY district, trade_area
        """)
        result = db.execute(query).fetchall()

        districts = set()
        trade_areas_by_district = {}

        for row in result:
            district = row[0]
            trade_area = row[1]

            if district:
                districts.add(district)

                if district not in trade_areas_by_district:
                    trade_areas_by_district[district] = []

                if trade_area and trade_area not in trade_areas_by_district[district]:
                    trade_areas_by_district[district].append(trade_area)

        districts_list = sorted(list(districts))

        return {
            "districts": districts_list,
            "trade_areas": trade_areas_by_district
        }

    except Exception as e:
        logger.error(f"获取行政区商圈数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")
    finally:
        if db is not None:
            db.close()
