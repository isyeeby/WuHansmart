"""
模型管理器 - 统一管理模型加载、版本控制和训练任务
"""
import os
import json
import joblib
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
import xgboost as xgb
import pandas as pd

from app.ml.calendar_features import CALENDAR_FEATURE_NAMES
from app.ml.price_feature_config import compute_is_budget_structural, ordered_facility_columns

logger = logging.getLogger(__name__)


class ModelManager:
    """
    模型管理器
    
    职责:
    1. 自动加载最新模型
    2. 模型版本管理
    3. 提供训练任务接口
    4. 热更新支持
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)

        # 当前加载的模型
        self.price_model: Optional[Any] = None
        self.similarity_matrix: Optional[Any] = None
        self.id_map: Optional[Dict] = None

        # 位置编码器
        self.district_encoder: Optional[Dict] = None
        self.trade_area_encoder: Optional[Dict] = None
        self.house_type_encoder: Optional[Dict] = None

        # 行政区统计信息 (目标编码)
        self.district_stats: Optional[Dict] = None

        # 模型元数据
        self.price_model_meta: Optional[Dict] = None
        self.recommender_meta: Optional[Dict] = None
        # 无 unit_id / 无日历时，与训练集一致的默认日历特征（cal_n_days=0）
        self.calendar_defaults: Dict[str, float] = {}

        # 自动加载模型
        self._load_models()
    
    def _load_models(self):
        """自动加载最新模型"""
        self._load_price_model()
        self._load_recommender_model()
    
    def reload_models(self):
        """重新加载所有模型"""
        logger.info("Reloading models...")
        self._load_models()
        logger.info("Models reloaded successfully")
    
    def _load_price_model(self):
        """加载价格预测模型"""
        try:
            # 优先加载 latest 模型
            latest_model_path = self.models_dir / "xgboost_price_model_latest.pkl"
            if latest_model_path.exists():
                self.price_model = joblib.load(latest_model_path)
                logger.info(f"Price model loaded: {latest_model_path.name}")
            else:
                # 如果没有 latest，查找最新的模型文件
                model_files = list(self.models_dir.glob("xgboost_price_model_*.pkl"))
                if not model_files:
                    logger.warning("No price model found")
                    return

                # 按修改时间排序，取最新的
                latest_model = max(model_files, key=lambda p: p.stat().st_mtime)

                # 加载模型
                self.price_model = joblib.load(latest_model)
                logger.info(f"Price model loaded: {latest_model.name}")

            # 加载商圈编码器
            encoder_path = self.models_dir / "district_encoder_latest.pkl"
            if encoder_path.exists():
                self.district_encoder = joblib.load(encoder_path)
                logger.info(f"District encoder loaded: {encoder_path.name}")
            else:
                # 尝试从metrics文件中加载
                metrics_files = list(self.models_dir.glob("model_metrics_*.json"))
                if metrics_files:
                    latest_metrics = max(metrics_files, key=lambda p: p.stat().st_mtime)
                    with open(latest_metrics, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)
                        if 'district_encoder' in metrics:
                            self.district_encoder = metrics['district_encoder']
                            logger.info(f"District encoder loaded from metrics: {latest_metrics.name}")

            # 加载 trade_area 编码器
            self.trade_area_encoder = None
            trade_area_encoder_path = self.models_dir / "trade_area_encoder_latest.pkl"
            if trade_area_encoder_path.exists():
                self.trade_area_encoder = joblib.load(trade_area_encoder_path)
                logger.info(f"Trade area encoder loaded: {trade_area_encoder_path.name}")
            else:
                metrics_files = list(self.models_dir.glob("model_metrics_*.json"))
                if metrics_files:
                    latest_metrics = max(metrics_files, key=lambda p: p.stat().st_mtime)
                    with open(latest_metrics, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)
                        if 'trade_area_encoder' in metrics:
                            self.trade_area_encoder = metrics['trade_area_encoder']
                            logger.info(f"Trade area encoder loaded from metrics: {latest_metrics.name}")

            # 加载 house_type 编码器（与训练脚本 Label 映射一致）
            self.house_type_encoder = None
            house_type_encoder_path = self.models_dir / "house_type_encoder_latest.pkl"
            if house_type_encoder_path.exists():
                self.house_type_encoder = joblib.load(house_type_encoder_path)
                logger.info(f"House type encoder loaded: {house_type_encoder_path.name}")
            else:
                metrics_latest = self.models_dir / "model_metrics_latest.json"
                if metrics_latest.exists():
                    with open(metrics_latest, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)
                        if 'house_type_encoder' in metrics:
                            self.house_type_encoder = metrics['house_type_encoder']
                            logger.info("House type encoder loaded from model_metrics_latest.json")
                else:
                    metrics_files = list(self.models_dir.glob("model_metrics_*.json"))
                    if metrics_files:
                        latest_metrics = max(metrics_files, key=lambda p: p.stat().st_mtime)
                        with open(latest_metrics, 'r', encoding='utf-8') as f:
                            metrics = json.load(f)
                            if 'house_type_encoder' in metrics:
                                self.house_type_encoder = metrics['house_type_encoder']
                                logger.info(
                                    f"House type encoder loaded from metrics: {latest_metrics.name}"
                                )

            cal_def_path = self.models_dir / "calendar_feature_defaults.json"
            if cal_def_path.exists():
                with open(cal_def_path, "r", encoding="utf-8") as f:
                    self.calendar_defaults = {k: float(v) for k, v in json.load(f).items()}
                logger.info(f"Calendar feature defaults loaded: {cal_def_path.name}")
            else:
                self.calendar_defaults = {}

            # 加载行政区统计信息 (用于目标编码)
            district_stats_path = self.models_dir / "district_stats.json"
            if district_stats_path.exists():
                with open(district_stats_path, 'r', encoding='utf-8') as f:
                    stats_list = json.load(f)
                    # 转换为字典格式: {district: {dist_mean, dist_median, dist_std, dist_count}}
                    self.district_stats = {}
                    for item in stats_list:
                        self.district_stats[item['district']] = {
                            'dist_mean': item.get('dist_mean', 200),
                            'dist_median': item.get('dist_median', 165),
                            'dist_std': item.get('dist_std', 100),
                            'dist_count': item.get('dist_count', 10)
                        }
                    logger.info(f"District stats loaded: {len(self.district_stats)} districts")
            else:
                self.district_stats = {}
                logger.warning("District stats file not found")

            # 加载元数据
            meta_file = latest_model_path.with_suffix('.json')
            if meta_file.exists():
                with open(meta_file, 'r', encoding='utf-8') as f:
                    self.price_model_meta = json.load(f)

        except Exception as e:
            logger.error(f"Failed to load price model: {e}")
            self.price_model = None
            self.calendar_defaults = {}

    def _load_recommender_model(self):
        """加载推荐模型"""
        try:
            # 查找最新的相似度矩阵
            matrix_files = list(self.models_dir.glob("listing_similarity_*.npz"))
            if not matrix_files:
                logger.warning("No recommender model found")
                return
            
            latest_matrix = max(matrix_files, key=lambda p: p.stat().st_mtime)
            self.similarity_matrix = load_npz(str(latest_matrix))
            
            # 加载ID映射
            id_map_file = latest_matrix.name.replace('similarity', 'id_map').replace('.npz', '.json')
            id_map_path = self.models_dir / id_map_file
            if id_map_path.exists():
                with open(id_map_path, 'r', encoding='utf-8') as f:
                    raw_map = json.load(f)
                    # 新的格式：包含 id_to_index 和 index_to_id
                    if 'id_to_index' in raw_map:
                        self.id_map = {k: int(v) for k, v in raw_map['id_to_index'].items()}
                        self.index_to_id = {int(k): v for k, v in raw_map['index_to_id'].items()}
                    else:
                        # 旧格式：直接是 id -> index 映射
                        self.id_map = {}
                        for k, v in raw_map.items():
                            if k in ('created_at', 'total_listings', 'data_source'):
                                continue
                            if isinstance(v, int):
                                self.id_map[k] = v
                            elif isinstance(v, str) and v.isdigit():
                                self.id_map[k] = int(v)
                        self.index_to_id = {v: k for k, v in self.id_map.items()}
            else:
                self.id_map = None
                self.index_to_id = {}
            
            # 加载元数据
            meta_file = latest_matrix.with_suffix('.json')
            if meta_file.exists():
                with open(meta_file, 'r', encoding='utf-8') as f:
                    self.recommender_meta = json.load(f)
            
            logger.info(f"Recommender model loaded: {latest_matrix.name}")
            
        except Exception as e:
            logger.error(f"Failed to load recommender model: {e}")
            self.similarity_matrix = None
            self.id_map = None
    
    def get_price_model(self) -> Optional[Any]:
        """获取价格预测模型"""
        return self.price_model
    
    def get_recommender_model(self) -> tuple:
        """获取推荐模型 (similarity_matrix, id_map)"""
        return self.similarity_matrix, self.id_map
    
    def get_similar_listings(self, unit_id: str, top_k: int = 5) -> list:
        """
        获取相似房源
        
        Args:
            unit_id: 房源ID
            top_k: 返回数量
        
        Returns:
            相似房源列表
        """
        if self.similarity_matrix is None or self.id_map is None:
            return []
        
        try:
            if unit_id not in self.id_map:
                logger.warning(f"Unit {unit_id} not found in model")
                return []
            
            idx = self.id_map[unit_id]
            
            # 获取相似度分数
            similarities = self.similarity_matrix[idx].toarray().flatten()
            
            # 获取 top-k 相似房源（排除自己）
            similar_indices = similarities.argsort()[::-1][1:top_k+1]
            
            results = []
            for sim_idx in similar_indices:
                if sim_idx in self.index_to_id:
                    similar_id = self.index_to_id[sim_idx]
                    similarity_score = float(similarities[sim_idx])
                    results.append({
                        "unit_id": similar_id,
                        "similarity": round(similarity_score, 4)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting similar listings: {e}")
            return []
    
    def predict_price(self, features: Dict) -> Optional[float]:
        """
        使用价格模型进行预测

        Args:
            features: 特征字典

        Returns:
            预测价格或 None
        """
        if self.price_model is None:
            return None

        try:
            # 加载特征名称
            feature_names_path = self.models_dir / "feature_names_latest.json"
            if feature_names_path.exists():
                with open(feature_names_path, 'r') as f:
                    feature_names = json.load(f)
            else:
                logger.warning("Feature names file not found")
                return None

            # 获取基础特征
            district = features.get('district', '')
            trade_area = features.get('trade_area', '') or district
            area = features.get('area', 50)
            bedroom_count = features.get('bedroom_count', 1)
            bed_count = features.get('bed_count', bedroom_count)
            capacity = features.get('capacity', bedroom_count * 2)
            rating = features.get('rating', 4.85)
            favorite_count = features.get('favorite_count', 100)

            # 行政区编码和目标编码
            if self.district_encoder and district in self.district_encoder:
                district_encoded = self.district_encoder[district]
            else:
                district_encoded = 0

            if self.trade_area_encoder:
                trade_area_encoded = int(self.trade_area_encoder.get(trade_area, 0))
            else:
                trade_area_encoded = district_encoded

            # 行政区统计 (目标编码)
            if self.district_stats and district in self.district_stats:
                stats = self.district_stats[district]
                dist_mean = stats['dist_mean']
                dist_median = stats['dist_median']
                dist_std = stats['dist_std']
                dist_count = stats['dist_count']
            else:
                # 默认值
                dist_mean = 200
                dist_median = 165
                dist_std = 100
                dist_count = 10

            # 房屋类型编码（优先使用训练导出的映射表，保证与 XGBoost 特征一致）
            house_type = str(features.get('house_type', '整套') or '整套')
            if self.house_type_encoder:
                house_type_encoded = int(self.house_type_encoder.get(house_type, 0))
            else:
                house_type_map = {'整套': 0, '单间': 1, '复式': 2, '别墅': 3, '公寓': 0, '整套房屋': 0}
                house_type_encoded = int(house_type_map.get(house_type, 0))

            # 设施特征映射 (前端参数名 -> 模型特征名)
            facility_mapping = {
                'near_subway': features.get('near_metro', 0) or features.get('near_subway', 0),
                'near_station': features.get('near_station', 0),
                'near_university': features.get('near_university', 0),
                'near_ski': features.get('near_ski', 0),
                'river_view': 1 if features.get('has_view') and '江景' in str(features.get('view_type', '')) else features.get('river_view', 0),
                'lake_view': 1 if features.get('has_view') and '湖景' in str(features.get('view_type', '')) else features.get('lake_view', 0),
                'mountain_view': features.get('mountain_view', 0),
                'terrace': features.get('has_terrace', 0) or features.get('terrace', 0),
                'sunroom': features.get('sunroom', 0),
                'garden': features.get('garden', 0),
                'city_view': features.get('city_view', 0),
                'projector': features.get('has_projector', 0) or features.get('projector', 0),
                'big_projector': features.get('big_projector', 0),
                'washer': features.get('has_washer', 0) or features.get('washer', 0),
                'bathtub': features.get('has_bathtub', 0) or features.get('bathtub', 0),
                'view_bathtub': features.get('view_bathtub', 0),
                'karaoke': features.get('karaoke', 0),
                'mahjong': features.get('has_mahjong', 0) or features.get('mahjong', 0),
                'kitchen': features.get('has_kitchen', 0) or features.get('kitchen', 0),
                'fridge': features.get('has_fridge', 0) or features.get('fridge', 0),
                'oven': features.get('oven', 0),
                'dry_wet_sep': features.get('dry_wet_sep', 0),
                'smart_lock': features.get('has_smart_lock', 0) or features.get('smart_lock', 0),
                'smart_toilet': features.get('smart_toilet', 0),
                'ac': features.get('has_air_conditioning', 1) or features.get('ac', 1),
                'hot_water': features.get('hot_water', 1),
                'elevator': features.get('has_elevator', 0) or features.get('elevator', 0),
                'pet_friendly': features.get('pet_friendly', 0),
                'free_parking': features.get('has_parking', 0) or features.get('free_parking', 0),
                'paid_parking': features.get('paid_parking', 0),
                'free_water': features.get('free_water', 0),
                'front_desk': features.get('front_desk', 0),
                'butler': features.get('butler', 0),
                'luggage': features.get('luggage', 0),
                'style_modern': features.get('style_modern', 0),
                'style_ins': features.get('style_ins', 0),
                'style_western': features.get('style_western', 0),
                'style_chinese': features.get('style_chinese', 0),
                'style_japanese': features.get('style_japanese', 0),
                'real_photo': features.get('real_photo', 0),
                'instant_confirm': features.get('instant_confirm', 0),
                'family_friendly': features.get('family_friendly', 0),
                'business': features.get('business', 0),
            }

            # 派生特征（与 scripts/train_model_mysql.py 及 price_feature_config 一致）
            is_large = 1 if (bedroom_count >= 4 or area >= 150) else 0
            is_budget = compute_is_budget_structural(area, bedroom_count)
            area_per_bedroom = area / (bedroom_count + 1)
            heat_score = favorite_count * rating / 10

            # 设施数量：对 FACILITY_KEYWORDS 映射列求和，与训练时 facility_count 定义一致
            _fac_cols = ordered_facility_columns()
            facility_count = sum(int(facility_mapping.get(c, 0) or 0) for c in _fac_cols)

            # 经纬度 (如果没有则使用默认值)
            latitude = features.get('latitude', 30.5)
            longitude = features.get('longitude', 114.3)

            # 构建完整特征字典
            full_features = {
                'rating': rating,
                'area': area,
                'bedroom_count': bedroom_count,
                'bed_count': bed_count,
                'capacity': capacity,
                'favorite_count': favorite_count,
                'latitude': latitude,
                'longitude': longitude,
                'is_large': is_large,
                'is_budget': is_budget,
                'district_encoded': district_encoded,
                'trade_area_encoded': trade_area_encoded,
                'dist_mean': dist_mean,
                'dist_median': dist_median,
                'dist_std': dist_std,
                'dist_count': dist_count,
                'house_type_encoded': house_type_encoded,
                'area_per_bedroom': area_per_bedroom,
                'heat_score': heat_score,
                'facility_count': facility_count,
            }
            # 添加设施特征
            full_features.update(facility_mapping)

            for cal_name in CALENDAR_FEATURE_NAMES:
                if cal_name not in feature_names:
                    continue
                raw = features.get(cal_name)
                if raw is None and self.calendar_defaults:
                    raw = self.calendar_defaults.get(cal_name)
                if raw is None:
                    raw = 0.0
                full_features[cal_name] = float(raw)

            # 按照特征名称顺序构建DataFrame
            df = pd.DataFrame([[float(full_features.get(name, 0)) for name in feature_names]],
                            columns=feature_names)

            # 确保所有列为数值类型
            df = df.fillna(0).replace([np.inf, -np.inf], 0)

            # 预测 (模型使用了对数变换)
            pred_log = self.price_model.predict(df)[0]
            logger.info(f"Model prediction - pred_log: {pred_log}")
            # 反变换: exp(x) - 1
            prediction = np.expm1(pred_log)
            logger.info(f"After expm1 - prediction: {prediction}")

            return round(float(max(prediction, 50)), 2)  # 最低价格50元

        except Exception as e:
            logger.error(f"Price prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        获取特征重要性
        从 XGBoost 模型中提取特征重要性分数
        """
        if self.price_model is None:
            logger.warning("Price model not loaded")
            return None
        
        try:
            # 使用 feature_importances_ 属性（兼容新版 XGBoost）
            if hasattr(self.price_model, 'feature_importances_'):
                importance_dict = {}
                # 获取特征名称
                feature_names = self.price_model.get_booster().feature_names
                if feature_names:
                    for name, score in zip(feature_names, self.price_model.feature_importances_):
                        importance_dict[name] = float(score)
                    return importance_dict
            return None
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return None
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            "price_model": {
                "loaded": self.price_model is not None,
                "meta": self.price_model_meta
            },
            "recommender_model": {
                "loaded": self.similarity_matrix is not None,
                "meta": self.recommender_meta
            }
        }
    
# 全局模型管理器实例
model_manager = ModelManager()
