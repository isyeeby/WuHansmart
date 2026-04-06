"""
模型管理器：加载房源内容相似度矩阵（推荐）。
民宿定价由日级 XGBoost 独立服务加载，见 app.services.daily_price_service。
"""
import json
import logging
from typing import Any, Dict, Optional

from pathlib import Path

import numpy as np
from scipy.sparse import load_npz

logger = logging.getLogger(__name__)


class ModelManager:
    """
    职责:
    1. 加载 listing_similarity_*.npz 与 ID 映射
    2. 热重载支持
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.similarity_matrix: Optional[Any] = None
        self.id_map: Optional[Dict[str, int]] = None
        self.index_to_id: Dict[int, Any] = {}
        self.recommender_meta: Optional[Dict] = None

        self._load_models()

    def _load_models(self) -> None:
        self._load_recommender_model()

    def reload_models(self) -> None:
        logger.info("Reloading models...")
        self._load_models()
        logger.info("Models reloaded successfully")

    def _load_recommender_model(self) -> None:
        try:
            matrix_files = list(self.models_dir.glob("listing_similarity_*.npz"))
            if not matrix_files:
                logger.warning("No recommender model found")
                return

            latest_matrix = max(matrix_files, key=lambda p: p.stat().st_mtime)
            self.similarity_matrix = load_npz(str(latest_matrix))

            id_map_file = latest_matrix.name.replace("similarity", "id_map").replace(".npz", ".json")
            id_map_path = self.models_dir / id_map_file
            if id_map_path.exists():
                with open(id_map_path, "r", encoding="utf-8") as f:
                    raw_map = json.load(f)
                    if "id_to_index" in raw_map:
                        self.id_map = {k: int(v) for k, v in raw_map["id_to_index"].items()}
                        self.index_to_id = {int(k): v for k, v in raw_map["index_to_id"].items()}
                    else:
                        self.id_map = {}
                        for k, v in raw_map.items():
                            if k in ("created_at", "total_listings", "data_source"):
                                continue
                            if isinstance(v, int):
                                self.id_map[k] = v
                            elif isinstance(v, str) and v.isdigit():
                                self.id_map[k] = int(v)
                        self.index_to_id = {v: k for k, v in self.id_map.items()}
            else:
                self.id_map = None
                self.index_to_id = {}

            meta_file = latest_matrix.with_suffix(".json")
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    self.recommender_meta = json.load(f)

            logger.info("Recommender model loaded: %s", latest_matrix.name)

        except Exception as e:
            logger.error("Failed to load recommender model: %s", e)
            self.similarity_matrix = None
            self.id_map = None
            self.index_to_id = {}

    def get_recommender_model(self) -> tuple:
        return self.similarity_matrix, self.id_map

    def get_similar_listings(self, unit_id: str, top_k: int = 5) -> list:
        if self.similarity_matrix is None or self.id_map is None:
            return []

        try:
            if unit_id not in self.id_map:
                logger.warning("Unit %s not found in model", unit_id)
                return []

            idx = self.id_map[unit_id]
            similarities = self.similarity_matrix[idx].toarray().flatten()
            similar_indices = similarities.argsort()[::-1][1 : top_k + 1]

            results = []
            for sim_idx in similar_indices:
                if sim_idx in self.index_to_id:
                    similar_id = self.index_to_id[sim_idx]
                    similarity_score = float(similarities[sim_idx])
                    results.append(
                        {"unit_id": similar_id, "similarity": round(similarity_score, 4)}
                    )

            return results

        except Exception as e:
            logger.error("Error getting similar listings: %s", e)
            return []

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "recommender_model": {
                "loaded": self.similarity_matrix is not None,
                "meta": self.recommender_meta,
            }
        }


model_manager = ModelManager()
