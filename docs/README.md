# 项目文档索引（Tujia-backend）

按用途选读；**新增 Markdown 请在本文件登记一条**，避免重复散落。

## 阅读顺序（与实现对齐）

1. **数据从哪来、线上是否以 MySQL 为主** → [DATA_LAYER_AND_RUNTIME.md](DATA_LAYER_AND_RUNTIME.md)  
2. **指标名词与均价口径** → [METRICS_GLOSSARY.md](METRICS_GLOSSARY.md)  
3. **接口字段与首页/推荐差异** → [BACKEND_API_SPEC.md](BACKEND_API_SPEC.md)（冲突以运行中 `/docs` 为准）  
4. **`GET /api/recommend` 走哪条策略** → [RECOMMENDATION_ONLINE_BEHAVIOR.md](RECOMMENDATION_ONLINE_BEHAVIOR.md)  
5. **问卷字段如何进推荐与首页条** → [USER_SURVEY_AND_RECOMMENDATION.md](USER_SURVEY_AND_RECOMMENDATION.md)

## 运行与数据层

| 文档 | 说明 |
|------|------|
| [../README.md](../README.md) | 安装、环境变量、Docker Hive、脚本入口、烟测命令 |
| [DATA_LAYER_AND_RUNTIME.md](DATA_LAYER_AND_RUNTIME.md) | 线上 MySQL 主存、Hive 离线、`HIVE_ANALYTICS_PRIMARY`、导数脚本、两源 JSON 交集 |
| [METRICS_GLOSSARY.md](METRICS_GLOSSARY.md) | 商圈均价/模型价/竞品均价等口径对照 |
| [HIVE_GUIDE.md](HIVE_GUIDE.md) | ODS→DWD→DWS→ADS、`export_mysql_for_hive`、`hive_docker_import` |
| [MODULE_AUDIT_AND_SMOKE.md](MODULE_AUDIT_AND_SMOKE.md) | 模块×路由×API、口径风险、E2E/烟测清单 |

## 接口与产品

| 文档 | 说明 |
|------|------|
| [BACKEND_API_SPEC.md](BACKEND_API_SPEC.md) | **前后端共用**接口说明（含首页推荐条与 `/api/recommend` 区分） |
| [LISTINGS_PERSONALIZED_SORT.md](LISTINGS_PERSONALIZED_SORT.md) | 房源列表 `sort_by=personalized`：**规则区域重排**原理及与推荐接口边界 |
| [DASHBOARD_API.md](DASHBOARD_API.md) | `/api/dashboard/kpi`、`heatmap`、`top-districts` 等 |
| [USER_SURVEY_AND_RECOMMENDATION.md](USER_SURVEY_AND_RECOMMENDATION.md) | 问卷落库、`/api/recommend` 补全、`/api/home/recommendations` 重排、前端入口 |
| [RECOMMENDATION_ONLINE_BEHAVIOR.md](RECOMMENDATION_ONLINE_BEHAVIOR.md) | `/api/recommend` 分支；矩阵/冷启动；与首页、详情相似接口边界 |
| [PRD.md](PRD.md) | 产品需求 **v2.1**（当前功能与数据口径以代码+本索引为准） |
| [PRD_THESIS_v1.md](PRD_THESIS_v1.md) | 开题用长稿（2025-12）；与 v2/代码不一致时 **以 PRD.md 与代码为准** |

## 模型与论文素材

| 文档 | 说明 |
|------|------|
| [THESIS_PRICE_MODEL_PIPELINE.md](THESIS_PRICE_MODEL_PIPELINE.md) | 价格模型流水线与线上对齐 |
| [THESIS_RECOMMENDATION_SYSTEM.md](THESIS_RECOMMENDATION_SYSTEM.md) | 推荐论文体例（离线矩阵+在线策略）；**在线路由细节**以 `RECOMMENDATION_ONLINE_BEHAVIOR` 为准 |
| [LISTING_SCENE_TFIDF_PIPELINE.md](LISTING_SCENE_TFIDF_PIPELINE.md) | `scene_scores` / `nearest_hospital_km` 离线训练与读库加分 |
| [ML_DATA_FLOW.md](ML_DATA_FLOW.md) | Hive 分层与训练数据选型 |
| [MODEL_ACCURACY_EXPLANATION.md](MODEL_ACCURACY_EXPLANATION.md) | R² 等指标释义（示例数值以当次训练为准） |

## 维护说明

- 表结构以 [`app/db/database.py`](../app/db/database.py) 为准。待办与可选扩展见仓库根目录 [`TODO.md`](../TODO.md)。  
- 已从仓库移除的过时/重复稿：根目录 `QUICKSTART.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/DATABASE_ARCHITECTURE.md`；前端侧重复的 `BACKEND_API_SPEC.md`、`dashboard-api-requirements.md`、`SYSTEM_ANALYSIS.md`。  
- **Swagger**：`http://localhost:8000/docs` 与本文档冲突时以代码为准。

## 前端仓库（TuJiaFeature）

仅维护 [`TuJiaFeature/README.md`](../../TuJiaFeature/README.md)；API 与数据层链至 **`BACKEND_API_SPEC.md`**、**`DATA_LAYER_AND_RUNTIME.md`**。
