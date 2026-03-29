# 房源列表「按行为偏好」排序（`sort_by=personalized`）

**实现**：[`app/api/endpoints/listings.py`](../app/api/endpoints/listings.py) 中 `get_listings`、`_user_preference_regions`、`_escape_like_pattern`（关键词检索另见同文件）。

## 原理：规则重排，非相似度矩阵

1. **行为聚合**：从 `favorites`、`user_view_history` 关联 `listings`，取每条行为对应房源的 `district`、`trade_area`。收藏每次权重 **3**，浏览每次权重 **1**，分别统计行政区、商圈频次，各取 **Top 5** 作为偏好集合。
2. **列表匹配分**：对当前筛选后的每一套房源，用 SQL `CASE`：若 `district` 落在偏好行政区集合 → **2** 分；否则若 `trade_area` 落在偏好商圈集合 → **1** 分；否则 **0** 分（行政区优先于商圈）。
3. **排序**：先按该分数 **降序**，再按 `favorite_count` **降序**。
4. **冷启动**：未登录、无有效 JWT、或偏好集合为空时，不叠加 CASE，效果与按 **收藏数** 排序一致。

## 与「个性化推荐」页、首页推荐条的区别

| 能力 | 接口 | 方法概要 |
|------|------|----------|
| **房源列表按偏好排序** | `GET /api/listings?sort_by=personalized`（可选 `Authorization`） | 上述 **Top-K 区域 + CASE** 规则；**不读** `listing_similarity_*.npz`，不调用 `RecommendationService` 矩阵分支 |
| 个性化推荐页 | `GET /api/recommend` | 条件匹配 / 收藏浏览 + 相似度矩阵等，见 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](./RECOMMENDATION_ONLINE_BEHAVIOR.md) |
| 首页横向推荐条 | `GET /api/home/recommendations` | SQL 候选 + 场景/设施重排，见 [`USER_SURVEY_AND_RECOMMENDATION.md`](./USER_SURVEY_AND_RECOMMENDATION.md) |

## 浏览历史写入

登录用户打开详情并成功拉取数据后，前端调用 `POST /api/user/me/history` 写入 `user_view_history`，为上述偏好统计提供信号；与协同过滤训练脚本读取的同表一致，但**列表排序不依赖离线矩阵**。
