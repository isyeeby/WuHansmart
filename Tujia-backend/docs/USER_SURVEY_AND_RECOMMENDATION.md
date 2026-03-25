# 首登问卷与推荐 / 首页的联动

本文说明：**用户在问卷与个人资料中填写的偏好，如何进入在线推荐与首页展示**（实现于 2026-03 起迭代）。

**仅针对 `GET /api/recommend`**：条件 vs 行为协同 vs 兜底 以 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](./RECOMMENDATION_ONLINE_BEHAVIOR.md) 为准。「个性化推荐」页默认带出行目的，主路径为 **条件匹配**，一般不走纯收藏/浏览协同。**首页推荐条**走 `/api/home/recommendations`，见下文 §「GET `/api/home/recommendations`」。

## 数据落库

- 普通用户（`guest`）相关字段写入 `users`：`preferred_district`、`preferred_price_min/max`、`travel_purpose`（中文短词，**与推荐/场景标签对齐，表示浏览参考时偏好的房源类型，不表示本平台提供预订**）、`required_facilities`（JSON 数组，中文标签如「投影」「厨房」）。
- 出行目的中文 → 条件推荐引擎英文 key 的映射见 [`app/core/recommend_travel.py`](../app/core/recommend_travel.py)（与 `listings.scene_scores` 键一致）。
- 问卷设施中文 → 推荐设施键映射见 [`RecommendationService.USER_FACILITY_CN_TO_KEY`](../app/services/recommender.py) 与 `map_user_facilities_to_api_keys()`。

## GET `/api/recommend`（登录且未传对应查询参数时）

自动从当前用户补全：

| 查询参数缺省时 | 来源 |
|----------------|------|
| `district` | `users.preferred_district` |
| `price_min` / `price_max` | `users.preferred_price_*` |
| `travel_purpose` | `users.travel_purpose` → 经 `travel_purpose_for_condition_recommend` 转英文 key |
| `facilities`（整条未传） | `users.required_facilities` → 映射为 `projector`/`cooking` 等后进入条件推荐 |

当补全后的 `travel_purpose` 或设施列表非空时，走 **条件匹配 + 场景分加分**（`scene_scores` 已回写的前提下）。**仅当二者在补全后仍为空** 时，才进入 `get_recommendations`：**有行为且已加载相似度矩阵** 时尝试行为协同，否则热门兜底（详见 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](./RECOMMENDATION_ONLINE_BEHAVIOR.md)）。

## GET `/api/home/recommendations`

在原有「行政区 + 价格」SQL 过滤与评分基础上，对已登录用户：

- 按 `travel_purpose` 转英文后，对每条候选房源加上与 [`RecommendationService._scene_purpose_bonus`](../app/services/recommender.py) 一致的 **场景分加权**（缩放后参与排序）。
- 按问卷 **必带设施** 命中标签额外加分，再排序取 Top `limit`。

## 前端首页（TuJiaFeature）

- **「智能推荐」** 区块调用 **`GET /api/home/recommendations`**（[`homeApi.getHomeRecommendations`](../../TuJiaFeature/src/services/homeApi.ts)），与上文首页重排逻辑一致；**不再**用 `GET /api/recommend` 拉首页条。
- **常用功能** 卡片顺序随 `user.user_role`（`operator` / `investor` / `guest`）变化。
- 画像摘要 **`persona_summary`** 仅在 **个人信息页** 展示；首页不展示摘要（避免 Hero 信息过载）。

## 相关代码位置

| 能力 | 文件 |
|------|------|
| 推荐默认注入 | `app/api/endpoints/recommend.py` |
| 设施中文映射 | `app/services/recommender.py`（`USER_FACILITY_CN_TO_KEY`、`map_user_facilities_to_api_keys`） |
| 条件推荐内出行目的规范化 | `get_condition_based_recommendations` 内调用 `travel_purpose_for_condition_recommend` |
| 首页重排 | `app/api/endpoints/home.py`（`get_home_recommendations`） |
| 首页 UI / 接口调用 | `TuJiaFeature/src/pages/Home.tsx`、`homeApi.getHomeRecommendations` → `/api/home/recommendations` |
