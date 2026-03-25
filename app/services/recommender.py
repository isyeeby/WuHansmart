"""
Hybrid Collaborative Filtering Recommendation Service.

通过 ModelManager 加载预训练的混合相似度矩阵，
结合用户收藏/浏览历史进行个性化推荐。
"""
import json
import logging
import math
from typing import Any, List, Optional

import numpy as np

from app.ml.listing_scene_weak_labels import MEDICAL_HOSPITAL_PROXIMITY_KM
from app.models.schemas import HomestayRecommendation, RecommendationResponse
from app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

# 条件推荐中「医疗陪护」时，按 nearest_hospital_km 追加加分（与弱标签 2km 阈值对齐，5km 外为 0）
_MEDICAL_DISTANCE_BONUS_MAX = 0.018
_MEDICAL_DISTANCE_BONUS_FAR_KM = 5.0


class RecommendationService:
    """
    混合协同过滤推荐引擎。

    推荐优先级:
    1. 有登录用户 & 有行为数据 → 基于相似度矩阵的协同过滤推荐
    2. 无用户 / 无行为数据 → 基于评分的热门推荐 (fallback)
    """

    def __init__(self):
        self.manager = model_manager

    @staticmethod
    def _nearest_hospital_km_optional(listing: Any) -> Optional[float]:
        """ORM `nearest_hospital_km`，无效或缺失时 None。"""
        v = getattr(listing, "nearest_hospital_km", None)
        if v is None:
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(x) or x < 0:
            return None
        return round(x, 3)

    @staticmethod
    def _nearest_hospital_name_optional(listing: Any) -> Optional[str]:
        s = getattr(listing, "nearest_hospital_name", None)
        if s is None:
            return None
        t = str(s).strip()
        return t if t else None

    @staticmethod
    def _medical_hospital_distance_bonus(listing: Any, travel_purpose: Optional[str]) -> float:
        """仅 travel_purpose=medical 时，按库中直线距离加分（不在线算 POI）。"""
        if travel_purpose != "medical":
            return 0.0
        d = RecommendationService._nearest_hospital_km_optional(listing)
        if d is None:
            return 0.0
        near = float(MEDICAL_HOSPITAL_PROXIMITY_KM)
        mx = _MEDICAL_DISTANCE_BONUS_MAX
        if d <= near:
            return mx
        far = _MEDICAL_DISTANCE_BONUS_FAR_KM
        if d >= far:
            return 0.0
        return mx * (far - d) / (far - near)

    @staticmethod
    def _scene_purpose_bonus(listing: Any, travel_purpose: Optional[str]) -> float:
        """
        scene_scores 目的概率加分 +（医疗目的时）nearest_hospital_km 距离加分。
        均由 listing_scene_pipeline 离线回写；缺失则对应部分为 0。
        """
        bonus = 0.0
        if travel_purpose:
            scores = getattr(listing, "scene_scores", None)
            if isinstance(scores, dict):
                raw = scores.get(travel_purpose)
                if raw is not None:
                    try:
                        p = float(raw)
                        p = max(0.0, min(1.0, p))
                        bonus += 0.03 * p
                    except (TypeError, ValueError):
                        pass
        bonus += RecommendationService._medical_hospital_distance_bonus(
            listing, travel_purpose
        )
        return bonus

    # ==================================================================
    # 主推荐接口
    # ==================================================================

    def get_recommendations(
        self,
        user_id: Optional[str] = None,
        district: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        capacity: Optional[int] = None,
        top_k: int = 10,
    ) -> RecommendationResponse:
        """
        获取推荐列表。

        对登录用户：查询其收藏和浏览记录，利用预计算的相似度矩阵
        聚合用户偏好房源的相似房源，实现真正的协同过滤推荐。
        """
        try:
            if user_id:
                cf_result = self._cf_recommend_for_user(
                    user_id, district, price_min, price_max, top_k
                )
                if cf_result and cf_result.recommendations:
                    return cf_result

            return self._fallback_recommend(district, price_min, price_max, capacity, top_k)
        except Exception as e:
            logger.error(f"Recommendation error: {e}")
            return self._fallback_recommend(district, price_min, price_max, capacity, top_k)

    # ==================================================================
    # 基于条件的智能推荐 (用户选择条件 → 匹配 + 相似度扩展)
    # ==================================================================

    # 前端 key → 房源标签关键词
    FACILITY_MAP = {
        'subway':    ['近地铁', '地铁'],
        'projector': ['投影', '巨幕', '家庭影院'],
        'bathtub':   ['浴缸', '泡澡'],
        'cooking':   ['厨房', '做饭', '可做饭'],
        'wifi':      ['WiFi', 'wifi'],
        'washer':    ['洗衣机'],
        'parking':   ['停车', '车位'],
        'mahjong':   ['麻将', '棋牌'],
        'balcony':   ['阳台', '露台', '落地窗'],
        'smart_lock': ['智能锁', '密码锁'],
        'pet':       ['宠物', '携宠', '可带宠物', '宠物友好', '狗', '猫'],
    }

    # 出行目的 → 偏好设施 (前端 key)
    PURPOSE_FACILITY_PREFS = {
        'couple':   ['projector', 'bathtub', 'balcony'],
        'family':   ['cooking', 'washer', 'wifi'],
        'business': ['wifi', 'subway', 'smart_lock'],
        'exam':     ['wifi', 'subway'],
        'team_party': ['mahjong', 'cooking', 'projector', 'wifi'],
        'medical':  ['wifi', 'subway', 'washer'],
        'pet_friendly': ['pet', 'balcony', 'wifi'],
        'long_stay': ['washer', 'cooking', 'wifi'],
    }

    # 出行目的 → 价格倾向 (倍率，< 1 偏好便宜)
    PURPOSE_PRICE_BIAS = {
        'couple': 1.0,
        'family': 1.0,
        'business': 1.2,
        'exam': 0.6,
        'team_party': 0.95,
        'medical': 0.85,
        'pet_friendly': 1.0,
        'long_stay': 0.65,
    }

    # 问卷 required_facilities 中文 → FACILITY_MAP 键
    USER_FACILITY_CN_TO_KEY = {
        "投影": "projector",
        "厨房": "cooking",
        "洗衣机": "washer",
        "停车位": "parking",
        "WiFi": "wifi",
        "wifi": "wifi",
        "空调": "wifi",
    }

    @classmethod
    def map_user_facilities_to_api_keys(cls, items: Optional[List[str]]) -> List[str]:
        """将问卷必带设施中文映射为推荐服务设施键，去重保序。"""
        out: List[str] = []
        for x in items or []:
            if not isinstance(x, str):
                continue
            k = cls.USER_FACILITY_CN_TO_KEY.get(x.strip())
            if k and k not in out:
                out.append(k)
        return out

    def get_condition_based_recommendations(
        self,
        travel_purpose: Optional[str] = None,
        facilities: Optional[List[str]] = None,
        district: Optional[str] = None,
        trade_area: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        bedroom_count: Optional[int] = None,
        capacity: Optional[int] = None,
        top_k: int = 10,
    ) -> RecommendationResponse:
        """
        基于用户选择条件的智能推荐。

        流程:
        1. 按价格、商圈等硬条件从 DB 筛选候选房源
        2. 对每个候选计算条件匹配度:
           - 设施匹配分 (40%): 用户要求的设施命中了多少
           - 目的匹配分 (25%): 适合出行目的的设施命中了多少
           - 质量分 (20%):    评分和收藏综合
           - 价格适配分 (15%): 价格在用户区间内的居中程度
        3. 取匹配度最高的作为"种子"，用相似度矩阵扩展推荐池
        4. 合并去重、按综合分排序返回 Top-K
        """
        from app.db.database import SessionLocal, Listing
        from sqlalchemy import desc
        from app.core.recommend_travel import travel_purpose_for_condition_recommend

        travel_purpose = travel_purpose_for_condition_recommend(travel_purpose)

        # 合并出行目的隐含的设施偏好
        all_facilities = list(facilities or [])
        purpose_facs = self.PURPOSE_FACILITY_PREFS.get(travel_purpose or "", [])
        for f in purpose_facs:
            if f not in all_facilities:
                all_facilities.append(f)

        # 构建设施关键词集合 (用于匹配标签文本)
        required_keywords = {}
        for fkey in all_facilities:
            kws = self.FACILITY_MAP.get(fkey, [fkey])
            required_keywords[fkey] = kws

        user_required = set(facilities or [])
        purpose_implied = set(purpose_facs) - user_required

        db = SessionLocal()
        try:
            query = db.query(Listing).filter(Listing.final_price.isnot(None))
            if district:
                query = query.filter(Listing.district == district)
            if trade_area:
                query = query.filter(Listing.trade_area == trade_area)
            if price_min is not None:
                query = query.filter(Listing.final_price >= price_min)
            if price_max is not None:
                query = query.filter(Listing.final_price <= price_max)
            if bedroom_count is not None:
                query = query.filter(Listing.bedroom_count >= bedroom_count)
            if capacity is not None:
                query = query.filter(Listing.capacity.isnot(None))
                query = query.filter(Listing.capacity >= capacity)

            candidates = query.order_by(desc(Listing.rating)).limit(500).all()

            if not candidates:
                return RecommendationResponse(recommendations=[])

            price_mid = None
            if price_min is not None and price_max is not None:
                bias = self.PURPOSE_PRICE_BIAS.get(travel_purpose, 1.0)
                price_mid = (price_min + price_max) / 2 * bias

            scored_items = []
            for listing in candidates:
                tags_text = ' '.join(self._parse_facilities(listing.house_tags))

                # --- 设施匹配分 (用户明确要求的) ---
                if user_required:
                    hit = sum(1 for fk in user_required
                              if any(kw in tags_text for kw in self.FACILITY_MAP.get(fk, [fk])))
                    facility_score = hit / len(user_required)
                else:
                    facility_score = 0.5

                # --- 目的匹配分 (出行目的隐含的) ---
                if purpose_implied:
                    hit = sum(1 for fk in purpose_implied
                              if any(kw in tags_text for kw in self.FACILITY_MAP.get(fk, [fk])))
                    purpose_score = hit / len(purpose_implied)
                else:
                    purpose_score = 0.5

                # --- 质量分 ---
                rating_val = float(listing.rating or 4.0) / 5.0
                fav_val = min(math.log(float(listing.favorite_count or 0) + 1) / 7, 1.0)
                quality_score = rating_val * 0.7 + fav_val * 0.3

                # --- 价格适配分 (越居中越好) ---
                if price_mid and listing.final_price:
                    price_val = float(listing.final_price)
                    price_range = (price_max or price_val) - (price_min or 0)
                    if price_range > 0:
                        price_fit = 1 - abs(price_val - price_mid) / price_range
                        price_fit = max(0, min(1, price_fit))
                    else:
                        price_fit = 1.0
                else:
                    price_fit = 0.5

                total = (
                    facility_score * 0.40
                    + purpose_score * 0.25
                    + quality_score * 0.20
                    + price_fit * 0.15
                    + self._scene_purpose_bonus(listing, travel_purpose)
                )

                scored_items.append((listing, total, facility_score))

            scored_items.sort(key=lambda x: x[1], reverse=True)

            # --- 用相似度矩阵扩展 ---
            sim_matrix, id_map = self.manager.get_recommender_model()
            expanded = {}
            for listing, score, _ in scored_items[:top_k]:
                expanded[str(listing.unit_id)] = (listing, score)

            if sim_matrix is not None and id_map is not None:
                seeds = scored_items[:3]
                index_to_id = {v: k for k, v in id_map.items()}
                for listing, seed_score, _ in seeds:
                    uid_str = str(listing.unit_id)
                    if uid_str not in id_map:
                        continue
                    idx = id_map[uid_str]
                    row = sim_matrix[idx]
                    if hasattr(row, 'toarray'):
                        row = row.toarray().flatten()
                    else:
                        row = np.asarray(row).flatten()
                    top_sim_idx = np.argsort(row)[::-1][1:8]
                    for si in top_sim_idx:
                        sim_id = index_to_id.get(si) or index_to_id.get(int(si))
                        if sim_id and sim_id not in expanded:
                            derived_score = seed_score * float(row[si]) * 0.85
                            sim_listing = db.query(Listing).filter(
                                Listing.unit_id == sim_id).first()
                            if sim_listing:
                                derived_score += self._scene_purpose_bonus(
                                    sim_listing, travel_purpose
                                )
                            if sim_listing and self._passes_filter(
                                sim_listing,
                                price_min,
                                price_max,
                                district,
                                trade_area=trade_area,
                                bedroom_count=bedroom_count,
                                capacity=capacity,
                            ):
                                expanded[sim_id] = (sim_listing, derived_score)

            final = sorted(expanded.values(), key=lambda x: x[1], reverse=True)[:top_k]

            purpose_labels = {
                'couple': '情侣出游',
                'family': '家庭亲子',
                'business': '商务差旅',
                'exam': '学生考研',
                'team_party': '团建聚会',
                'medical': '医疗陪护',
                'pet_friendly': '宠物友好',
                'long_stay': '长租',
            }
            purpose_label = purpose_labels.get(travel_purpose, '')

            recommendations = []
            for listing, score in final:
                fac_list = self._parse_facilities(listing.house_tags)
                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                reason = self._build_reason(
                    score,
                    fac_list,
                    user_required,
                    purpose_label,
                    str(listing.unit_id)
                    not in {str(s[0].unit_id) for s in scored_items[:top_k]},
                    nearest_hospital_km=nh,
                    nearest_hospital_name=hn,
                )
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '优质民宿',
                        district=listing.district or '未知商圈',
                        price=float(listing.final_price or 300),
                        rating=float(listing.rating or 4.5),
                        cover_image=listing.cover_image,
                        facilities=fac_list,
                        match_score=round(min(score, 1.0), 2),
                        reason=reason,
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )

            return RecommendationResponse(recommendations=recommendations)
        except Exception as e:
            logger.error(f"Condition-based recommendation error: {e}")
            return self._fallback_recommend(
                district, price_min, price_max, capacity, top_k
            )
        finally:
            db.close()

    @staticmethod
    def _passes_filter(
        listing,
        price_min,
        price_max,
        district,
        trade_area=None,
        bedroom_count=None,
        capacity=None,
    ) -> bool:
        if district and listing.district != district:
            return False
        if trade_area and (listing.trade_area or "") != trade_area:
            return False
        if bedroom_count is not None:
            bc = listing.bedroom_count
            if bc is None or bc < bedroom_count:
                return False
        if capacity is not None:
            cap = listing.capacity
            if cap is None or cap < capacity:
                return False
        p = float(listing.final_price or 0)
        if price_min is not None and p < price_min:
            return False
        if price_max is not None and p > price_max:
            return False
        return True

    @staticmethod
    def _build_reason(
        score,
        fac_list,
        user_required,
        purpose_label,
        is_sim_expanded,
        nearest_hospital_km: Optional[float] = None,
        nearest_hospital_name: Optional[str] = None,
    ):
        parts = []
        if purpose_label:
            parts.append(f"适合{purpose_label}")
        if purpose_label == "医疗陪护" and nearest_hospital_km is not None:
            if nearest_hospital_name:
                disp = nearest_hospital_name.strip()
                if len(disp) > 26:
                    disp = disp[:25] + "…"
                parts.append(f"距「{disp}」约{nearest_hospital_km:.1f}km")
            else:
                parts.append(f"距最近医院约{nearest_hospital_km:.1f}km")
        if user_required:
            fac_text = ' '.join(fac_list)
            hit_names = {
                'subway': '近地铁', 'projector': '有投影', 'bathtub': '有浴缸',
                'cooking': '可做饭', 'wifi': 'WiFi', 'washer': '洗衣机',
                'parking': '停车', 'mahjong': '麻将', 'balcony': '阳台',
                'smart_lock': '智能锁', 'pet': '宠物友好',
            }
            matched = [hit_names.get(f, f) for f in user_required
                       if any(kw in fac_text for kw in
                              RecommendationService.FACILITY_MAP.get(f, [f]))]
            if matched:
                parts.append('、'.join(matched))
        if is_sim_expanded:
            parts.append("相似好房发现")
        if not parts:
            parts.append(f"匹配度 {score:.0%}")
        return ' | '.join(parts)

    # ==================================================================
    # 协同过滤推荐 (基于用户行为 + 相似度矩阵)
    # ==================================================================

    def _cf_recommend_for_user(
        self, user_id: str, district, price_min, price_max, top_k
    ) -> Optional[RecommendationResponse]:
        """
        基于用户历史行为的协同过滤推荐。

        流程:
        1. 查询用户的收藏和最近浏览，获取其交互过的 unit_id 列表
        2. 对每个交互房源，从预计算的相似度矩阵中取出其相似度向量
        3. 加权聚合 (收藏权重 > 浏览权重)，得到每个候选房源的综合分数
        4. 按分数降序排列，应用筛选条件后取 Top-K
        """
        sim_matrix, id_map = self.manager.get_recommender_model()
        if sim_matrix is None or id_map is None:
            return None

        interacted = self._get_user_interactions(user_id)
        if not interacted:
            return None

        n = sim_matrix.shape[0]
        scores = np.zeros(n)
        weight_sum = 0.0

        for unit_id, weight in interacted:
            uid_str = str(unit_id)
            if uid_str in id_map:
                idx = id_map[uid_str]
                row = sim_matrix[idx]
                if hasattr(row, 'toarray'):
                    row = row.toarray().flatten()
                else:
                    row = np.asarray(row).flatten()
                scores += row * weight
                weight_sum += weight

        if weight_sum == 0:
            return None
        scores /= weight_sum

        # 排除已交互的房源
        for unit_id, _ in interacted:
            uid_str = str(unit_id)
            if uid_str in id_map:
                scores[id_map[uid_str]] = -1

        index_to_id = {v: k for k, v in id_map.items()}
        top_indices = np.argsort(scores)[::-1][:top_k * 3]

        from app.db.database import SessionLocal, Listing

        db = SessionLocal()
        recommendations = []
        try:
            for idx in top_indices:
                if scores[idx] <= 0:
                    break
                uid = index_to_id.get(idx) or index_to_id.get(int(idx))
                if not uid:
                    continue

                listing = db.query(Listing).filter(Listing.unit_id == str(uid)).first()
                if not listing:
                    continue

                if district and listing.district != district:
                    continue
                if price_min is not None and (listing.final_price or 0) < price_min:
                    continue
                if price_max is not None and (listing.final_price or 0) > price_max:
                    continue

                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '优质民宿',
                        district=listing.district or '未知商圈',
                        price=float(listing.final_price or 300),
                        rating=float(listing.rating or 4.5),
                        cover_image=listing.cover_image,
                        facilities=self._parse_facilities(listing.house_tags),
                        match_score=round(float(scores[idx]), 2),
                        reason="根据您的偏好智能推荐",
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )
                if len(recommendations) >= top_k:
                    break
        finally:
            db.close()

        if not recommendations:
            return None
        return RecommendationResponse(recommendations=recommendations)

    def _get_user_interactions(self, user_id: str) -> List[tuple]:
        """
        获取用户交互过的房源及其权重。

        Returns:
            [(unit_id, weight), ...] — 收藏 weight=3.0, 浏览 weight=1.0
        """
        from app.db.database import SessionLocal, Favorite, UserViewHistory

        db = SessionLocal()
        result = []
        try:
            uid = int(user_id)

            favs = db.query(Favorite.unit_id).filter(Favorite.user_id == uid).all()
            for (fav_id,) in favs:
                result.append((str(fav_id), 3.0))

            views = (
                db.query(UserViewHistory.unit_id)
                .filter(UserViewHistory.user_id == uid)
                .order_by(UserViewHistory.created_at.desc())
                .limit(20)
                .all()
            )
            seen = {r[0] for r in result}
            for (view_id,) in views:
                vid = str(view_id)
                if vid not in seen:
                    result.append((vid, 1.0))
                    seen.add(vid)
        except Exception as e:
            logger.warning(f"Failed to load user interactions: {e}")
        finally:
            db.close()

        return result

    # ==================================================================
    # 相似房源接口 (优先用预计算矩阵)
    # ==================================================================

    def get_similar_listings(self, unit_id: str, top_k: int = 5) -> List[dict]:
        """获取相似房源 (委托给 ModelManager)。"""
        return self.manager.get_similar_listings(unit_id, top_k)

    def get_similar_homestays(
        self, homestay_id: str, top_k: int = 5
    ) -> RecommendationResponse:
        """
        获取相似房源推荐。

        优先使用预计算的相似度矩阵（O(1) 查询），
        矩阵不可用或房源不在矩阵中时回退到 SQL 查询。
        """
        similar = self.manager.get_similar_listings(homestay_id, top_k=top_k)
        if similar:
            return self._build_similar_response(similar, homestay_id, top_k)

        return self._sql_similar_fallback(homestay_id, top_k)

    def _build_similar_response(
        self, similar_items: list, base_id: str, top_k: int
    ) -> RecommendationResponse:
        """从相似度矩阵结果构建响应，查询 MySQL 获取房源详情。"""
        from app.db.database import SessionLocal, Listing

        db = SessionLocal()
        recommendations = []
        try:
            for item in similar_items[:top_k]:
                uid = str(item.get('unit_id', ''))
                sim_score = item.get('similarity', 0)
                listing = db.query(Listing).filter(Listing.unit_id == uid).first()
                if not listing:
                    continue
                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '相似房源',
                        district=listing.district or '未知商圈',
                        price=float(listing.final_price or 300),
                        rating=float(listing.rating or 4.5),
                        cover_image=listing.cover_image,
                        facilities=self._parse_facilities(listing.house_tags),
                        match_score=round(float(sim_score), 2),
                        reason=f"相似度 {sim_score:.0%}",
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )
        finally:
            db.close()

        return RecommendationResponse(
            recommendations=recommendations,
            user_preferences={"based_on": base_id},
        )

    def _sql_similar_fallback(
        self, homestay_id: str, top_k: int
    ) -> RecommendationResponse:
        """预计算矩阵中找不到时，按同商圈 + 相近价格查询。"""
        from app.db.database import SessionLocal, Listing

        db = SessionLocal()
        try:
            base = db.query(Listing).filter(Listing.unit_id == homestay_id).first()
            if not base:
                return RecommendationResponse(recommendations=[])

            query = db.query(Listing).filter(Listing.unit_id != homestay_id)
            if base.district:
                query = query.filter(Listing.district == base.district)
            if base.final_price:
                lo = float(base.final_price) * 0.7
                hi = float(base.final_price) * 1.3
                query = query.filter(Listing.final_price.between(lo, hi))

            from sqlalchemy import desc
            listings = query.order_by(desc(Listing.rating)).limit(top_k).all()

            recommendations = []
            for listing in listings:
                price_sim = 1 - abs(
                    float(listing.final_price or 0) - float(base.final_price or 0)
                ) / max(float(base.final_price or 1), 1)
                rating_score = float(listing.rating or 4) / 5.0
                score = round(price_sim * 0.5 + rating_score * 0.5, 2)

                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '相似房源',
                        district=listing.district or '',
                        price=float(listing.final_price or 0),
                        rating=float(listing.rating or 4.0),
                        cover_image=listing.cover_image,
                        facilities=self._parse_facilities(listing.house_tags),
                        match_score=score,
                        reason=f"同商圈相似价位",
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )

            return RecommendationResponse(
                recommendations=recommendations,
                user_preferences={"based_on": homestay_id},
            )
        except Exception as e:
            logger.error(f"SQL similar fallback error: {e}")
            return RecommendationResponse(recommendations=[])
        finally:
            db.close()

    # ==================================================================
    # 热门 / 个性化
    # ==================================================================

    def get_popular_homestays(
        self, district: Optional[str] = None, days: int = 30, top_k: int = 10
    ) -> RecommendationResponse:
        """基于评分 × log(收藏+1) 的热度排行。"""
        from app.db.database import SessionLocal, Listing
        from sqlalchemy import desc

        db = SessionLocal()
        try:
            query = db.query(Listing).filter(Listing.final_price.isnot(None))
            if district:
                query = query.filter(Listing.district == district)
            listings = query.order_by(desc(Listing.rating)).limit(top_k * 2).all()

            recommendations = []
            for listing in listings:
                heat = float(listing.rating or 4) * math.log(
                    float(listing.favorite_count or 0) + 1
                )
                score = min(1.0, heat / 10)
                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '热门房源',
                        district=listing.district or '',
                        price=float(listing.final_price or 0),
                        rating=float(listing.rating or 4.0),
                        cover_image=listing.cover_image,
                        facilities=self._parse_facilities(listing.house_tags),
                        match_score=round(score, 2),
                        reason=f"热度TOP | {int(listing.favorite_count or 0)}人收藏",
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )

            recommendations.sort(key=lambda x: x.match_score, reverse=True)
            return RecommendationResponse(recommendations=recommendations[:top_k])
        except Exception as e:
            logger.error(f"Popular homestays error: {e}")
            return RecommendationResponse(recommendations=[])
        finally:
            db.close()

    def get_personalized_recommendations(
        self, user_preferences: dict, top_k: int = 10
    ) -> RecommendationResponse:
        """基于用户偏好设置的个性化推荐。"""
        district = user_preferences.get('preferred_district')
        price_min = user_preferences.get('preferred_price_min')
        price_max = user_preferences.get('preferred_price_max')
        travel_purpose = user_preferences.get('travel_purpose')

        purpose_facilities = {
            '情侣': ['浴缸', '投影', '落地窗'],
            '家庭': ['厨房', '洗衣机'],
            '商务': ['WiFi', '近地铁'],
            '考研': ['安静', '书桌', 'WiFi'],
            '休闲': ['阳台', '浴缸'],
            '团建聚会': ['投影', '厨房', '麻将', '棋牌'],
            '医疗陪护': ['地铁', 'WiFi', '安静'],
            '宠物友好': ['宠物', '阳台'],
            '长租': ['洗衣机', '厨房', 'WiFi'],
        }

        result = self.get_recommendations(
            district=district, price_min=price_min, price_max=price_max, top_k=top_k * 2
        )

        if travel_purpose and travel_purpose in purpose_facilities:
            pref_facs = purpose_facilities[travel_purpose]
            for rec in result.recommendations:
                bonus = sum(1 for f in pref_facs if f in str(rec.facilities)) * 0.05
                rec.match_score = min(1.0, rec.match_score + bonus)
                if bonus > 0:
                    rec.reason = f"适合{travel_purpose} | {rec.reason}"

        result.recommendations = sorted(
            result.recommendations, key=lambda x: x.match_score, reverse=True
        )[:top_k]
        return result

    # ==================================================================
    # Fallback: 热门排行
    # ==================================================================

    def _fallback_recommend(self, district, price_min, price_max, capacity, top_k):
        from app.db.database import SessionLocal, Listing
        from sqlalchemy import desc

        db = SessionLocal()
        try:
            query = db.query(Listing)
            if district:
                query = query.filter(Listing.district == district)
            if price_min is not None:
                query = query.filter(Listing.final_price >= price_min)
            if price_max is not None:
                query = query.filter(Listing.final_price <= price_max)
            if capacity is not None:
                query = query.filter(Listing.capacity.isnot(None))
                query = query.filter(Listing.capacity >= capacity)

            listings = query.order_by(desc(Listing.rating)).limit(top_k).all()
            if not listings:
                return RecommendationResponse(recommendations=[])

            recommendations = []
            for listing in listings:
                rating_score = (float(listing.rating or 4.0) / 5.0) * 0.7
                fav_score = min(float(listing.favorite_count or 0), 100) / 100 * 0.3
                score = min(1.0, rating_score + fav_score)

                nh = self._nearest_hospital_km_optional(listing)
                hn = self._nearest_hospital_name_optional(listing)
                recommendations.append(
                    HomestayRecommendation(
                        id=str(listing.unit_id),
                        unit_id=str(listing.unit_id),
                        title=listing.title or '优质民宿',
                        district=listing.district or '未知商圈',
                        price=float(listing.final_price or 300),
                        rating=float(listing.rating or 4.5),
                        cover_image=listing.cover_image,
                        facilities=self._parse_facilities(listing.house_tags),
                        match_score=round(score, 2),
                        reason="高评分热门房源" if (listing.rating or 0) > 4.5 else "性价比优选",
                        nearest_hospital_km=nh,
                        nearest_hospital_name=hn,
                    )
                )
            return RecommendationResponse(recommendations=recommendations)
        except Exception as e:
            logger.error(f"Fallback recommend error: {e}")
            return RecommendationResponse(recommendations=[])
        finally:
            db.close()

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _parse_facilities(house_tags) -> list:
        """从 house_tags JSON 提取设施标签文本。"""
        if not house_tags:
            return []
        try:
            tags = json.loads(house_tags) if isinstance(house_tags, str) else house_tags
            result = []
            if isinstance(tags, list):
                for t in tags[:6]:
                    if isinstance(t, str):
                        result.append(t)
                    elif isinstance(t, dict):
                        tt = t.get('tagText', '')
                        if isinstance(tt, dict):
                            text = tt.get('text', '')
                        elif isinstance(tt, str):
                            text = tt
                        else:
                            text = ''
                        if text:
                            result.append(text)
            return result
        except Exception:
            return []


# 单例
recommendation_service = RecommendationService()
