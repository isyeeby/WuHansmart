"""
XGBoost Price Prediction Model Service.
使用 ModelManager 统一管理模型
"""
import logging
from typing import Optional

import pandas as pd

from app.services.model_manager import model_manager
from app.models.schemas import PredictionRequest

logger = logging.getLogger(__name__)


class PricePredictionModel:
    """
    XGBoost-based price prediction service.
    委托给 ModelManager 统一管理
    """

    def __init__(self):
        # 使用全局 model_manager
        self.manager = model_manager

    def _load_model(self):
        """模型已由 ModelManager 加载，无需重复加载"""
        pass

    def _prepare_features(self, request: PredictionRequest) -> pd.DataFrame:
        """
        Convert prediction request to feature DataFrame.
        Performs one-hot encoding and feature engineering.
        """
        # Base features from request
        data = {
            'capacity': request.capacity,
            'bedrooms': request.bedrooms,
            'bathrooms': request.bathrooms,
            'has_wifi': 1 if request.has_wifi else 0,
            'has_kitchen': 1 if request.has_kitchen else 0,
            'has_air_conditioning': 1 if request.has_air_conditioning else 0,
            'has_projector': 1 if getattr(request, 'has_projector', False) else 0,
            'has_bathtub': 1 if getattr(request, 'has_bathtub', False) else 0,
            'has_washer': 1 if getattr(request, 'has_washer', False) else 0,
            'has_smart_lock': 1 if getattr(request, 'has_smart_lock', False) else 0,
            'has_tv': 1 if getattr(request, 'has_tv', False) else 0,
            'has_heater': 1 if getattr(request, 'has_heater', False) else 0,
            'is_weekend': 1 if request.is_weekend else 0,
            'is_holiday': 1 if request.is_holiday else 0,
            'distance_to_metro': getattr(request, 'distance_to_metro', 1.0) or 1.0,
        }

        # District one-hot encoding
        districts = ["江汉路", "光谷", "楚河汉街", "黄鹤楼", "武昌火车站", "汉口火车站", "昙华林"]
        for district in districts:
            data[f'dist_{district}'] = 1 if request.district == district else 0

        # Room type one-hot encoding
        room_types = ["整套房屋", "独立房间", "合住房间"]
        for room_type in room_types:
            data[f'room_{room_type}'] = 1 if request.room_type == room_type else 0

        # Feature engineering
        data['capacity_bedroom_ratio'] = data['capacity'] / (data['bedrooms'] + 1)
        data['has_luxury_amenities'] = data['has_projector'] + data['has_bathtub'] + data['has_smart_lock']

        # Create DataFrame
        df = pd.DataFrame([data])

        # Ensure all expected features are present
        feature_names = getattr(self, 'feature_names', None)
        if feature_names:
            for feature in feature_names:
                if feature not in df.columns:
                    df[feature] = 0
            df = df[feature_names]

        return df

    def predict(self, request: PredictionRequest) -> float:
        """
        Predict price using XGBoost model via ModelManager.
        """
        try:
            # 使用 ModelManager 进行预测 - 传递完整的特征
            rating_raw = getattr(request, "rating", None)
            favorite_raw = getattr(request, "favorite_count", None)
            features = {
                # 位置特征
                'district': request.district,
                'trade_area': getattr(request, 'trade_area', None) or request.district,
                # 数值特征（None 表示未提供，由 ModelManager 结合 has_* 与 cold_start 处理）
                'rating': float(rating_raw) if rating_raw is not None else None,
                'has_rating_ob': 0 if rating_raw is None else 1,
                'bedroom_count': request.bedrooms,
                'bed_count': getattr(request, 'bed_count', request.bedrooms) or request.bedrooms,
                'area': getattr(request, 'area', 50) or 50,
                'capacity': request.capacity,
                'favorite_count': int(favorite_raw) if favorite_raw is not None else None,
                'has_favorite_ob': 0 if favorite_raw is None else 1,
                'latitude': getattr(request, 'latitude', 30.5) or 30.5,
                'longitude': getattr(request, 'longitude', 114.3) or 114.3,
                # 房屋类型
                'house_type': getattr(request, 'room_type', '整套'),
                'has_heater': bool(getattr(request, 'has_heater', False)),
                # 设施特征 - 映射到模型特征名
                'near_subway': 1 if getattr(request, 'near_metro', False) else 0,
                'near_station': 1 if getattr(request, 'near_station', False) else 0,
                'near_university': 1 if getattr(request, 'near_university', False) else 0,
                'projector': 1 if getattr(request, 'has_projector', False) else 0,
                'washer': 1 if getattr(request, 'has_washer', False) else 0,
                'bathtub': 1 if getattr(request, 'has_bathtub', False) else 0,
                'smart_lock': 1 if getattr(request, 'has_smart_lock', False) else 0,
                'ac': 1 if getattr(request, 'has_air_conditioning', True) else 0,
                'kitchen': 1 if getattr(request, 'has_kitchen', False) else 0,
                'fridge': 1 if getattr(request, 'has_fridge', False) else 0,
                'terrace': 1 if getattr(request, 'has_terrace', False) else 0,
                'elevator': 1 if getattr(request, 'has_elevator', False) else 0,
                'mahjong': 1 if getattr(request, 'has_mahjong', False) else 0,
                'pet_friendly': 1 if getattr(request, 'pet_friendly', False) else 0,
                'has_view': 1 if getattr(request, 'has_view', False) else 0,
                'view_type': getattr(request, 'view_type', None),
                # 景观特征
                'river_view': 1 if (getattr(request, 'has_view', False) and '江景' in str(getattr(request, 'view_type', ''))) else 0,
                'lake_view': 1 if (getattr(request, 'has_view', False) and '湖景' in str(getattr(request, 'view_type', ''))) else 0,
                # 其他特征
                'near_ski': 1 if getattr(request, 'near_ski', False) else 0,
                'mountain_view': 1
                if (getattr(request, 'has_view', False) and '山景' in str(getattr(request, 'view_type', '')))
                else 0,
                'sunroom': 0,
                'garden': 1 if getattr(request, 'garden', False) else 0,
                'city_view': 0,
                'big_projector': 1 if getattr(request, 'has_projector', False) else 0,  # 有投影则可能有巨幕投影
                'view_bathtub': 0,
                'karaoke': 0,
                'oven': 0,
                'dry_wet_sep': 0,
                'smart_toilet': 0,
                'free_parking': 1 if getattr(request, 'has_parking', False) else 0,
                'paid_parking': 0,
                'free_water': 0,
                'front_desk': 0,
                'butler': 0,
                'luggage': 0,
                'style_modern': 0,
                'style_ins': 0,
                'style_western': 0,
                'style_chinese': 0,
                'style_japanese': 0,
                'real_photo': 0,
                'instant_confirm': 0,
                'family_friendly': 0,
                'business': 0,
            }

            # 定价推理不查 price_calendars：日历维由 ModelManager 用 calendar_feature_defaults.json 填充，
            # 与训练主评估口径一致，避免依赖 unit_id 拉库「作弊」。
            prediction = self.manager.predict_price(features)
            if prediction is not None:
                return prediction

            # 如果模型预测失败，使用启发式预测
            return self._dummy_predict(request)

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._dummy_predict(request)

    def _dummy_predict(self, request: PredictionRequest) -> float:
        """
        Heuristic-based fallback prediction.
        Used when XGBoost model is not available.
        """
        base_price = 150.0

        # District multiplier
        district_multipliers = {
            "江汉路": 1.5,
            "光谷": 1.2,
            "楚河汉街": 1.6,
            "武昌火车站": 1.0,
            "汉口火车站": 1.1,
            "黄鹤楼": 1.4,
            "昙华林": 1.3
        }
        multiplier = district_multipliers.get(request.district, 1.0)

        # Room type multiplier
        room_multipliers = {
            "整套房屋": 1.5,
            "独立房间": 1.0,
            "合住房间": 0.6
        }
        r_multiplier = room_multipliers.get(request.room_type, 1.0)

        # Calculate price
        price = base_price * multiplier * r_multiplier
        price += (request.capacity - 1) * 30
        price += request.bedrooms * 50
        price += request.bathrooms * 30

        if request.has_wifi:
            price += 10
        if request.has_kitchen:
            price += 20
        if request.is_weekend:
            price *= 1.2
        if request.is_holiday:
            price *= 1.5

        return round(price, 2)

    def _encode_district(self, district: str) -> int:
        """
        将区名编码为数字
        与模型训练时的编码一致（使用pandas Categorical.codes，按出现顺序）
        """
        district_map = {
            "东西湖区": 0,
            "武昌区": 1,
            "汉阳区": 2,
            "江夏区": 3,
            "江岸区": 4,
            "江汉区": 5,
            "洪山区": 6,
            "硚口区": 7,
            "蔡甸区": 8,
            "青山区": 9,
            "黄陂区": 10,
        }
        return district_map.get(district, 0)

    def get_feature_importance(self) -> Optional[dict]:
        """
        Get feature importance from the model.
        委托给 ModelManager 获取
        """
        try:
            # 从 manager 获取特征重要性
            importance = self.manager.get_feature_importance()
            if importance:
                return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
            return None
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return None


# Singleton instance
model_service = PricePredictionModel()
