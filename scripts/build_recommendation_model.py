"""
混合协同过滤推荐模型训练脚本 (Hybrid Collaborative Filtering)

方法论:
  1. 内容相似度 (Content-Based Filtering):
     - 房源多维特征分组提取（结构、价格、质量、设施、位置）
     - 各组独立标准化后按领域权重缩放
     - TruncatedSVD 提取潜在语义因子，降低噪声与维度灾难
     - 在潜在因子空间计算余弦相似度

  2. 行为相似度 (User Behavior-Based CF):
     - 利用用户收藏 (强信号) 和浏览历史 (弱信号) 构建 User-Item 隐式反馈矩阵
     - 应用 IUF (Inverse User Frequency) 加权，抑制热门物品偏差
     - 计算 Item-Item 余弦相似度

  3. 混合融合 (Hybrid Fusion):
     S_hybrid = α × S_content + (1 − α) × S_behavior
     当行为数据不足时自动退化为纯内容相似度 (α = 1)

  4. 评估指标:
     内容一致性: Coverage@K, Avg_Similarity@K, District_Consistency, Price_MAE_Ratio, Diversity@K
     用户行为 (留一法): HitRate@K, MRR (Mean Reciprocal Rank)

参考文献:
  - Koren Y., Bell R., Volinsky C. "Matrix Factorization Techniques for Recommender Systems", IEEE Computer, 2009
  - Sarwar B. et al. "Item-Based Collaborative Filtering Recommendation Algorithms", WWW, 2001
  - Burke R. "Hybrid Recommender Systems: Survey and Experiments", UMUAI, 2002

Usage:
    python scripts/build_recommendation_model.py [--alpha 0.7] [--n-factors 50] [--top-k 20]
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, save_npz, diags
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 特征分组权重 —— 通过 sqrt(weight) 缩放使其在余弦内积中等效加权
# ---------------------------------------------------------------------------
FEATURE_GROUP_WEIGHTS = {
    'structural': 0.30,
    'price':      0.15,
    'quality':    0.15,
    'facility':   0.25,
    'location':   0.15,
}

FACILITY_KEYWORDS = {
    'has_projector':  ['投影', '巨幕', '家庭影院'],
    'has_kitchen':    ['厨房', '做饭', '烹饪', '可做饭'],
    'has_washer':     ['洗衣机', '洗衣'],
    'has_bathtub':    ['浴缸', '泡澡'],
    'has_smart_lock': ['智能锁', '智能门锁', '密码锁'],
    'has_wifi':       ['WiFi', 'wifi', '无线网络'],
    'has_ac':         ['空调', '冷暖'],
    'has_parking':    ['停车', '车位', '免费停车'],
    'has_balcony':    ['阳台', '露台', '落地窗'],
    'has_mahjong':    ['麻将', '棋牌'],
    'has_fridge':     ['冰箱'],
    'has_tv':         ['电视'],
}


class HybridRecommendationTrainer:
    """
    混合协同过滤推荐模型训练器

    将基于内容的过滤与基于用户行为的协同过滤相结合，
    通过 TruncatedSVD 提取潜在因子，在潜在空间中度量房源相似度。
    """

    def __init__(self, alpha: float = 0.7, n_factors: int = 50, top_k: int = 20):
        self.alpha = alpha
        self.n_factors = n_factors
        self.top_k = top_k
        self.scaler = StandardScaler()
        self.svd = None

    # ======================================================================
    # 数据加载
    # ======================================================================

    def _get_engine(self):
        from sqlalchemy import create_engine
        return create_engine(settings.DATABASE_URL)

    def _load_listing_data(self) -> pd.DataFrame:
        """
        加载房源数据。
        优先使用 raw_listings（含已提取的设施布尔列），
        回退到 listings 表（需解析 house_tags JSON）。
        """
        engine = self._get_engine()

        # ---------- 方案 1: raw_listings ----------
        try:
            query = """
                SELECT unit_id, district, price, rating,
                       comment_count, favorite_count,
                       bedroom_count, bathroom_count, bed_count,
                       area_sqm AS area, pic_count, heat_score,
                       has_projector, has_kitchen,
                       has_washing_machine AS has_washer,
                       has_bathtub, has_smart_lock,
                       has_floor_window   AS has_balcony,
                    has_ac, has_wifi, has_tv, has_heater
                FROM raw_listings
                WHERE price IS NOT NULL AND price > 0
            """
            df = pd.read_sql(query, engine)
            if len(df) > 0:
                logger.info(f"从 raw_listings 加载 {len(df)} 条记录")
                return df
        except Exception as e:
            logger.warning(f"raw_listings 不可用 ({e})，尝试 listings 表")

        # ---------- 方案 2: listings ----------
        query = """
            SELECT unit_id, district,
                   final_price AS price, rating,
                   favorite_count, pic_count,
                   bedroom_count, bed_count,
                   area, capacity, house_type, house_tags,
                   longitude, latitude
            FROM listings
            WHERE final_price IS NOT NULL AND final_price > 0
        """
        df = pd.read_sql(query, engine)
        if len(df) == 0:
            raise ValueError("listings 表无有效数据")
        logger.info(f"从 listings 加载 {len(df)} 条记录")
        df = self._parse_tags_to_facilities(df)
        return df

    def _parse_tags_to_facilities(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 house_tags JSON 字段解析出设施布尔列。"""
        for col in FACILITY_KEYWORDS:
            df[col] = 0

        for idx, row in df.iterrows():
            raw = row.get('house_tags')
            if not raw or (isinstance(raw, float) and pd.isna(raw)):
                continue
            try:
                tags = json.loads(raw) if isinstance(raw, str) else raw
                texts = []
                if isinstance(tags, list):
                    for t in tags:
                        if isinstance(t, dict):
                            tt = t.get('tagText', '')
                            if isinstance(tt, dict):
                                texts.append(tt.get('text', ''))
                            elif isinstance(tt, str):
                                texts.append(tt)
                        elif isinstance(t, str):
                            texts.append(t)
                combined = ' '.join(texts)
                for col, keywords in FACILITY_KEYWORDS.items():
                    if any(kw in combined for kw in keywords):
                        df.at[idx, col] = 1
            except (json.JSONDecodeError, TypeError):
                continue
            return df

    def _load_user_behavior(self):
        """加载用户收藏 + 浏览历史。"""
        engine = self._get_engine()
        try:
            fav_df = pd.read_sql("SELECT user_id, unit_id FROM favorites", engine)
            logger.info(f"收藏记录: {len(fav_df)} 条, {fav_df['user_id'].nunique()} 个用户")
        except Exception:
            fav_df = pd.DataFrame(columns=['user_id', 'unit_id'])

        try:
            view_df = pd.read_sql(
                "SELECT user_id, unit_id, view_duration FROM user_view_history "
                "ORDER BY created_at DESC LIMIT 50000", engine
            )
            logger.info(f"浏览记录: {len(view_df)} 条, {view_df['user_id'].nunique()} 个用户")
        except Exception:
            view_df = pd.DataFrame(columns=['user_id', 'unit_id', 'view_duration'])

        return fav_df, view_df

    # ======================================================================
    # 特征工程
    # ======================================================================

    def _build_feature_matrix(self, df: pd.DataFrame):
        """
        分组加权特征矩阵构建。

        每组特征独立 StandardScaler 标准化后乘以 sqrt(group_weight)，
        使得余弦相似度中每组的贡献与设定权重一致。

        Returns
        -------
        features : np.ndarray  (n_items, n_features)
        feature_names : list[str]
        """
        groups = {}
        names  = {}

        # -- 结构特征 --
        cols = [c for c in ['bedroom_count', 'bed_count', 'area', 'capacity', 'bathroom_count'] if c in df.columns]
        if cols:
            data = df[cols].fillna(0).values.astype(float)
            groups['structural'] = StandardScaler().fit_transform(data)
            names['structural'] = cols

        # -- 价格特征 --
        price = df['price'].fillna(0).values.astype(float).reshape(-1, 1)
        bedroom = df['bedroom_count'].fillna(1).replace(0, 1).values.astype(float)
        price_per_br = (price.flatten() / bedroom).reshape(-1, 1)
        price_all = np.hstack([price, price_per_br])
        groups['price'] = StandardScaler().fit_transform(price_all)
        names['price'] = ['price', 'price_per_bedroom']

        # -- 质量评价特征 --
        qcols = [c for c in ['rating', 'comment_count', 'favorite_count', 'heat_score', 'pic_count'] if c in df.columns]
        if qcols:
            qdata = df[qcols].fillna(0).values.astype(float)
            for i, c in enumerate(qcols):
                if c in ('comment_count', 'favorite_count', 'heat_score'):
                    qdata[:, i] = np.log1p(qdata[:, i])
            groups['quality'] = StandardScaler().fit_transform(qdata)
            names['quality'] = qcols

        # -- 设施特征 (0/1，加设施占比) --
        fcols = [c for c in FACILITY_KEYWORDS if c in df.columns]
        if fcols:
            fdata = df[fcols].fillna(0).values.astype(float)
            ratio = fdata.sum(axis=1, keepdims=True) / max(len(fcols), 1)
            groups['facility'] = np.hstack([fdata, ratio])
            names['facility'] = fcols + ['facility_ratio']

        # -- 位置特征 (独热编码) --
        if 'district' in df.columns:
            dummies = pd.get_dummies(df['district'], prefix='dist')
            groups['location'] = dummies.values.astype(float)
            names['location'] = dummies.columns.tolist()

        # -- 按权重缩放并拼接 --
        parts = []
        all_names = []
        for gname in ['structural', 'price', 'quality', 'facility', 'location']:
            if gname not in groups:
                continue
            w = FEATURE_GROUP_WEIGHTS.get(gname, 0.1)
            parts.append(groups[gname] * np.sqrt(w))
            all_names.extend(names.get(gname, []))

        features = np.hstack(parts)
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

        logger.info(f"特征矩阵: {features.shape[0]} 样本 × {features.shape[1]} 维")
        for gname, gdata in groups.items():
            w = FEATURE_GROUP_WEIGHTS.get(gname, 0.1)
            logger.info(f"  {gname:12s}: {gdata.shape[1]:3d} 维  权重 {w:.0%}")

        return features, all_names

    # ======================================================================
    # 相似度计算
    # ======================================================================

    def _compute_content_similarity(self, features: np.ndarray) -> np.ndarray:
        """
        内容相似度: 特征矩阵 → TruncatedSVD 降维 → 余弦相似度。

        SVD 降维消除特征噪声并缓解高维稀疏下余弦相似度趋同的问题，
        在潜在因子空间中计算的相似度具有更好的区分度。
        """
        n_samples, n_features = features.shape
        n_components = min(self.n_factors, n_features - 1, n_samples - 1)

        logger.info(f"TruncatedSVD: {n_features} 维 → {n_components} 潜在因子")
        self.svd = TruncatedSVD(n_components=n_components, random_state=42, n_iter=10)
        latent = self.svd.fit_transform(features)

        explained = self.svd.explained_variance_ratio_
        logger.info(f"累计解释方差: {explained.sum():.4f}")
        for i in range(min(5, len(explained))):
            logger.info(f"  PC{i+1}: {explained[i]:.4f}")

        sim = cosine_similarity(latent)
        np.fill_diagonal(sim, 1.0)
        logger.info(f"内容相似度: mean={sim.mean():.4f}, std={sim.std():.4f}")
        return sim

    def _compute_behavior_similarity(self, fav_df, view_df, listing_ids) -> np.ndarray:
        """
        基于用户行为的 Item-CF 相似度。

        1. 构建 User-Item 隐式反馈矩阵（收藏 weight=3, 浏览 weight=1+时长奖励）
        2. 列维度乘以 IUF = log(N_users / popularity_j) 抑制热门偏差
        3. 转置后计算 item-item 余弦相似度
        """
        n_items = len(listing_ids)
        id_to_idx = {str(lid): i for i, lid in enumerate(listing_ids)}

        interactions = []
        user_set = set()

        if fav_df is not None:
            for _, row in fav_df.iterrows():
                uid, uid_str = int(row['user_id']), str(row['unit_id'])
                if uid_str in id_to_idx:
                    interactions.append((uid, id_to_idx[uid_str], 3.0))
                    user_set.add(uid)

        if view_df is not None:
            for _, row in view_df.iterrows():
                uid, uid_str = int(row['user_id']), str(row['unit_id'])
                if uid_str in id_to_idx:
                    dur = float(row.get('view_duration', 0) or 0)
                    w = 1.0 + min(dur / 60.0, 2.0)
                    interactions.append((uid, id_to_idx[uid_str], w))
                    user_set.add(uid)

        n_users = len(user_set)
        logger.info(f"行为数据: {n_users} 用户, {len(interactions)} 条交互")

        if n_users < 3 or len(interactions) < 10:
            logger.warning("行为数据不足 (需 ≥3 用户 & ≥10 条交互)，跳过行为相似度")
            return None

        user_list = sorted(user_set)
        u2i = {uid: i for i, uid in enumerate(user_list)}

        rows, cols, data = [], [], []
        for uid, item_idx, w in interactions:
            rows.append(u2i[uid])
            cols.append(item_idx)
            data.append(w)

        ui_mat = csr_matrix((data, (rows, cols)), shape=(n_users, n_items))

        # IUF 加权
        popularity = np.array((ui_mat > 0).sum(axis=0)).flatten() + 1
        iuf = np.log(n_users / popularity)
        ui_weighted = ui_mat.dot(diags(iuf))

        # item-item 余弦相似度
        item_vecs = ui_weighted.T
        bsim = cosine_similarity(item_vecs)
        np.fill_diagonal(bsim, 1.0)

        nonzero_ratio = np.count_nonzero(bsim) / bsim.size
        logger.info(f"行为相似度: mean={bsim.mean():.4f}, 非零率={nonzero_ratio:.4f}")
        return bsim

    def _fuse_similarity(self, content_sim, behavior_sim) -> np.ndarray:
        """S_hybrid = α × S_content + (1 − α) × S_behavior"""
        if behavior_sim is None:
            logger.info("无有效行为数据 → 使用纯内容相似度 (α=1.0)")
            return content_sim

        alpha = self.alpha
        hybrid = alpha * content_sim + (1 - alpha) * behavior_sim

        lo, hi = hybrid.min(), hybrid.max()
        if hi > lo:
            hybrid = (hybrid - lo) / (hi - lo)
        np.fill_diagonal(hybrid, 1.0)

        logger.info(f"混合融合: α={alpha:.2f} (内容) + {1 - alpha:.2f} (行为)")
        logger.info(f"融合矩阵: mean={hybrid.mean():.4f}, std={hybrid.std():.4f}")
        return hybrid

    # ======================================================================
    # 评估
    # ======================================================================

    def _evaluate(self, sim_matrix, df, fav_df) -> dict:
        """
        离线评估。

        内容一致性 (无需用户行为):
          - Coverage@K       推荐覆盖率
          - Avg_Sim@K        平均相似度 (区分度检测)
          - District_Hit@K   商圈一致率
          - Price_MAE_Ratio  价格相对偏差
          - Diversity@K      Top-K 内多样性 (1 − avg pairwise sim)

        用户行为 (留一法, 需 ≥2 条收藏的用户):
          - HitRate@K        命中率
          - MRR              Mean Reciprocal Rank
        """
        n = sim_matrix.shape[0]
        K = min(self.top_k, n - 1)
        metrics = {}

        logger.info(f"\n{'=' * 60}")
        logger.info(f"模型评估  Top-{K}")
        logger.info(f"{'=' * 60}")

        # ---- 内容一致性 ----
        recommended_set = set()
        district_hits, district_total = 0, 0
        price_diffs, avg_sims, diversities = [], [], []

        prices = df['price'].fillna(0).values.astype(float)
        districts = df['district'].fillna('').values if 'district' in df.columns else None

        for i in range(n):
            row_sim = sim_matrix[i].copy()
            row_sim[i] = -1
            topk = np.argsort(row_sim)[::-1][:K]

            recommended_set.update(topk.tolist())
            avg_sims.append(row_sim[topk].mean())

            if districts is not None:
                district_hits += sum(1 for j in topk if districts[j] == districts[i])
                district_total += K

            if prices[i] > 0:
                price_diffs.append(np.mean(np.abs(prices[topk] - prices[i])) / prices[i])

            if K > 1:
                sub = sim_matrix[np.ix_(topk, topk)]
                mask = np.triu(np.ones_like(sub, dtype=bool), k=1)
                pw = sub[mask]
                if len(pw):
                    diversities.append(1 - pw.mean())

        metrics['coverage_at_k']          = len(recommended_set) / n
        metrics['avg_similarity_at_k']    = float(np.mean(avg_sims))
        metrics['district_consistency']   = district_hits / max(district_total, 1)
        metrics['price_mae_ratio']        = float(np.mean(price_diffs)) if price_diffs else 0.0
        metrics['diversity_at_k']         = float(np.mean(diversities)) if diversities else 0.0

        logger.info(f"  Coverage@{K}:          {metrics['coverage_at_k']:.4f}")
        logger.info(f"  Avg_Similarity@{K}:    {metrics['avg_similarity_at_k']:.4f}")
        logger.info(f"  District_Consistency:  {metrics['district_consistency']:.4f}")
        logger.info(f"  Price_MAE_Ratio:       {metrics['price_mae_ratio']:.4f}")
        logger.info(f"  Diversity@{K}:          {metrics['diversity_at_k']:.4f}")

        # ---- 留一法评估 ----
        if fav_df is not None and len(fav_df) > 0:
            listing_ids = df['unit_id'].astype(str).tolist()
            id2idx = {lid: i for i, lid in enumerate(listing_ids)}

            user_favs = {}
            for _, row in fav_df.iterrows():
                uid_str = str(row['unit_id'])
                if uid_str in id2idx:
                    user_favs.setdefault(int(row['user_id']), []).append(uid_str)

            hits, rrs, total = 0, [], 0
            for uid, fids in user_favs.items():
                if len(fids) < 2:
                    continue
                for lo_idx in range(len(fids)):
                    hidden = fids[lo_idx]
                    known  = [f for j, f in enumerate(fids) if j != lo_idx]

                    scores = np.zeros(n)
                    cnt = 0
                    for kid in known:
                        if kid in id2idx:
                            scores += sim_matrix[id2idx[kid]]
                            cnt += 1
                    if cnt == 0:
                        continue
                    scores /= cnt
                    for kid in known:
                        if kid in id2idx:
                            scores[id2idx[kid]] = -1

                    topk = np.argsort(scores)[::-1][:K]
                    h_idx = id2idx[hidden]
                    if h_idx in topk:
                        hits += 1
                        rank = int(np.where(topk == h_idx)[0][0]) + 1
                        rrs.append(1.0 / rank)
                    else:
                        rrs.append(0.0)
                    total += 1

            if total > 0:
                metrics['hit_rate_at_k'] = hits / total
                metrics['mrr'] = float(np.mean(rrs))
                metrics['loo_tests'] = total
                logger.info(f"\n  --- 留一法评估 ({total} 次) ---")
                logger.info(f"  HitRate@{K}: {metrics['hit_rate_at_k']:.4f}")
                logger.info(f"  MRR:         {metrics['mrr']:.4f}")
            else:
                logger.info("  收藏数据不足 (需 ≥2 条/用户)，跳过留一法")

        return metrics

    # ======================================================================
    # 保存 (兼容 model_manager.py)
    # ======================================================================

    def _save_model(self, sim_matrix, listing_ids, feature_names, metrics,
                    output_dir='models'):
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ids_str = [str(lid) for lid in listing_ids]

        # 1. 相似度矩阵 .npz
        sparse = csr_matrix(sim_matrix)
        for sfx in (ts, 'latest'):
            save_npz(f"{output_dir}/listing_similarity_{sfx}.npz", sparse)

        # 2. ID 映射 .json
        id_map = {
            'listing_ids': ids_str,
            'id_to_index': {lid: i for i, lid in enumerate(ids_str)},
            'index_to_id': {i: lid for i, lid in enumerate(ids_str)},
            'created_at': datetime.now().isoformat(),
            'total_listings': len(ids_str),
        }
        for sfx in (ts, 'latest'):
            with open(f"{output_dir}/listing_id_map_{sfx}.json", 'w', encoding='utf-8') as f:
                json.dump(id_map, f, ensure_ascii=False, indent=2)

        # 3. 元数据 .json
        meta = {
            'model_type': 'Hybrid Collaborative Filtering (SVD + Cosine)',
            'method': {
                'content': 'Feature Grouping → StandardScaler → TruncatedSVD → Cosine Similarity',
                'behavior': 'User-Item Implicit Feedback → IUF Weighting → Item-Item Cosine',
                'fusion': f'α·content + (1−α)·behavior, α={self.alpha}',
            },
            'parameters': {
                'alpha': self.alpha,
                'n_factors': self.n_factors,
                'top_k_eval': self.top_k,
                'feature_group_weights': FEATURE_GROUP_WEIGHTS,
            },
            'svd_explained_variance': float(self.svd.explained_variance_ratio_.sum()) if self.svd else None,
            'total_listings': len(ids_str),
            'feature_count': len(feature_names),
            'features': feature_names,
            'evaluation': metrics,
            'created_at': datetime.now().isoformat(),
        }
        for sfx in (ts, 'latest'):
            with open(f"{output_dir}/recommendation_meta_{sfx}.json", 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        logger.info(f"\n模型已保存到 {output_dir}/")
        logger.info(f"  listing_similarity_{ts}.npz  (shape={sim_matrix.shape})")
        logger.info(f"  listing_id_map_{ts}.json     ({len(ids_str)} 房源)")
        logger.info(f"  recommendation_meta_{ts}.json")
        return f"{output_dir}/listing_similarity_{ts}.npz"

    # ======================================================================
    # 推荐效果展示
    # ======================================================================

    def _show_examples(self, sim_matrix, df):
        logger.info("\n推荐效果示例:")
        indices = [0, len(df) // 4, len(df) // 2, len(df) * 3 // 4]
        for idx in indices:
            if idx >= len(df):
                continue
            r = df.iloc[idx]
            sims = sim_matrix[idx].copy()
            sims[idx] = -1
            top5 = np.argsort(sims)[::-1][:5]
            logger.info(f"\n  基准: [{r.get('district', '?')}] ¥{r.get('price', '?'):.0f}  "
                        f"({str(r.get('unit_id', ''))[:12]})")
            for rank, j in enumerate(top5, 1):
                t = df.iloc[j]
                logger.info(f"    Top{rank}: [{t.get('district', '?')}] ¥{t.get('price', '?'):.0f}  "
                            f"sim={sims[j]:.3f}")

    # ======================================================================
    # 主流程
    # ======================================================================

    def train(self) -> str:
        logger.info("=" * 60)
        logger.info("混合协同过滤推荐模型训练")
        logger.info(f"参数: α={self.alpha}, n_factors={self.n_factors}, top_k={self.top_k}")
        logger.info("=" * 60)

        logger.info("\n[1/6] 加载房源数据...")
        df = self._load_listing_data()
        if len(df) < 10:
            raise ValueError(f"数据量不足: 仅 {len(df)} 条")
        listing_ids = df['unit_id'].tolist()

        logger.info("\n[2/6] 加载用户行为数据...")
        fav_df, view_df = self._load_user_behavior()

        logger.info("\n[3/6] 构建特征矩阵...")
        features, feature_names = self._build_feature_matrix(df)

        logger.info("\n[4/6] 计算内容相似度 (SVD + Cosine)...")
        content_sim = self._compute_content_similarity(features)

        logger.info("\n[5/6] 计算行为相似度 (Item-CF)...")
        behavior_sim = self._compute_behavior_similarity(fav_df, view_df, listing_ids)

        hybrid_sim = self._fuse_similarity(content_sim, behavior_sim)

        logger.info("\n[6/6] 模型评估...")
        metrics = self._evaluate(hybrid_sim, df, fav_df)

        model_path = self._save_model(hybrid_sim, listing_ids, feature_names, metrics)
        self._show_examples(hybrid_sim, df)

        logger.info(f"\n{'=' * 60}")
        logger.info("训练完成!")
        logger.info(f"{'=' * 60}")
        return model_path


def main():
    parser = argparse.ArgumentParser(description='混合协同过滤推荐模型训练')
    parser.add_argument('--alpha', type=float, default=0.7,
                        help='内容相似度权重 α (0~1, 默认 0.7)')
    parser.add_argument('--n-factors', type=int, default=50,
                        help='SVD 潜在因子数 (默认 50)')
    parser.add_argument('--top-k', type=int, default=20,
                        help='评估 Top-K (默认 20)')
    args = parser.parse_args()

    trainer = HybridRecommendationTrainer(
        alpha=args.alpha,
        n_factors=args.n_factors,
        top_k=args.top_k,
    )
    trainer.train()


if __name__ == "__main__":
    os.makedirs("models", exist_ok=True)
    main()
