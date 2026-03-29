# 数据层与运行环境说明（毕设 / 答辩）

## 线上运行时数据面 = MySQL（生产推荐）

**目标**：线上 API **以 MySQL 为权威数据源**，请求延迟低、部署简单（单库或主从即可，无需随 API 同机部署 HiveServer2）。

| 阶段 | 组件 | 说明 |
|------|------|------|
| 离线清洗与分层 | **Hive**（ODS/DWD/DWS/ADS） | 大数据量批处理、数据分析、报表 |
| 特征与训练 | **Hive 或导出文件 → 训练脚本** | 如 `scripts/train_model_v2.py`；产出模型文件供 API 加载 |
| 导数入库 | **导入脚本 → MySQL** | `scripts/import_full_data.py`、`scripts/listing_scene_pipeline.py`、`scripts/backfill_listing_coordinates.py` 等写入 `listings` 等表 |
| **线上读写** | **MySQL** | Dashboard、列表、详情、推荐、预测、KPI 等**默认只读/写 MySQL** |

**配置**：生产建议设置 **`HIVE_ANALYTICS_PRIMARY=false`**（见 `.env.example`），使 `app/services/hive_service.py` 中分析类逻辑走 MySQL 回退，避免运行期强依赖 Hive。本地若需对比 Hive 聚合，可设为 `true`。

数据流（答辩可引用）：

```text
Hive（清洗/分析/训练） ──导数脚本──► MySQL ──► FastAPI ──► 前端
```

---

## 目标架构与当前实现（与上表一致）

| 层级 | 设计目标 | 当前部署 |
|------|----------|----------|
| 分析/数仓（DWS/ADS） | Apache Hive 四层加工结果 | **`HiveDataService`**（`app/services/hive_service.py`）在 `HIVE_ANALYTICS_PRIMARY=true`（默认）时优先查 Hive；**`false` 或 Hive 不可用**时回退 **MySQL** 现场聚合。**线上推荐 `false`**。 |
| 行级 OLTP | 单套房源、按区列表 | 始终 **MySQL** `listings`（`get_listing_detail`、`get_listings_by_district` 等）。 |
| Hive SQL 直连 | `app/db/hive.py` 的 `execute_query_to_df` | **pyhive** / **impyla**；失败时可试 Docker CLI。仅开发/离线任务必需。 |

环境与开关：

1. 连接参数见 `.env` / `app/core/config.py`（`HIVE_HOST`、`HIVE_PORT`、`HIVE_DATABASE`）。Docker 部署见 `docs/HIVE_GUIDE.md`。
2. 关闭「分析优先 Hive」：`HIVE_ANALYTICS_PRIMARY=false`，则 `hive_service` 分析类方法以 **MySQL** 为主。

## 导数入口与 MySQL 表（摘要）

| 脚本 | 作用 |
|------|------|
| `scripts/import_full_data.py` | 日历 + tags 流式合并入库（交集 unit_id） |
| `scripts/listing_scene_pipeline.py` | 写入 `listings.scene_scores`、`nearest_hospital_km` 等 |
| `scripts/backfill_listing_coordinates.py` | 回填 `listings.longitude` / `latitude` |
| `scripts/train_model_v2.py`（及 `model_training/`） | 离线训练，产出 `models/` 下模型文件 |

表结构以 [`app/db/database.py`](../app/db/database.py) 为准。

## 生产部署检查清单（摘要）

详见根目录 [`README.md`](../README.md)。

- [ ] `DATABASE_URL` 指向可写 MySQL，`init_db` 或迁移已执行  
- [ ] 已执行导数脚本，`listings` 有业务数据  
- [ ] `MODEL_PATH` / `RECOMMENDER_PATH` 指向存在文件  
- [ ] `HIVE_ANALYTICS_PRIMARY=false`（线上）  
- [ ] `SECRET_KEY` 已更换；`DEBUG=false`  
- [ ] `CORS_ORIGINS` 配置为前端域名（勿用 `*` + credentials）

## MySQL 表与 ORM

业务表以代码为准：[`app/db/database.py`](../app/db/database.py)（如 `listings`、`price_calendars`、`users`、`favorites`、`my_listings` 等）。不再单独维护易过期的「数据库大表」文档，避免与迁移脱节。

**`listings.scene_scores`**（JSON）、**`listings.nearest_hospital_km`**（数值，km）、**`listings.nearest_hospital_name`**（最近 POI 医院名称）：均由离线流水线 [`scripts/listing_scene_pipeline.py`](../scripts/listing_scene_pipeline.py) 写入。前者为八类场景概率（与 `travel_purpose` 英文 key 一致）；后者为至 `data/hospital_poi_wuhan.json` 中最近医院 POI 的 Haversine 距离。条件推荐 **只读库** 做加分（含 `travel_purpose=medical` 时的距离项），不在请求路径算 POI。详见 [`LISTING_SCENE_TFIDF_PIPELINE.md`](LISTING_SCENE_TFIDF_PIPELINE.md)。启动时 `init_db()` → `_ensure_extra_columns()` 会尝试为已存在的 `listings` 表补齐上述列（与手工执行 `sql/add_listing_*.sql` 等价意图）。用户问卷中的中文出行目的经 [`app/core/recommend_travel.py`](../app/core/recommend_travel.py) 与此处键对齐后再参与打分；与首页推荐、GET `/api/recommend` 的联动见 [`USER_SURVEY_AND_RECOMMENDATION.md`](USER_SURVEY_AND_RECOMMENDATION.md)。

## 推荐双通道（仅文档说明，不合并实现）

首页推荐 **`GET /api/home/recommendations`** 与个性化推荐 **`GET/POST /api/recommend`** 为**两套独立接口与实现**，**不合并**代码路径。差异见 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](RECOMMENDATION_ONLINE_BEHAVIOR.md) 与 [`USER_SURVEY_AND_RECOMMENDATION.md`](USER_SURVEY_AND_RECOMMENDATION.md)；**产品页面不向最终用户展示「双通道」文案**。

**房源列表** `GET /api/listings?sort_by=personalized` 使用 `favorites` + `user_view_history` 做 **Top-K 行政区/商圈规则重排**（SQL `CASE`），**不经**上述推荐路由，亦**不读**离线相似度矩阵；原理见 [`LISTINGS_PERSONALIZED_SORT.md`](LISTINGS_PERSONALIZED_SORT.md)。

## 指标与「真实」口径

部分接口返回 **启发式指数** 或 **示意序列**，与订单口径、财务 ROI 不同。详细对照见各接口 `description` 与响应内 `methodology` / `series_note` / `kpi_definitions`；聚合类指标线上以 **MySQL 表内数据** 为准。更多名词见 [`METRICS_GLOSSARY.md`](METRICS_GLOSSARY.md)。

## 途家原始 JSON：两源与交集

仓库内 **`tujia_calendar_data.json`** 与 **`tujia_calendar_data_tags.json`** 覆盖的 `unit_id` 集合**不一致**。论文与导入口径上，**完整房源**应定义为两文件中 **均出现的 unit_id（交集）**；仅在一侧出现的记录缺少价日历或缺少详情结构，不宜与交集样本混为同一母体。

- 统计与导出交集：`python scripts/listing_source_intersection.py`
- 详情合并入库（仅交集）：`python scripts/import_full_data.py`（日历流式 + tags 流式）
- 坐标回填（可选仅交集）：`python scripts/backfill_listing_coordinates.py --both-sources-only`

## 数据库结构演进

启动时 `init_db()` 会 `create_all` 并对已存在表执行轻量 `ALTER` 以补充新增列（如 `favorites.folder_name`、`users.email`、`user_view_history.last_viewed_at` 等）。若生产环境禁用自动 DDL，请手工执行等价迁移。启动时还会尝试创建 `listings` 常用查询索引（见 `_ensure_performance_indexes`）。

## 全栈排查与指标诚实性（实施记录摘要）

- **收藏 / 用户**：`Favorite` ORM 与 `folder_name`、价格提醒字段对齐；`User.email` 可选；`/api/my-listings` 按登录用户落库与查询。
- **热力图**：`/api/dashboard/heatmap` 在无经纬度时返回行政区哈希占位点并附 `series_note`。
- **KPI**：`occupancy_rate`、`avg_roi` 在接口中附 `kpi_definitions` 说明启发式口径；价格环比来自价格日历。
- **预测 `/trend`**：响应含 `data_kind` 与 `methodology`，标明示意序列；定价建议置信度改为与价差相关的确定性启发式。
- **首页**：`/api/home/*` 响应可含 `data_source`（`live` / `mysql` / `hive` / `demo_fallback` / `empty`），便于区分真实数据与演示兜底。
- **前端**：`favoritesApi` 与 `/api/user/me/*` 路径对齐；`analysisApi` 已移除无后端路由的「兼容」函数；首页/投资/对比/因子分析页补充口径说明。

论文撰写时请直接引用本节与各接口返回中的 `methodology` / `series_note` / `kpi_definitions`。
