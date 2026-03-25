# 民宿价格数据分析系统 - 产品需求文档 (PRD)

**版本**: v1.0
**日期**: 2025-12
**作者**: 龚婷
**指导教师**: 刘凤华

---

## 1. 文档概述

### 1.1 文档目的
本文档详细描述了"基于大数据的民宿价格数据分析系统"的产品需求，包括功能需求、非功能需求、系统架构、数据模型及界面交互设计，为开发团队提供明确的实施指导。

### 1.2 适用范围
- 开发团队：前后端开发人员、算法工程师、测试工程师
- 利益相关者：民宿经营者、投资者、监管部门、平台方

### 1.3 术语定义

| 术语 | 定义 |
|------|------|
| OTA | Online Travel Agency，在线旅行社，如途家、美团民宿 |
| RMS | Revenue Management System，收益管理系统 |
| 代理变量 | 用于替代无法直接观测变量的可测量指标，如用评论增量模拟订单量 |
| MGWR | Multi-scale Geographically Weighted Regression，多尺度地理加权回归 |
| XGBoost | eXtreme Gradient Boosting，极端梯度提升算法 |
| Hive | 基于Hadoop的数据仓库工具，用于大规模数据分析 |

---

## 2. 产品概述

### 2.1 产品背景
武汉作为"高校密集+交通枢纽"双属性城市，民宿市场呈现独特的"双元"结构：高校刚需市场与商旅游客市场并存。现有民宿经营者面临严重的"数据焦虑"与"决策盲区"，缺乏科学的定价参考与竞品分析工具。

### 2.2 产品目标
构建一个闭环的民宿价格决策支持平台，实现：
1. **数据采集与重构**：通过分布式爬虫采集途家网数据，利用代理变量法模拟历史成交
2. **多维分析**：基于Hive进行商圈维度的价格分析与波动规律挖掘
3. **智能预测**：XGBoost模型输出动态定价建议
4. **个性推荐**：基于内容相似度与条件匹配的房源推荐（可选结合用户行为）
5. **可视化展示**：直观呈现分析结果，辅助决策

### 2.3 目标用户

| 用户角色 | 核心需求 | 使用场景 |
|---------|---------|---------|
| 民宿经营者 | 智能定价、竞品监测、客群分析 | 日常运营决策 |
| 潜在投资者 | 市场饱和度、投资回报模拟 | 选址与产品定位 |
| 监管部门 | 市场监控、异常识别 | 政策制定与行业规范 |
| 平台方 | 优质房源筛选、违规识别 | 平台运营管理 |

---

## 3. 功能需求

### 3.1 功能架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      前端展示层 (React + TypeScript)              │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│  数据大屏   │  商圈分析   │  价格预测   │  房源推荐   │ 个人中心 │
│  Dashboard  │   Module    │  Predictor  │  Recommender│  Profile  │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴────┬────┘
       │             │             │             │           │
┌──────▼─────────────▼─────────────▼─────────────▼───────────▼────┐
│                    分析与算法层 (Python)                          │
├───────────┬───────────┬───────────┬───────────┬─────────────────┤
│ XGBoost   │ 相似度推荐 │ 统计分析  │ 特征工程  │  代理变量模型   │
│ 价格预测  │ 内容为主  │ 商圈分析  │ 特征处理  │  销量还原       │
└─────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┴────────┬────────┘
      │           │           │           │              │
┌─────▼───────────▼───────────▼───────────▼──────────────▼────────┐
│                    存储与计算层                                   │
├────────────────┬────────────────┬───────────────┬───────────────┤
│   Hadoop HDFS  │   Hive 数据仓库 │   MySQL/PostgreSQL │  Redis缓存   │
│   原始数据存储  │   离线分析计算  │   业务数据存储    │  热点数据    │
└───────┬────────┴────────┬───────┴───────┬───────┴───────┬───────┘
        │                 │               │               │
┌───────▼─────────────────▼───────────────▼───────────────▼───────┐
│                    数据采集与重构层                               │
├────────────────────────────┬────────────────────────────────────┤
│     Scrapy 分布式爬虫       │         定时调度任务                │
│  (房源/价格/评论/商圈数据)   │    (增量更新/模拟计算/模型重训)      │
└────────────────────────────┴────────────────────────────────────┘
```

### 3.2 核心功能模块

#### 3.2.1 数据采集与预处理模块

**功能编号**: F001
**功能名称**: 分布式数据采集
**优先级**: P0（核心）

**需求描述**:
- 基于Scrapy分布式框架，并发抓取武汉各行政区途家网房源数据
- 采集字段包括：
  - **房源基本信息**：房源ID、标题、位置（经纬度）、面积、卧室数、床位数、可住人数
  - **设施配置**：WiFi、空调、投影、智能锁、浴缸等标签
  - **价格信息**：实时挂牌价、历史价格变动
  - **评论数据**：评论数、评分、评论时间戳
  - **商圈标签**：所属商圈、距离地铁口距离、周边POI

**技术要求**:
- 动态User-Agent池轮换
- 分布式代理IP切换机制
- Selenium处理动态渲染内容（验证码、价格数据）
- 定时调度机制（每日增量更新）

**验收标准**:
- 数据采集成功率 ≥ 90%
- 支持并发抓取10个以上行政区
- 数据更新延迟 ≤ 24小时

---

#### 3.2.2 销量还原与模拟模块

**功能编号**: F002
**功能名称**: 基于代理变量的销量还原
**优先级**: P0（核心）

**需求描述**:
- 构建"评论增量-订单量"映射模型
- 基于行业公认的3:1-5:1订单-评论转化比，模拟历史成交序列
- 结合商圈折扣规则（挂牌价虚高12%-18%），反向推导真实成交价
- 处理特殊时段（节假日）的折扣偏差扩大问题

**算法逻辑**:
```
订单量 = 评论增量 × 转化系数 (3-5)
真实成交价 = 挂牌价 × (1 - 商圈折扣率)
折扣率修正 = 基础折扣率 + 节假日调整系数
```

**验收标准**:
- 销量模拟准确度偏差 ≤ 20%
- 价格还原误差控制在15%以内

---

#### 3.2.3 Hive多维分析模块

**功能编号**: F003
**功能名称**: 商圈维度离线分析
**优先级**: P1（重要）

**需求描述**:
- **商圈划分**：江汉路网红区、光谷高新差旅区、昙华林文创区等
- **供需分析**：各商圈房源密度、订单热度、价格中位数
- **效应分析**：
  - 周末效应：单价溢价率统计
  - 节假日效应：五一/十一涨幅分析
  - 特殊事件：马拉松季、开学季价格拉动系数
- **设施溢价分析**：量化特定标签（巨幕投影、智能锁、浴缸）的平均溢价金额

**Hive表结构设计**:
```sql
-- 房源基础信息表
CREATE TABLE t_listing (
    listing_id STRING,
    district STRING,
    business_circle STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    area DECIMAL(5,2),
    bedroom_count INT,
    bed_count INT,
    max_guests INT,
    amenities ARRAY<STRING>
);

-- 价格时序数据表
CREATE TABLE t_price_time_series (
    listing_id STRING,
    date DATE,
    listed_price DECIMAL(10,2),
    estimated_real_price DECIMAL(10,2),
    estimated_orders INT
);

-- 商圈统计汇总表
CREATE TABLE t_business_circle_stats (
    business_circle STRING,
    stat_date DATE,
    avg_price DECIMAL(10,2),
    median_price DECIMAL(10,2),
    listing_count INT,
    order_heat_score DOUBLE
);
```

**验收标准**:
- 支持百万级数据的秒级聚合查询
- 商圈维度分析响应时间 ≤ 3秒

---

#### 3.2.4 价格预测模块

**功能编号**: F004
**功能名称**: XGBoost智能定价
**优先级**: P0（核心）

**需求描述**:
- **特征工程**：
  - 地理特征：到最近地铁口距离、到地标景观距离
  - 物理特征：床位数、面积、卧室数
  - 信誉特征：评分、评论数
  - 时间特征：星期、月份、节假日标识
  - 商圈特征：所属商圈类型、周边POI密度
- **模型训练**：XGBoost回归算法，GridSearchCV超参数优化
- **预测输出**：未来7-14天动态建议挂牌价区间
- **特殊事件提示**：标注重大事件导致的调价时机

**特征列表**:

| 特征类别 | 特征名称 | 数据类型 | 说明 |
|---------|---------|---------|------|
| 地理特征 | distance_to_metro | FLOAT | 到最近地铁口距离(米) |
| 地理特征 | distance_to_landmark | FLOAT | 到地标距离(米) |
| 物理特征 | area | FLOAT | 房源面积(m²) |
| 物理特征 | bedroom_count | INT | 卧室数量 |
| 物理特征 | bed_count | INT | 床位数量 |
| 信誉特征 | rating | FLOAT | 综合评分 |
| 信誉特征 | review_count | INT | 评论数量 |
| 时间特征 | day_of_week | INT | 星期(0-6) |
| 时间特征 | month | INT | 月份(1-12) |
| 时间特征 | is_holiday | BOOLEAN | 是否节假日 |
| 商圈特征 | business_circle_type | STRING | 商圈类型编码 |

**模型评估指标**:
- MAE（平均绝对误差）目标：较线性回归降低28.6%
- R² Score ≥ 0.75
- 支持按商圈分层建模

**验收标准**:
- 单房源预测响应时间 ≤ 500ms
- 预测准确度MAE ≤ 30元

---

#### 3.2.5 个性化推荐模块

**功能编号**: F005
**功能名称**: 基于内容相似度的房源推荐
**优先级**: P1（重要）

**需求描述**:
- 基于用户的浏览历史、收藏行为构建用户画像
- 采用多维房源特征与相似度矩阵；交互数据充足时训练脚本可融合 Item-Item 行为相似度
- 推荐相似房源或热门房源
- 解决小众特色房源的冷启动问题

**推荐场景**:
- 相似房源推荐："看过此房源的用户还看了"
- 热门房源推荐：基于商圈的热度排行
- 个性化推荐：基于用户偏好的智能推荐

**验收标准**:
- 推荐响应时间 ≤ 1秒
- 推荐点击率 ≥ 10%

---

#### 3.2.6 可视化展示模块

**功能编号**: F006
**功能名称**: 数据可视化与交互
**优先级**: P1（重要）

**需求描述**:
- **经营驾驶舱Dashboard**：
  - 核心指标卡片：平均价格、入住率趋势、竞品动态
  - 价格走势折线图：历史价格与未来预测对比
  - 商圈对比看板：多商圈指标横向对比

- **商圈分析页面**：
  - 价格热力图：基于地图的价格分布可视化
  - 供需关系图：商圈饱和度分析
  - 设施溢价排行榜

- **预测结果页面**：
  - 定价建议日历视图
  - 价格区间推荐卡片
  - 调价时机提醒

**UI组件库**: Ant Design + ECharts
**响应式设计**: 支持PC端、平板访问

**验收标准**:
- 页面加载时间 ≤ 2秒
- 图表交互流畅度 ≥ 60fps
- 支持Chrome、Firefox、Safari主流浏览器

---

## 4. 非功能需求

### 4.1 性能需求

| 指标 | 要求 | 说明 |
|-----|------|------|
| 系统响应时间 | ≤ 3秒 | 95%的请求在3秒内响应 |
| 并发用户支持 | ≥ 100 | 支持100个用户同时在线 |
| 数据采集频率 | 每日1次 | 定时增量更新 |
| 模型重训频率 | 每周1次 | 自动触发模型更新 |
| Hive查询响应 | ≤ 5秒 | 百万级数据聚合查询 |
| 数据库查询 | ≤ 500ms | 单条记录查询 |

### 4.2 可用性需求

- **系统可用性**: ≥ 99.5%（年度计划停机时间 ≤ 43.8小时）
- **故障恢复**: 支持自动故障转移，RTO ≤ 10分钟
- **数据备份**: 每日全量备份，保留30天

### 4.3 安全性需求

- **数据加密**: 敏感数据（手机号、身份证）采用AES加密存储
- **访问控制**: 基于RBAC的权限管理，支持角色分级
- **爬虫合规**: 遵守robots协议，请求频率控制（≤ 1次/秒）
- **隐私保护**: 符合《个人信息保护法》《数据安全法》要求

### 4.4 可扩展性需求

- 支持水平扩展，可通过增加节点提升处理能力
- 支持新增商圈的快速接入
- 支持新算法的插件化集成

---

## 5. 系统架构设计

### 5.1 技术栈

| 层级 | 技术选型 | 说明 |
|-----|---------|------|
| 前端 | React 18 + TypeScript 5 | 响应式UI框架 |
| 前端UI | Ant Design 5.x | 企业级UI组件库 |
| 可视化 | ECharts 5.x | 数据可视化图表 |
| 后端 | Python 3.11 + FastAPI | 高性能API框架 |
| 机器学习 | XGBoost + Scikit-learn | 算法库 |
| 爬虫 | Scrapy 2.x + Selenium | 分布式爬虫 |
| 大数据 | Hadoop 3.x + Hive 3.x | 分布式存储与计算 |
| 数据库 | MySQL 8.0 / PostgreSQL 15 | 关系型数据库 |
| 缓存 | Redis 7.x | 热点数据缓存 |
| 任务调度 | Apache Airflow / Celery | 定时任务调度 |
| 部署 | Docker + Docker Compose | 容器化部署 |

### 5.2 部署架构

```
                    ┌─────────────┐
                    │   用户浏览器   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Nginx反向代理 │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │ 前端服务 │       │ API服务 │       │ 管理后台 │
   │  React  │       │ FastAPI │       │  Airflow │
   └─────────┘       └────┬────┘       └─────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │  MySQL  │      │  Redis  │      │  Hive   │
   │业务数据库 │      │  缓存   │      │ 数据仓库 │
   └─────────┘      └─────────┘      └────┬────┘
                                           │
                                    ┌──────▼──────┐
                                    │  Hadoop HDFS │
                                    │  分布式存储  │
                                    └─────────────┘
```

---

## 6. 数据模型设计

### 6.1 业务数据库表结构（MySQL）

```sql
-- 用户表
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('operator', 'investor', 'admin', 'platform') DEFAULT 'operator',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 房源基础信息表
CREATE TABLE listings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    listing_id VARCHAR(50) UNIQUE NOT NULL COMMENT '途家房源ID',
    title VARCHAR(255) NOT NULL,
    district VARCHAR(50) NOT NULL COMMENT '行政区',
    business_circle VARCHAR(100) NOT NULL COMMENT '商圈',
    address TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    area DECIMAL(5, 2) COMMENT '面积m²',
    bedroom_count INT DEFAULT 1,
    bed_count INT DEFAULT 1,
    max_guests INT DEFAULT 2,
    amenities JSON COMMENT '设施标签JSON',
    rating DECIMAL(3, 2) DEFAULT 5.00,
    review_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_business_circle (business_circle),
    INDEX idx_district (district)
);

-- 价格历史表
CREATE TABLE price_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    listing_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    listed_price DECIMAL(10, 2) NOT NULL COMMENT '挂牌价',
    estimated_real_price DECIMAL(10, 2) COMMENT '估算真实成交价',
    estimated_orders INT COMMENT '估算订单量',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_listing_date (listing_id, date),
    FOREIGN KEY (listing_id) REFERENCES listings(listing_id)
);

-- 预测结果表
CREATE TABLE price_predictions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    listing_id VARCHAR(50) NOT NULL,
    predict_date DATE NOT NULL COMMENT '预测日期',
    predicted_price DECIMAL(10, 2) NOT NULL COMMENT '预测价格',
    price_lower DECIMAL(10, 2) COMMENT '价格区间下限',
    price_upper DECIMAL(10, 2) COMMENT '价格区间上限',
    confidence DECIMAL(3, 2) COMMENT '置信度',
    model_version VARCHAR(20) COMMENT '模型版本',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_listing_predict_date (listing_id, predict_date)
);

-- 商圈统计表
CREATE TABLE business_circle_stats (
    id INT PRIMARY KEY AUTO_INCREMENT,
    business_circle VARCHAR(100) NOT NULL,
    stat_date DATE NOT NULL,
    avg_price DECIMAL(10, 2) COMMENT '平均价格',
    median_price DECIMAL(10, 2) COMMENT '价格中位数',
    min_price DECIMAL(10, 2),
    max_price DECIMAL(10, 2),
    listing_count INT COMMENT '房源数量',
    new_reviews INT COMMENT '新增评论数',
    estimated_orders INT COMMENT '估算订单量',
    occupancy_rate DECIMAL(5, 2) COMMENT '估算入住率',
    heat_score DECIMAL(5, 2) COMMENT '热度评分',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_circle_date (business_circle, stat_date)
);
```

### 6.2 Hive数仓分层设计

```
ODS层（原始数据层）
├── ods_tujia_listing_raw       -- 房源原始数据
├── ods_tujia_price_raw         -- 价格原始数据
├── ods_tujia_review_raw        -- 评论原始数据

DWD层（明细数据层）
├── dwd_listing_detail          -- 房源明细表
├── dwd_price_detail            -- 价格明细表（含代理变量计算）
├── dwd_review_detail           -- 评论明细表

DWS层（汇总数据层）
├── dws_business_circle_daily   -- 商圈日汇总
├── dws_listing_monthly         -- 房源月汇总
├── dws_price_trend             -- 价格趋势汇总

ADS层（应用数据层）
├── ads_price_prediction_input  -- 预测模型输入特征
├── ads_recommendation_matrix   -- 推荐算法矩阵
├── ads_dashboard_metrics       -- 大屏展示指标
```

---

## 7. 接口设计

### 7.1 RESTful API规范

#### 获取商圈列表
```
GET /api/v1/business-circles
Response:
{
    "code": 200,
    "data": [
        {
            "id": "jianghan",
            "name": "江汉路网红区",
            "district": "江汉区",
            "listing_count": 1250,
            "avg_price": 268.5
        }
    ]
}
```

#### 获取商圈分析数据
```
GET /api/v1/business-circles/{id}/analytics
Params:
- start_date: 开始日期 (YYYY-MM-DD)
- end_date: 结束日期 (YYYY-MM-DD)

Response:
{
    "code": 200,
    "data": {
        "price_stats": {
            "median": 280.0,
            "avg": 295.5,
            "trend": "up",
            "change_percent": 12.5
        },
        "occupancy_rate": 0.78,
        "hot_facilities": [
            {"name": "巨幕投影", "premium": 35.5},
            {"name": "智能锁", "premium": 15.0}
        ],
        "heat_map": [...]
    }
}
```

#### 价格预测
```
POST /api/v1/predictions/price
Request:
{
    "listing_id": "tj_123456",
    "prediction_days": 14
}

Response:
{
    "code": 200,
    "data": {
        "listing_id": "tj_123456",
        "predictions": [
            {
                "date": "2026-01-15",
                "predicted_price": 298.0,
                "price_range": [268, 328],
                "confidence": 0.85,
                "suggestion": "建议调价",
                "reason": "周末效应+节假日临近"
            }
        ]
    }
}
```

#### 房源推荐
```
GET /api/v1/recommendations
Params:
- user_id: 用户ID
- business_circle: 商圈ID (可选)
- limit: 返回数量 (默认10)

Response:
{
    "code": 200,
    "data": {
        "recommendations": [
            {
                "listing_id": "tj_789012",
                "title": "江汉路地铁站旁温馨公寓",
                "price": 268.0,
                "rating": 4.9,
                "match_score": 0.92,
                "reason": "相似用户推荐"
            }
        ]
    }
}
```

---

## 8. 界面原型

### 8.1 页面结构

```
├── 登录/注册页 (/login)
├── 布局框架
│   ├── 顶部导航栏
│   ├── 侧边菜单栏
│   └── 内容区域
├── 核心页面
│   ├── 数据大屏 Dashboard (/dashboard)
│   │   ├── KPI指标卡片
│   │   ├── 价格趋势图
│   │   └── 商圈对比图表
│   ├── 商圈分析 (/business-analysis)
│   │   ├── 商圈选择器
│   │   ├── 价格热力地图
│   │   ├── 供需分析图表
│   │   └── 设施溢价分析
│   ├── 价格预测 (/price-prediction)
│   │   ├── 房源搜索
│   │   ├── 预测结果日历
│   │   └── 定价建议详情
│   ├── 房源推荐 (/recommendations)
│   │   ├── 个性化推荐列表
│   │   └── 热门房源排行
│   └── 个人中心 (/profile)
│       ├── 我的房源
│       ├── 收藏记录
│       └── 系统设置
```

### 8.2 关键界面描述

#### Dashboard数据大屏
- **顶部KPI区域**：4个核心指标卡片（今日均价、入住率、竞品数量、预测准确率）
- **左侧图表**：价格走势折线图（支持时间区间选择）
- **右侧图表**：商圈对比柱状图
- **底部表格**：热门商圈排行榜

#### 商圈分析页
- **地图区域**：ECharts热力图展示价格分布
- **筛选器**：行政区、商圈、时间范围
- **分析卡片**：
  - 供需饱和度仪表盘
  - 设施溢价TOP10排行
  - 节假日效应系数对比

#### 价格预测页
- **搜索区**：房源ID/关键词搜索
- **结果区**：
  - 日历视图：每天显示建议价格区间
  - 特殊标记：节假日、特殊事件高亮
  - 建议卡片：调价建议与理由说明

---

## 9. 项目里程碑

| 阶段 | 时间 | 交付物 | 验收标准 |
|-----|------|--------|---------|
| 需求分析 | 第1-2周 | PRD文档、原型图 | 需求评审通过 |
| 数据采集 | 第3-4周 | 爬虫系统、原始数据 | 采集成功率≥90% |
| 数据处理 | 第5-6周 | Hive数仓、清洗流程 | 数据质量达标 |
| 模型开发 | 第7-9周 | XGBoost模型、推荐算法 | MAE降低28.6% |
| 系统开发 | 第10-12周 | 前后端系统、API接口 | 功能覆盖率100% |
| 集成测试 | 第13-14周 | 测试报告、Bug修复 | 缺陷率<5% |
| 上线部署 | 第15-16周 | 生产环境、运维文档 | 系统稳定运行 |

---

## 10. 风险评估

| 风险项 | 影响程度 | 应对措施 |
|-------|---------|---------|
| 爬虫被封禁 | 高 | 动态IP池、请求频率控制、多账号轮换 |
| 数据质量不达标 | 高 | 数据清洗规则、质量监控、人工校验 |
| 模型预测精度不足 | 中 | 特征工程优化、分层建模、A/B测试 |
| 系统性能瓶颈 | 中 | 缓存优化、数据库索引、Hive调优 |
| 法规合规风险 | 高 | 数据脱敏、合规审查、用户协议 |

---

## 11. 附录

### 11.1 商圈列表（武汉）

| 商圈ID | 商圈名称 | 行政区 | 类型 | 特征描述 |
|-------|---------|--------|------|---------|
| jianghan | 江汉路网红区 | 江汉区 | 商业旅游 | 步行街、网红打卡点 |
| guanggu | 光谷高新差旅区 | 洪山区 | 高校商务 | 高校集中、商务出行 |
| tanhualin | 昙华林文创区 | 武昌区 | 文化旅游 | 文艺气息、文创产业 |
| jiedaokou | 街道口商圈 | 洪山区 | 高校刚需 | 高校周边、学生为主 |
| hankou | 汉口江滩区 | 江岸区 | 休闲旅游 | 江滩景观、休闲度假 |

### 11.2 设施标签列表

```json
{
  "basic": ["wifi", "air_conditioner", "heating", "tv"],
  "bathroom": ["hot_water", "bathtub", "hair_dryer", "toiletries"],
  "kitchen": ["kitchen", "fridge", "cooker", "kitchenware"],
  "entertainment": ["projector", "game_console", "books"],
  "safety": ["smart_lock", "fire_extinguisher", "smoke_detector"],
  "service": ["luggage_storage", "express_checkin", "cleaning"]
}
```

### 11.3 节假日配置

| 节日 | 日期范围 | 折扣调整系数 | 价格涨幅预期 |
|-----|---------|-------------|-------------|
| 春节 | 农历除夕-初六 | -0.05 | +80% |
| 五一 | 5月1日-5日 | -0.08 | +60% |
| 国庆 | 10月1日-7日 | -0.10 | +70% |
| 开学季 | 9月1日-15日 | -0.03 | +30% |

---

**文档版本历史**

| 版本 | 日期 | 作者 | 变更内容 |
|-----|------|------|---------|
| v1.0 | 2025-12 | 龚婷 | 初始版本 |

---

*本文档由中原工学院人工智能学院数据科学与大数据技术专业编制*
