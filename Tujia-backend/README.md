# 民宿价格数据分析系统 - 后端

基于大数据的民宿价格数据分析系统后端服务，使用 FastAPI + Hive + XGBoost 构建。

**Monorepo 说明**：本目录在完整仓库中为 **`Tujia-backend/`**。单独拉「后端部署分支」时，使用远程分支 **`deploy-backend`**（由 `git subtree split --prefix=Tujia-backend` 生成，根目录即本后端内容）。详见仓库根目录 [`../deploy/README.md`](../deploy/README.md)。

## 数据层说明（Hive 与 MySQL）

**线上运行时**以 **MySQL** 为权威数据源（列表、详情、驾驶舱、推荐、预测等默认只读 MySQL），部署简单、延迟低。**Apache Hive** 用于离线清洗、分层分析、模型训练特征与**导数入库**；生产建议 `HIVE_ANALYTICS_PRIMARY=false`（见 [.env.example](.env.example)）。详见 [docs/DATA_LAYER_AND_RUNTIME.md](docs/DATA_LAYER_AND_RUNTIME.md)。

### 生产部署检查清单（摘要）

- [ ] `DATABASE_URL` 指向 MySQL，已执行 `init_db` 或等价迁移  
- [ ] 已运行导数脚本（如 `scripts/import_full_data.py`），`listings` 有数据  
- [ ] `MODEL_PATH`、`RECOMMENDER_PATH` 文件存在  
- [ ] `DEBUG=false`，`SECRET_KEY` 已更换为强随机值（≥16 字符）  
- [ ] `HIVE_ANALYTICS_PRIMARY=false`，`HIVE_HEALTH_REQUIRED=false`（无需随 API 部署 Hive 时）  
- [ ] `CORS_ORIGINS` 配置为前端源（逗号分隔）；勿在生产使用 `allow_credentials=true` 且 `*`  

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │  认证   │ │  用户   │ │价格预测 │ │ 数据分析│ │ 推荐    │  │
│  │ Auth    │ │ User    │ │Predict  │ │Analysis │ │Recommend│  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
└───────┼───────────┼───────────┼───────────┼───────────┼───────┘
        │           │           │           │           │
        └───────────┴───────────┴───────────┴───────────┘
                              │
                    ┌─────────┴─────────┐
                    │    Service Layer  │
                    │  ┌─────────────┐  │
                    │  │ ML Model    │  │
                    │  │ Recommender │  │
                    │  └─────────────┘  │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────┴───────┐    ┌────────┴────────┐   ┌──────┴──────┐
│   SQLite/MySQL │    │      Hive       │   │   Scripts   │
│  (用户数据)    │    │   (业务数据)    │   │ (模型训练)  │
│  - 用户信息    │    │  - 房源数据     │   │ - XGBoost   │
│  - 偏好设置    │    │  - 价格数据     │   │ - 内容相似度推荐 │
│  - 登录token   │    │  - 评论数据     │   │ - 数据处理  │
└───────────────┘    └─────────────────┘   └─────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| Web框架 | FastAPI + Uvicorn |
| 认证 | JWT + Passlib |
| 用户数据库 | SQLite (默认) / MySQL (可选) |
| 业务数据仓库 | Apache Hive |
| 机器学习 | XGBoost, scikit-learn |
| 数据科学 | Pandas, NumPy |

## 目录结构

```
Tujia-backend/
├── app/                          # 主应用代码
│   ├── api/                      # API路由
│   │   ├── deps.py              # 依赖注入
│   │   └── endpoints/            # 各功能端点
│   │       ├── auth.py          # 登录注册
│   │       ├── user.py          # 用户管理
│   │       ├── predict.py       # 价格预测
│   │       ├── analysis.py      # 数据分析
│   │       └── recommend.py     # 推荐系统
│   ├── core/                     # 核心配置
│   │   ├── config.py            # 配置管理
│   │   └── security.py          # JWT、密码加密
│   ├── db/                       # 数据库连接
│   │   ├── hive.py              # Hive连接
│   │   └── database.py          # SQLite/MySQL ORM 与 get_db
│   ├── models/                   # 数据模型
│   │   └── schemas.py           # Pydantic模型
│   └── services/                 # 业务逻辑
│       ├── ml_model.py          # XGBoost模型服务
│       └── recommender.py       # 推荐服务
├── scripts/                      # 脚本工具
│   ├── build_recommendation_model.py  # 房源相似度矩阵（内容为主）
│   ├── model_training/          # 模型训练
│   │   └── train_price_model.py
│   └── data_processing/         # 数据处理
│       └── data_import.py
├── models/                       # 预训练模型文件
│   ├── xgboost_price_model.json
│   └── listing_similarity_*.npz（及 id 映射、meta，由 build_recommendation_model 生成）
├── main.py                       # 应用入口
└── requirements.txt              # 依赖列表
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 应用配置
APP_NAME=民宿价格数据分析系统
DEBUG=True
SECRET_KEY=your-secret-key-change-this-in-production

# 用户数据库 (默认SQLite，可选MySQL)
DATABASE_URL=sqlite:///./sql_app.db
# MySQL示例: mysql+pymysql://user:password@localhost/homestay_user_db

# Hive连接配置
HIVE_HOST=localhost
HIVE_PORT=10000
HIVE_USER=hadoop
HIVE_DATABASE=homestay_db

# 模型路径
MODEL_PATH=models/xgboost_price_model.json
RECOMMENDER_PATH=models/listing_similarity_latest.npz
```

### 3. 启动服务

```bash
# 开发模式（自动重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/api/health

## API端点说明

### 认证模块

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录（OAuth2） |
| POST | `/api/auth/login-json` | 用户登录（JSON） |
| GET | `/api/auth/me` | 获取当前用户信息 |
| POST | `/api/auth/refresh` | 刷新Token |

### 用户模块

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/user/me` | 获取用户资料 |
| PUT | `/api/user/me` | 更新用户资料 |
| GET | `/api/user/me/preferences` | 获取用户偏好 |
| PUT | `/api/user/me/preferences` | 更新推荐偏好 |

### 价格预测模块

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/predict/` | XGBoost价格预测 |
| GET | `/api/predict/quick` | 快速预测（GET参数） |
| GET | `/api/predict/district-average/{district}` | 商圈均价 |
| POST | `/api/predict/batch` | 批量预测 |

### 数据分析模块

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/analysis/district-stats` | 商圈统计 |
| GET | `/api/analysis/price-trend/{district}` | 价格趋势 |
| GET | `/api/analysis/facility-impact` | 设施溢价分析 |
| GET | `/api/analysis/seasonal-effect/{district}` | 季节效应分析 |
| GET | `/api/analysis/district-comparison` | 商圈对比 |

### 推荐与首页推荐条

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/home/recommendations` | 首页横向推荐（SQL+场景/设施重排） |
| GET | `/api/recommend/` | 个性化推荐页（条件/协同/兜底，见 docs） |
| POST | `/api/recommend/` | 同上，POST 参数 |
| GET | `/api/recommend/personalized` | 基于用户资料的个性化（内部多走协同再重排） |
| GET | `/api/recommend/similar/{id}` | 矩阵相似（当前前端业务页未接） |
| GET | `/api/recommend/popular` | 热门房源 |
| GET | `/api/listings/{unit_id}/similar` | 详情页规则相似（同区户型价近） |

### 房源列表（筛选与行为排序）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/listings` | 分页筛选；`keyword` 搜标题/区/商圈；`sort_by=personalized` + JWT 为 **规则区域重排**（见 [`docs/LISTINGS_PERSONALIZED_SORT.md`](docs/LISTINGS_PERSONALIZED_SORT.md)） |

## 两源数据与「完整房源」

- **`tujia_calendar_data.json`**：价日历、截面价、经纬度等（文件很大，需流式解析）。
- **`tujia_calendar_data_tags.json`**：详情页结构（户型、位置模块等）。

**完整样本** = 两个文件里 **unit_id 的交集**。单侧存在的 id 不应当作严谨分析的全量母体。

```bash
python scripts/listing_source_intersection.py
# 可选：导出交集 id 列表
python scripts/listing_source_intersection.py --write-ids data/hive_import/complete_unit_ids.txt
```

合并导入详情字段（**仅写交集**，日历用流式扫描）：

```bash
python scripts/import_full_data.py
```

## 文档索引

- **全部 Markdown 说明**（按用途分类）：[`docs/README.md`](docs/README.md)

## 测试与模块严谨性说明

- 答辩用简表、手工 E2E 清单、烟测说明：[`docs/MODULE_AUDIT_AND_SMOKE.md`](docs/MODULE_AUDIT_AND_SMOKE.md)
- 后端路由烟测（需可连配置中的数据库）：

```bash
pip install pytest httpx
pytest tests/test_smoke_routes.py -v
```

## 经纬度回填（竞品按距离）

平台房源表 `listings` 若缺少经纬度，可从日历 JSON 流式回填。建议与「完整样本」一致时加 **`--both-sources-only`**（仅回填在 `tags` 里也存在的 `unit_id`）：

```bash
pip install ijson
python scripts/backfill_listing_coordinates.py --dry-run
python scripts/backfill_listing_coordinates.py --both-sources-only
python scripts/backfill_listing_coordinates.py --force --both-sources-only   # 覆盖已有坐标
```

回填后，在「我的房源」中填写经纬度时，`GET /api/my-listings/{id}/competitors` 会在**同一行政区**内按**直线距离**优先选取最近竞品，并返回 `distance_km`。

## 模型训练

### 训练XGBoost价格预测模型

```bash
# 完整训练（含超参数调优）
python scripts/model_training/train_price_model.py --output models/xgboost_price_model.json

# 快速训练（跳过调优）
python scripts/model_training/train_price_model.py --skip-tuning --output models/xgboost_price_model.json
```

### 训练房源相似度矩阵（基于内容为主，交互充足时可融合行为相似度）

```bash
python scripts/build_recommendation_model.py
# 参数见脚本 --help；产物为 models/listing_similarity_latest.npz 等
```

论文/产品说明可侧重「内容特征 + 条件匹配」；详见 [`docs/THESIS_RECOMMENDATION_SYSTEM.md`](docs/THESIS_RECOMMENDATION_SYSTEM.md)。

### 房源场景多标签（TF-IDF + 逻辑回归，回写 `scene_scores` + `nearest_hospital_km`）

与前端「出行目的」英文 key 一致（含 `team_party` / `medical` / `pet_friendly` / `long_stay` 等共八类，详见文档）。离线流水线会写入 **场景概率 JSON** 与 **至最近医院 POI 的直线距离（km）**（`data/hospital_poi_wuhan.json`）。条件推荐 **读库** 叠加目的概率加分；当 `travel_purpose=medical` 时再叠加距离加分（不在线算 POI）。列表/详情与推荐项 schema 可带 `nearest_hospital_km` 供前端展示。说明与命令见 [`docs/LISTING_SCENE_TFIDF_PIPELINE.md`](docs/LISTING_SCENE_TFIDF_PIPELINE.md)。

```bash
python scripts/listing_scene_pipeline.py
```

## 前端集成示例

### 登录

```javascript
const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'username=test&password=test123'
});
const data = await response.json();
// 保存 token: data.access_token
```

### 价格预测

```javascript
const response = await fetch('http://localhost:8000/api/predict/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        district: "江汉路",
        room_type: "整套房屋",
        capacity: 4,
        bedrooms: 2,
        bathrooms: 1,
        has_wifi: true,
        is_weekend: false
    })
});
```

## Docker 本地 Hive（四层：ODS → DWD → DWS → ADS）

离线数仓表结构与装载逻辑见 [`sql/hive_load_data.hql`](sql/hive_load_data.hql)，说明见 [`docs/HIVE_GUIDE.md`](docs/HIVE_GUIDE.md)。

```bash
# 1) MySQL → TSV
python scripts/export_mysql_for_hive.py
# 2) 启动 Hive（首次全量）
docker compose -f docker-compose-hive.yml up -d
python scripts/hive_docker_import.py
# 仅重跑 HQL（容器与元数据已就绪）
python scripts/hive_docker_import.py --skip-up --skip-schema-init
```

HiveServer2 默认映射本机端口 **10000**；应用侧 `HIVE_HOST=localhost`、`HIVE_DATABASE=tujia_dw` 与 [`app/core/config.py`](app/core/config.py) 一致即可用 **pyhive / impyla** 直连。分析类接口默认 **`HIVE_ANALYTICS_PRIMARY=true`**（商圈统计、设施溢价、价格分布、ADS 洼地/ROI 优先读 Hive）；仅想全部走 MySQL 时设为 `false`。

## Hive数据表结构建议

### 原始数据表 (ODS)

```sql
-- 房源原始数据
CREATE TABLE ods_homestay_listings (
    id STRING,
    title STRING,
    district STRING,
    price DECIMAL(10,2),
    rating DECIMAL(2,1),
    review_count INT,
    facilities STRING,
    created_at TIMESTAMP
)
PARTITIONED BY (dt STRING);

-- 评论原始数据
CREATE TABLE ods_reviews (
    id STRING,
    homestay_id STRING,
    user_id STRING,
    rating INT,
    content STRING,
    created_at TIMESTAMP
)
PARTITIONED BY (dt STRING);
```

### 明细数据表 (DWD)

```sql
-- 日粒度房源数据
CREATE TABLE dwd_homestay_daily (
    id STRING,
    district STRING,
    price DECIMAL(10,2),
    rating DECIMAL(2,1),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    created_at TIMESTAMP
)
PARTITIONED BY (dt STRING);
```

### 汇总数据表 (ADS)

```sql
-- 商圈统计
CREATE TABLE ads_district_stats (
    district STRING,
    avg_price DECIMAL(10,2),
    total_listings INT,
    avg_rating DECIMAL(2,1),
    updated_at TIMESTAMP
);

-- 设施溢价分析
CREATE TABLE ads_facility_impact (
    facility_name STRING,
    avg_premium DECIMAL(10,2),
    premium_percent DECIMAL(5,2)
);
```

## 注意事项

1. **数据安全**: 生产环境请更换 `SECRET_KEY`，并使用HTTPS
2. **Hive 连接**: 本地 Docker 见上文「Docker 本地 Hive」；确保 `localhost:10000` 可达且已执行导入脚本
3. **模型文件**: 首次运行若无模型文件，系统会使用模拟数据
4. **用户数据**: 默认使用SQLite，生产环境可切换至MySQL

## 联系方式

如有问题请联系：龚婷 - 202219274207
