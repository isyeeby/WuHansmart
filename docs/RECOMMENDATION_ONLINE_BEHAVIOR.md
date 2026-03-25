# 在线推荐：真实路由与答辩口径

本文与代码一致，说明 **`GET /api/recommend` 的分支**、**「个性化推荐」页主路径**、**相似度矩阵**在条件推荐与行为协同中的不同用法。实现：[`recommend.py`](../app/api/endpoints/recommend.py)、[`recommender.py`](../app/services/recommender.py)。

问卷与首页推荐条联动见 [`USER_SURVEY_AND_RECOMMENDATION.md`](./USER_SURVEY_AND_RECOMMENDATION.md)。

## 双通道与产品展示约定

- **`GET /api/home/recommendations`（首页横向推荐条）** 与 **`GET/POST /api/recommend`（个性化推荐页）** 为**两套独立接口与实现**，**代码路径不合并**。
- 职责与字段差异见上文 §0 表格及 [`USER_SURVEY_AND_RECOMMENDATION.md`](./USER_SURVEY_AND_RECOMMENDATION.md)。
- **不在用户可见前端页面展示「双通道」类说明**；对内/答辩以本文档与 [`DATA_LAYER_AND_RUNTIME.md`](./DATA_LAYER_AND_RUNTIME.md) 为准。

## 0. 与其它接口的边界（易混）

| 能力 | 接口 | 方法概要 |
|------|------|----------|
| 首页「智能推荐」横向条 | `GET /api/home/recommendations` | MySQL 候选（登录可带行政区/价滤）+ 内存重排：`_scene_purpose_bonus` + 设施标签命中加分；**不是** `get_condition_based_recommendations`。见 [`home.py`](../app/api/endpoints/home.py)。 |
| 个性化推荐页 | `GET /api/recommend` | 下文 §1–§4。 |
| 详情页「相似房源」 | `GET /api/listings/{unit_id}/similar` | 同区、同卧室、价格接近排序；**不读** `listing_similarity_*.npz`。 |
| 基于矩阵的相似 | `GET /api/recommend/similar/{homestay_id}` | `RecommendationService.get_similar_homestays`；**当前前端业务页未使用**（`recommendApi.getSimilarListings` 无引用）。 |

## 1. `GET /api/recommend` 的分支（该接口内的规则）

FastAPI 中的判断顺序是：

1. 组装查询参数；若用户已登录，则用库内偏好**补全**缺省的 `district`、`price_min/max`、`travel_purpose`、`facilities`（见 [`USER_SURVEY_AND_RECOMMENDATION.md`](./USER_SURVEY_AND_RECOMMENDATION.md)）。
2. **若** `travel_purpose` 非空 **或** 设施列表 `facility_list` 非空 → 调用 **`get_condition_based_recommendations`（策略 1：条件匹配推荐）**。
3. **否则** → 调用 **`get_recommendations`**，其内部再尝试 **策略 2（基于收藏/浏览 + 相似度矩阵）**，失败则 **策略 3（热门兜底）**。

因此：**只要请求里最终带有出行目的或设施（含登录后由问卷注入），就不会进入「纯用户行为协同」那条 `get_recommendations` 主路径。**

## 2. 前端「个性化推荐」页实际走哪条策略

[`TuJiaFeature/src/pages/Recommendation.tsx`](../../TuJiaFeature/src/pages/Recommendation.tsx) 中表单 **默认** `target: 'couple'`（出行目的），首次加载与提交都会向 `/api/recommend` 带上 **`travel_purpose`**。

结论：**产品页名为「个性化推荐」，线上主路径是策略 1（条件匹配 + 质量/价格等打分 + 可选 `scene_scores` 加分），不是「基于当前用户收藏/浏览的 Item–Item 协同过滤」。**

若用户清空出行目的且不选设施、且未登录或库内也无注入，才会落到策略 2 或 3。

## 3. 策略 2（行为 + 矩阵）何时会用到

- 调用 **`get_recommendations`** 且 **`user_id` 有值** 时，内部会调 **`_cf_recommend_for_user`**（用收藏/浏览 + 相似度矩阵聚合）。
- 典型入口：
  - 上述 **未带条件** 的 `GET /api/recommend`；
  - **`GET /api/recommend/personalized`**：实现为先 **`get_recommendations`**（可触发策略 2），再按 `travel_purpose` 中文做加分与重排（见 `get_personalized_recommendations`）。

策略 2 **生效条件**（缺一不可）：

1. 磁盘上存在可加载的 **`listing_similarity_*.npz`** 及 ID 映射（否则启动日志 **`No recommender model found`**，矩阵为空）；
2. 用户有 **收藏或浏览** 等行为；否则 `_cf_recommend_for_user` 返回空，仍降级策略 3。

## 4. 相似度矩阵在策略 1 中的作用（≠ 行为协同）

在 **`get_condition_based_recommendations`** 中，对高匹配「种子」房源仍会尝试用 **同一套预计算矩阵** 做 **邻域扩展**（内容/混合相似度，取决于离线训练产物）。

- **有矩阵**：条件打分 + 相似扩展，结果更丰富。
- **无矩阵**：条件打分与排序仍可工作，扩展步骤实质退化。

这与策略 2「按**当前用户**历史在矩阵上聚合」是 **不同用法**。

## 5. 答辩/文档建议表述（简短版）

- **推荐页主线**：**显式条件**（出行目的、设施、价格、区划）+ **`scene_scores` 等读库加分**；登录后问卷可注入查询参数（见 USER_SURVEY）。
- **首页主线**：**`GET /api/home/recommendations`** — SQL 取候选 + 同套场景/设施重排；与推荐页共用问卷字段，但**不共用** `get_condition_based_recommendations` 整条链路。
- **可选增强**：离线矩阵用于 **条件推荐的邻域扩展**；**无目的且无设施** 且 **有行为与模型** 时，`/api/recommend` 走 **历史 + 矩阵**。
- **无模型文件**：**协同与扩展减弱**；条件推荐与首页 SQL 重排、热门兜底仍可用。

## 6. 部署与自检（与「No recommender model found」相关）

| 检查项 | 说明 |
|--------|------|
| 模型文件 | `ModelManager` 默认在 `models/` 下查找 `listing_similarity_*.npz`；无文件则打警告，矩阵为 `None`。 |
| 启动日志 | 出现 `No recommender model found` 表示 **未加载矩阵**；若产品以条件推荐为主，可接受，但需在文档/答辩中说明。 |
| 策略 2 烟测 | 使用 **有收藏/浏览** 的测试用户，且 **请求不带** `travel_purpose` 与设施，调 `GET /api/recommend`，观察是否仍主要为热门兜底（无模型时预期如此）。 |
| 策略 1 烟测 | 带 `travel_purpose=couple` 调 `GET /api/recommend`，应返回条件匹配结果；与是否有矩阵无关（扩展强弱可能不同）。 |

更偏论文体例的总体设计仍见 [`THESIS_RECOMMENDATION_SYSTEM.md`](./THESIS_RECOMMENDATION_SYSTEM.md)；**本文以线上路由为准**，若与旧叙述冲突，以本文与 `recommend.py` 为准。
