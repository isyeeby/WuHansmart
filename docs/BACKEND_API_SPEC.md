# 民宿价格数据分析系统 - 后端系统分析文档

**版本**: v2.0  
**更新日期**: 2026-03-19  
**目标读者**: 前端开发团队  

---

## 一、系统概述

### 1.1 项目背景

本系统是一个面向**民宿经营者**和**投资者**的价格数据分析平台，基于武汉途家网真实房源数据，提供智能定价、商圈分析、竞品对比、投资建议等核心功能。

### 1.2 目标用户

| 用户角色 | 核心需求 | 主要使用场景 |
|---------|---------|-------------|
| 民宿经营者 | 智能定价、竞品监测、设施优化 | 日常运营决策、调价策略 |
| 投资者 | 商圈分析、投资回报预估 | 选址决策、投资评估 |

### 1.3 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端展示层 (React)                         │
├─────────────────────────────────────────────────────────────┤
│                    后端API层 (FastAPI)                        │
│  端口: 8000  |  文档: /docs  |  基础路径: /api                │
├─────────────────────────────────────────────────────────────┤
│                    数据层                                     │
│  MySQL (业务数据)  |  Hive (数据仓库)  |  XGBoost (预测模型)   │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 数据概览

| 数据项 | 数量 |
|-------|------|
| 房源总数 | 2,307 条 |
| 商圈数量 | 11 个行政区 / 1,924 个商圈组合 |
| 平均价格 | ¥200.21 |
| 平均评分 | 4.85 分 |

---

## 二、功能模块总览

### 2.1 模块架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        民宿价格数据分析系统                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Dashboard  │  │  商圈分析    │  │       价格预测           │ │
│  │  数据大屏   │  │  Analysis   │  │      Prediction         │ │
│  │             │  │             │  │                         │ │
│  │ • 核心指标  │  │ • 商圈列表  │  │  • 价格预测              │ │
│  │ • 价格趋势  │  │ • 设施溢价  │  │  • 竞品分析              │ │
│  │ • 商圈对比  │  │ • 价格分布  │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      房源中心                                ││
│  │                   Listing Center                            ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ ││
│  │  │  房源列表    │  │  房源详情    │  │     个性推荐         │ ││
│  │  │  Listings   │  │   Detail    │  │   Recommendation    │ ││
│  │  │             │  │             │  │                     │ ││
│  │  │ • 筛选搜索   │  │ • 图片画廊   │  │ • 相似房源推荐       │ ││
│  │  │ • 排序功能   │  │ • 标签展示   │  │ • 热门房源排行       │ ││
│  │  │ • 分页加载   │  │ • 评分口碑   │  │ • 收藏功能          │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      我的房源                                ││
│  │                   My Listings                               ││
│  │  • 上传房源  • 竞品对比  • 定价建议  • 优化建议              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      用户中心                                ││
│  │                   User Center                               ││
│  │  • 用户注册/登录  • 收藏管理  • 浏览历史  • 个人设置         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块清单

| 模块名称 | 路由前缀 | 功能描述 |
|---------|---------|---------|
| 认证模块 | `/api/auth` | 用户注册、登录、Token管理 |
| 用户模块 | `/api/user` | 用户信息、偏好设置 |
| 房源列表 | `/api/listings` | 房源搜索、筛选、分页 |
| Dashboard | `/api/dashboard` | 核心指标、趋势图表 |
| 商圈分析 | `/api/analysis` | 商圈统计、设施溢价 |
| 我的房源 | `/api/my-listings` | 房源上传、竞品对比、定价建议 |
| 价格预测 | `/api/predict` | 价格预测、竞品分析 |
| 标签库 | `/api/tags` | 标签分类、热门标签 |
| 推荐系统 | `/api/recommend` | 个性化推荐页（条件/协同/兜底，见下文） |
| 收藏功能 | `/api/favorites` | 收藏管理 |
| 首页 | `/api/home` | 统计、热门商圈、**推荐条**（`/recommendations`）、热力等 |

---

## 三、接口详细设计

### 3.1 认证模块 (Auth)

#### 3.1.1 用户注册

**接口**: `POST /api/auth/register`

**功能描述**: 新用户注册账号

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| username | string | 是 | 用户名 | 3-50字符 |
| password | string | 是 | 密码 | 至少6位 |
| phone | string | 否 | 手机号 | 可选 |
| full_name | string | 否 | 姓名 | 可选 |

**响应示例**:
```json
{
  "id": 1,
  "username": "test_user",
  "phone": "13800138000",
  "full_name": "测试用户",
  "is_active": true,
  "created_at": "2026-03-19T10:00:00"
}
```

---

#### 3.1.2 用户登录

**接口**: `POST /api/auth/login`

**功能描述**: 用户登录获取Token

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| username | string | 是 | 用户名 | - |
| password | string | 是 | 密码 | - |

**响应示例**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### 3.2 房源列表模块 (Listings)

#### 3.2.1 获取房源列表

**接口**: `GET /api/listings`

**功能描述**: 分页获取房源列表，支持多条件筛选和排序

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| district | string | 否 | 行政区 | 如：洪山区、江岸区 |
| business_circle | string | 否 | 商圈 | 商圈名称 |
| min_price | float | 否 | 最低价格 | 价格下限 |
| max_price | float | 否 | 最高价格 | 价格上限 |
| tags | string | 否 | 标签筛选 | 逗号分隔，如：近地铁,可做饭 |
| bedroom_count | int | 否 | 卧室数 | 卧室数量筛选 |
| sort_by | string | 否 | 排序方式 | 可选值见下表 |
| page | int | 否 | 页码 | 默认1 |
| size | int | 否 | 每页数量 | 默认20，最大100 |

**排序方式 (sort_by)**:

| 值 | 说明 |
|---|------|
| price_asc | 价格从低到高 |
| price_desc | 价格从高到低 |
| rating | 评分从高到低 |
| favorite_count | 收藏数从高到低（默认） |

**响应示例**:
```json
{
  "total": 2307,
  "page": 1,
  "size": 20,
  "items": [
    {
      "unit_id": "331196",
      "title": "新店！武汉站，欢乐谷，玛雅海滩，阳光投影大床房",
      "district": "洪山区",
      "trade_area": "光谷广场",
      "final_price": 102.00,
      "original_price": 158.00,
      "discount_rate": 0.3544,
      "rating": 4.9,
      "favorite_count": 7000,
      "pic_count": 13,
      "cover_image": "https://pic.tujia.com/...",
      "house_tags": "[{\"text\":\"近地铁\"}, {\"text\":\"可做饭\"}]",
      "comment_brief": "房东热情好客",
      "bedroom_count": 1,
      "bed_count": 1,
      "longitude": 114.312685,
      "latitude": 30.620843,
      "nearest_hospital_km": 2.415,
      "nearest_hospital_name": "武汉大学中南医院"
    }
  ]
}
```

**字段映射表**:

| 字段名 | 中文名称 | 类型 | 说明 |
|-------|---------|------|------|
| unit_id | 房源ID | string | 唯一标识 |
| title | 房源标题 | string | 房源名称 |
| district | 行政区 | string | 所属行政区 |
| trade_area | 商圈 | string | 所属商圈 |
| final_price | 最终价格 | float | 当前售价（元） |
| original_price | 原价 | float | 原始价格（元） |
| discount_rate | 折扣率 | float | 折扣比例（0-1） |
| rating | 评分 | float | 用户评分（0-5） |
| favorite_count | 收藏数 | int | 被收藏次数 |
| pic_count | 图片数量 | int | 房源图片总数 |
| cover_image | 封面图 | string | 封面图片URL |
| house_tags | 房源标签 | string | JSON格式标签数组 |
| comment_brief | 评论摘要 | string | 优质评论摘要 |
| bedroom_count | 卧室数 | int | 卧室数量 |
| bed_count | 床位数 | int | 床位数量 |
| longitude | 经度 | float | 地理位置经度 |
| latitude | 纬度 | float | 地理位置纬度 |
| nearest_hospital_km | 最近医院距离 | float \| null | 至 POI 医院直线距离（km），离线流水线写入；未跑流水线或无坐标时为 `null` |
| nearest_hospital_name | 最近医院名称 | string \| null | 与 `nearest_hospital_km` 对应的 POI 名称（来自离线医院点位表）；未回写时为 `null` |

---

#### 3.2.2 获取房源详情

**接口**: `GET /api/listings/{unit_id}`

**功能描述**: 获取单个房源的详细信息

**路径参数**:

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| unit_id | string | 是 | 房源ID |

**响应示例**: 同列表接口中的单条数据结构

---

#### 3.2.3 获取房源图片画廊

**接口**: `GET /api/listings/{unit_id}/gallery`

**功能描述**: 获取房源图片，按房间类型分类

**响应示例**:
```json
{
  "unit_id": "331196",
  "title": "房源标题",
  "total_pics": 18,
  "categories": {
    "客厅": ["https://pic.tujia.com/.../1.jpg", "https://pic.tujia.com/.../2.jpg"],
    "卧室": ["https://pic.tujia.com/.../3.jpg"],
    "厨房": ["https://pic.tujia.com/.../4.jpg"],
    "卫生间": ["https://pic.tujia.com/.../5.jpg"],
    "阳台": ["https://pic.tujia.com/.../6.jpg"],
    "外景": ["https://pic.tujia.com/.../7.jpg"],
    "休闲": [],
    "其他": []
  }
}
```

**图片分类说明**:

| 分类 | 说明 |
|-----|------|
| 客厅 | 客厅相关照片 |
| 卧室 | 卧室相关照片 |
| 厨房 | 厨房相关照片 |
| 卫生间 | 卫生间相关照片 |
| 阳台 | 阳台/露台照片 |
| 外景 | 房屋外观/周边环境 |
| 休闲 | 休闲设施照片 |
| 其他 | 其他类型照片 |

---

#### 3.2.4 获取相似房源

**接口**: `GET /api/listings/{unit_id}/similar`

**功能描述**: 获取与指定房源相似的推荐房源

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| limit | int | 否 | 数量限制 | 默认10，最大20 |

**响应示例**:
```json
[
  {
    "unit_id": "76378129",
    "title": "相似房源标题",
    "district": "洪山区",
    "final_price": 298.00,
    "rating": 4.8,
    "similarity_score": 85.5
  }
]
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| similarity_score | 相似度分数 | 0-100，越高越相似 |

---

#### 3.2.5 获取热门房源排行

**接口**: `GET /api/listings/hot/ranking`

**功能描述**: 获取热门房源排行榜（按收藏数排序）

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| district | string | 否 | 行政区 | 按行政区筛选 |
| limit | int | 否 | 数量限制 | 默认10，最大50 |

**响应示例**: 返回房源列表数组

---

### 3.3 Dashboard模块

#### 3.3.1 获取核心指标汇总

**接口**: `GET /api/dashboard/summary`

**功能描述**: 获取Dashboard页面核心指标数据

**响应示例**:
```json
{
  "total_listings": 2307,
  "avg_price": 200.21,
  "avg_rating": 4.85,
  "district_count": 11,
  "price_trend": 5.2
}
```

**字段映射表**:

| 字段名 | 中文名称 | 类型 | 说明 |
|-------|---------|------|------|
| total_listings | 房源总数 | int | 平台房源总量 |
| avg_price | 平均价格 | float | 全平台均价（元） |
| avg_rating | 平均评分 | float | 全平台平均评分 |
| district_count | 商圈数量 | int | 行政区数量 |
| price_trend | 价格环比 | float | 相比上期变化百分比 |

---

#### 3.3.2 获取商圈对比数据

**接口**: `GET /api/dashboard/district-comparison`

**功能描述**: 获取各商圈对比数据，用于横向对比图表

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| limit | int | 否 | 数量限制 | 默认10，最大20 |

**响应示例**:
```json
{
  "items": [
    {
      "district": "洪山区",
      "trade_area": "光谷广场",
      "avg_price": 256.50,
      "listing_count": 128,
      "avg_rating": 4.82
    }
  ]
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| district | 行政区 | 所属行政区 |
| trade_area | 商圈 | 商圈名称 |
| avg_price | 平均价格 | 该商圈均价 |
| listing_count | 房源数量 | 该商圈房源数 |
| avg_rating | 平均评分 | 该商圈平均评分 |

---

### 3.4 商圈分析模块 (Analysis)

#### 3.4.1 获取商圈列表

**接口**: `GET /api/analysis/districts`

**功能描述**: 获取商圈列表及统计数据

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| district | string | 否 | 行政区 | 按行政区筛选 |

**响应示例**:
```json
[
  {
    "district": "洪山区",
    "trade_area": "光谷广场",
    "listing_count": 128,
    "avg_price": 256.50,
    "avg_rating": 4.82,
    "avg_favorite_count": 456.3,
    "avg_comment_count": 0,
    "avg_bedroom_count": 1.5,
    "min_price": 88.00,
    "max_price": 688.00
  }
]
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| listing_count | 房源数量 | 该商圈房源总数 |
| avg_price | 平均价格 | 该商圈均价 |
| avg_rating | 平均评分 | 该商圈平均评分 |
| avg_favorite_count | 平均收藏数 | 该商圈平均被收藏次数 |
| avg_bedroom_count | 平均卧室数 | 该商圈平均卧室数量 |
| min_price | 最低价格 | 该商圈最低价格 |
| max_price | 最高价格 | 该商圈最高价格 |

---

#### 3.4.2 获取设施溢价分析

**接口**: `GET /api/analysis/facility-premium`

**功能描述**: 分析各设施对价格的影响程度

**响应示例**:
```json
{
  "facilities": [
    {
      "facility_name": "投影",
      "avg_price_with": 328.50,
      "avg_price_without": 245.20,
      "premium_amount": 83.30,
      "premium_percent": 33.9,
      "listing_count": 456
    }
  ]
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| facility_name | 设施名称 | 设施名称 |
| avg_price_with | 有此设施均价 | 有该设施的房源均价 |
| avg_price_without | 无此设施均价 | 无该设施的房源均价 |
| premium_amount | 溢价金额 | 溢价的绝对金额 |
| premium_percent | 溢价比例 | 溢价百分比 |
| listing_count | 房源数量 | 有此设施的房源数 |

---

### 3.5 我的房源模块 (My Listings)

#### 3.5.1 创建我的房源

**接口**: `POST /api/my-listings`

**功能描述**: 经营者上传自己的房源信息

**请求头**:
```
Authorization: Bearer {token}
```

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| title | string | 是 | 房源标题 | 1-255字符 |
| district | string | 是 | 行政区 | 所属行政区 |
| business_circle | string | 否 | 商圈 | 所属商圈 |
| address | string | 否 | 详细地址 | 具体地址 |
| longitude | float | 否 | 经度 | 地理位置经度 |
| latitude | float | 否 | 纬度 | 地理位置纬度 |
| bedroom_count | int | 是 | 卧室数 | 默认1 |
| bed_count | int | 是 | 床位数 | 默认1 |
| bathroom_count | int | 是 | 卫生间数 | 默认1 |
| max_guests | int | 是 | 可住人数 | 默认2 |
| area | float | 否 | 面积 | 房源面积（㎡） |
| current_price | float | 是 | 当前定价 | 当前定价（元） |
| style_tags | array | 否 | 风格标签 | 如：["欧美风", "INS风"] |
| facility_tags | array | 否 | 设施标签 | 如：["投影", "洗衣机"] |
| location_tags | array | 否 | 位置标签 | 如：["近地铁", "近景点"] |
| crowd_tags | array | 否 | 人群标签 | 如：["适合团建", "亲子"] |

**请求示例**:
```json
{
  "title": "温馨两居室，近地铁",
  "district": "洪山区",
  "business_circle": "光谷广场",
  "address": "光谷广场附近",
  "bedroom_count": 2,
  "bed_count": 2,
  "bathroom_count": 1,
  "max_guests": 4,
  "area": 85.5,
  "current_price": 258.00,
  "facility_tags": ["投影", "洗衣机", "空调", "WiFi"]
}
```

**响应示例**:
```json
{
  "id": 1,
  "user_id": 1,
  "title": "温馨两居室，近地铁",
  "district": "洪山区",
  "current_price": 258.00,
  "status": "active",
  "created_at": "2026-03-19T10:00:00"
}
```

---

#### 3.5.2 获取我的房源列表

**接口**: `GET /api/my-listings`

**功能描述**: 获取当前用户上传的所有房源

**请求头**:
```
Authorization: Bearer {token}
```

**响应示例**: 返回房源列表数组

---

#### 3.5.3 获取竞品对比分析

**接口**: `GET /api/my-listings/{listing_id}/competitors`

**功能描述**: 分析我的房源与同商圈竞品的对比

**请求头**:
```
Authorization: Bearer {token}
```

**路径参数**:

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| listing_id | int | 是 | 我的房源ID |

**响应示例**:
```json
{
  "my_listing": {
    "id": 1,
    "title": "我的房源",
    "current_price": 258.00,
    "district": "洪山区"
  },
  "market_position": {
    "avg_price": 280.50,
    "my_price_rank": 15,
    "price_percentile": 35.2
  },
  "competitors": [
    {
      "unit_id": "76378129",
      "title": "竞品房源标题",
      "final_price": 298.00,
      "rating": 4.9,
      "favorite_count": 521,
      "similarity_score": 85.0
    }
  ],
  "analysis": {
    "advantages": ["价格具有竞争力", "位置优越"],
    "disadvantages": ["缺少热门设施：投影"],
    "suggestions": ["建议添加设施：投影", "建议价格调整至268元"]
  }
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| market_position | 市场定位 | 我在市场中的位置 |
| avg_price | 市场均价 | 竞品平均价格 |
| my_price_rank | 价格排名 | 我的价格在竞品中的排名 |
| price_percentile | 价格百分位 | 我的价格所处的百分位 |
| competitors | 竞品列表 | 相似竞品房源 |
| analysis | 分析结论 | 优劣势分析 |

---

### 3.5.4 获取定价建议

**接口**: `POST /api/my-listings/{listing_id}/price-suggestion`

**功能描述**: 基于XGBoost模型预测最优定价，给出调价建议

**请求头**:
```
Authorization: Bearer {token}
```

**路径参数**:

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| listing_id | int | 是 | 我的房源ID |

**响应示例**:
```json
{
  "current_price": 258.00,
  "suggested_price": 285.00,
  "price_difference": 27.00,
  "difference_percent": 10.5,
  "suggestion": "建议涨价",
  "reasoning": [
    "您的房源设施配置较好",
    "同商圈同类房源均价为285元",
    "近地铁房源溢价约15%"
  ],
  "confidence": 0.85
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| current_price | 当前价格 | 您当前的定价 |
| suggested_price | 建议价格 | 模型预测的最优价格 |
| price_difference | 价格差异 | 建议价格与当前价格差值 |
| difference_percent | 差异百分比 | 价格差异百分比 |
| suggestion | 建议 | 涨价/降价/保持 |
| reasoning | 建议理由 | 调价的具体原因列表 |
| confidence | 置信度 | 预测置信度（0-1） |

---

### 3.6 价格预测模块 (Prediction)

#### 3.6.1 价格预测

**接口**: `POST /api/predict/price`

**功能描述**: 输入房源特征，预测合理价格区间

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| district | string | 是 | 行政区 | 所属行政区 |
| bedroom_count | int | 是 | 卧室数 | 卧室数量 |
| bed_count | int | 是 | 床位数 | 床位数量 |
| bathroom_count | int | 否 | 卫生间数 | 默认1 |
| area | float | 否 | 面积 | 房源面积（㎡） |
| has_metro | boolean | 否 | 近地铁 | 是否近地铁 |
| has_kitchen | boolean | 否 | 可做饭 | 是否有厨房 |
| has_projector | boolean | 否 | 有投影 | 是否有投影 |
| has_washer | boolean | 否 | 有洗衣机 | 是否有洗衣机 |
| has_smart_lock | boolean | 否 | 智能门锁 | 是否有智能门锁 |
| has_air_conditioner | boolean | 否 | 空调 | 是否有空调 |
| has_bathtub | boolean | 否 | 浴缸 | 是否有浴缸 |
| has_parking | boolean | 否 | 停车位 | 是否有停车位 |
| has_balcony | boolean | 否 | 阳台 | 是否有阳台 |

**请求示例**:
```json
{
  "district": "洪山区",
  "bedroom_count": 2,
  "bed_count": 2,
  "bathroom_count": 1,
  "area": 85.5,
  "has_metro": true,
  "has_kitchen": true,
  "has_projector": true,
  "has_washer": true,
  "has_air_conditioner": true
}
```

**响应示例**:
```json
{
  "predicted_price": 278.50,
  "price_range": {
    "lower": 245.00,
    "upper": 312.00
  },
  "confidence": 0.82,
  "factors": [
    {"feature": "行政区", "impact": "+15%", "detail": "洪山区均价较高"},
    {"feature": "近地铁", "impact": "+12%", "detail": "交通便利溢价"},
    {"feature": "投影", "impact": "+8%", "detail": "热门设施溢价"}
  ],
  "district_avg_price": 256.30
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| predicted_price | 预测价格 | 模型预测价格 |
| price_range | 价格区间 | 建议价格范围 |
| price_range.lower | 下限 | 建议价格下限 |
| price_range.upper | 上限 | 建议价格上限 |
| confidence | 置信度 | 预测置信度 |
| factors | 影响因素 | 影响价格的关键因素 |
| district_avg_price | 商圈均价 | 该商圈平均价格 |

---

#### 3.6.2 获取竞品分析

**接口**: `GET /api/predict/competitors/{unit_id}`

**功能描述**: 获取指定房源的同商圈竞品分析

**路径参数**:

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| unit_id | string | 是 | 房源ID |

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| limit | int | 否 | 数量限制 | 默认10，最大20 |

**响应示例**:
```json
{
  "target_listing": {
    "unit_id": "76378129",
    "title": "目标房源",
    "price": 298.00,
    "rating": 4.9
  },
  "competitors": [
    {
      "unit_id": "63045403",
      "title": "竞品房源标题",
      "price": 296.00,
      "rating": 5.0,
      "favorite_count": 764,
      "house_tags": ["近地铁", "可做饭", "有洗衣机"],
      "similarity_score": 88.5,
      "price_diff": -2.00
    }
  ],
  "market_analysis": {
    "avg_price": 285.50,
    "min_price": 198.00,
    "max_price": 468.00,
    "avg_rating": 4.85,
    "total_competitors": 128
  },
  "position": {
    "price_rank": 15,
    "price_percentile": 65.2,
    "rating_rank": 8
  }
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| target_listing | 目标房源 | 当前分析的房源 |
| competitors | 竞品列表 | 相似竞品房源 |
| similarity_score | 相似度 | 与目标房源相似度（0-100） |
| price_diff | 价格差异 | 与目标房源价格差 |
| market_analysis | 市场分析 | 市场整体情况 |
| position | 市场定位 | 目标房源在市场中的位置 |
| price_rank | 价格排名 | 价格在竞品中的排名 |
| price_percentile | 价格百分位 | 价格所处百分位 |

---

### 3.7 标签库模块 (Tags)

#### 3.7.1 获取标签分类

**接口**: `GET /api/tags/categories`

**功能描述**: 获取所有标签分类及标签列表，用于房源上传时选择标签

**响应示例**:
```json
[
  {
    "category": "style",
    "category_name": "风格标签",
    "tags": ["欧美风", "网红INS风", "现代风", "日式风", "中式风", "地中海风"]
  },
  {
    "category": "facility",
    "category_name": "设施标签",
    "tags": ["投影", "洗衣机", "空调", "智能门锁", "浴缸", "冰箱", "吹风机", "全天热水", "有麻将机"]
  },
  {
    "category": "location",
    "category_name": "位置标签",
    "tags": ["近地铁", "近景点", "付费停车位", "超市/菜场", "近火车站"]
  },
  {
    "category": "service",
    "category_name": "服务标签",
    "tags": ["管家服务", "立即确认", "团建会议", "大客厅"]
  }
]
```

**标签分类说明**:

| 分类 | 英文Key | 说明 |
|-----|--------|------|
| style_tags | style | 房源装修风格 |
| facility_tags | facility | 房源设施配置 |
| location_tags | location | 房源位置特点 |
| service_tags | service | 房源服务特色 |

---

#### 3.7.2 获取热门标签

**接口**: `GET /api/tags/popular`

**功能描述**: 获取热门标签排行，可按商圈筛选

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| district | string | 否 | 行政区 | 按行政区筛选 |
| limit | int | 否 | 数量限制 | 默认20，最大50 |

**响应示例**:
```json
{
  "district": "洪山区",
  "tags": [
    {
      "tag_name": "近地铁",
      "usage_count": 456,
      "avg_price": 285.50,
      "premium_percent": 15.2,
      "percent": 35.2
    },
    {
      "tag_name": "可做饭",
      "usage_count": 389,
      "avg_price": 268.00,
      "premium_percent": 8.5,
      "percent": 30.1
    }
  ]
}
```

**字段映射表**:

| 字段名 | 中文名称 | 说明 |
|-------|---------|------|
| tag_name | 标签名称 | 标签文本 |
| usage_count | 使用次数 | 该标签被使用的房源数 |
| avg_price | 平均价格 | 有此标签的房源均价 |
| premium_percent | 溢价比例 | 相比无此标签的溢价百分比 |
| percent | 占比 | 该标签在筛选范围内的占比 |

---

### 3.8 推荐模块 (Recommend)

**首页 vs 推荐页**：首页「智能推荐」区块调用 **`GET /api/home/recommendations`**；「个性化推荐」页调用 **`GET /api/recommend`**。前者为 SQL 候选 + 场景/设施重排；后者为完整推荐分支（见 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](RECOMMENDATION_ONLINE_BEHAVIOR.md)）。详情页「相似房源」为 **`GET /api/listings/{unit_id}/similar`**（规则排序，非本模块矩阵接口）。

#### 3.8.1 首页推荐条

**接口**: `GET /api/home/recommendations`

**查询参数**:

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| limit | int | 否 | 默认 6，范围 1–12 |

**行为摘要**: 从 MySQL `listings` 查询；登录用户可应用问卷中的行政区、价格区间过滤；在候选集上按评分/收藏初筛后，用与 `RecommendationService._scene_purpose_bonus` 一致的场景加分及设施标签命中加分重排。无数据时可尝试 Hive，仍无则返回内置示例（见 `home.py`）。

**响应**: `{ "listings": [ ... ] }`，每项含 `unit_id`、`title`、`district`、`price`、`rating`、`tags`、`image_url`、`match_score`。**`match_score` 为 0–100 的整数**（与 `GET /api/recommend` 返回项中常见的 0–1 刻度 `match_score` 不同，前端勿混用换算）。

#### 3.8.2 获取个性化推荐

**接口**: `GET /api/recommend`

**功能描述**: 基于用户偏好获取个性化推荐房源。

**路由说明（与论文叙述区分）**：本接口在存在 `travel_purpose` 或设施参数时走 **条件匹配推荐**；仅当二者在合并登录补全后仍为空时，才走 **收藏/浏览 + 相似度矩阵** 与热门兜底。详见 [`RECOMMENDATION_ONLINE_BEHAVIOR.md`](RECOMMENDATION_ONLINE_BEHAVIOR.md)。

**登录用户默认偏好（与首登问卷 / 个人信息一致）**：请求头携带有效 JWT 时，若下列查询参数**未传**，则用当前用户在库中的偏好**补全**，再决定走「条件推荐」或协同过滤：

- `district` ← `preferred_district`
- `price_min` / `price_max` ← `preferred_price_min` / `preferred_price_max`
- `travel_purpose` ← `travel_purpose`（中文会转为与 `scene_scores` 一致的英文 key，见 `app/core/recommend_travel.py`）
- `facilities`（整条未传时）← `required_facilities`（中文设施名映射为 `subway`/`projector`/`cooking` 等内部键）

补全后若存在有效的 `travel_purpose` 或设施列表，则进入**条件匹配推荐**（读库：`scene_scores` 目的概率加分；`travel_purpose=medical` 时另加 **`nearest_hospital_km` 距离加分**，字段已回写时）；否则仍为协同过滤 / 热门兜底。显式传入的查询参数始终优先于库内偏好。

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| user_id | string | 否 | 用户ID | 登录用户自动获取 |
| district | string | 否 | 行政区 | 偏好行政区 |
| price_min | float | 否 | 最低价格 | 价格偏好下限 |
| price_max | float | 否 | 最高价格 | 价格偏好上限 |
| travel_purpose | string | 否 | 出行目的 | 英文 key；不传时登录用户可用库内中文偏好自动转换 |
| facilities | string | 否 | 设施 | 逗号分隔英文键；不传时登录用户可用 `required_facilities` 自动映射 |
| capacity | int | 否 | 入住人数 | 需容纳人数 |
| top_k | int | 否 | 返回数量 | 默认10，最大50 |

**响应示例**:
```json
{
  "recommendations": [
    {
      "id": "76378129",
      "title": "推荐房源标题",
      "district": "洪山区",
      "price": 298.00,
      "rating": 4.9,
      "match_score": 0.92,
      "reason": "符合您的价格偏好和位置偏好",
      "nearest_hospital_km": 1.8,
      "nearest_hospital_name": "华中科技大学同济医学院附属协和医院（主院区）"
    }
  ]
}
```

`nearest_hospital_km` / `nearest_hospital_name`：可选，来自 `listings` 表；便于「医疗陪护」展示「距某医院约 x km」。条件匹配下 **`travel_purpose=medical`** 时，服务端还会按距离对排序分追加加分（详见 [`LISTING_SCENE_TFIDF_PIPELINE.md`](LISTING_SCENE_TFIDF_PIPELINE.md)）。

---

### 3.9 收藏模块 (Favorites)

#### 3.9.1 添加收藏

**接口**: `POST /api/favorites/{unit_id}`

**功能描述**: 收藏指定房源

**请求头**:
```
Authorization: Bearer {token}
```

**路径参数**:

| 字段名 | 类型 | 必填 | 说明 |
|-------|------|-----|------|
| unit_id | string | 是 | 房源ID |

**响应示例**:
```json
{
  "id": 1,
  "unit_id": "76378129",
  "created_at": "2026-03-19T10:00:00"
}
```

---

#### 3.9.2 取消收藏

**接口**: `DELETE /api/favorites/{unit_id}`

**功能描述**: 取消收藏指定房源

**请求头**:
```
Authorization: Bearer {token}
```

**响应**: 204 No Content

---

#### 3.9.3 获取收藏列表

**接口**: `GET /api/favorites`

**功能描述**: 获取当前用户的收藏列表

**请求头**:
```
Authorization: Bearer {token}
```

**响应示例**: 返回收藏的房源列表

---

### 3.10 用户模块 (User)

#### 3.10.1 获取用户信息

**接口**: `GET /api/user/me`

**功能描述**: 获取当前登录用户信息

**请求头**:
```
Authorization: Bearer {token}
```

**响应示例**:
```json
{
  "id": 1,
  "username": "test_user",
  "phone": "13800138000",
  "full_name": "测试用户",
  "is_active": true,
  "preferred_district": "洪山区",
  "preferred_price_min": 100.00,
  "preferred_price_max": 300.00,
  "travel_purpose": "商务",
  "required_facilities": ["WiFi", "投影"]
}
```

---

#### 3.10.2 更新用户偏好

**接口**: `PUT /api/user/preferences`

**功能描述**: 更新用户偏好设置，用于优化推荐

**请求头**:
```
Authorization: Bearer {token}
```

**请求参数**:

| 字段名 | 类型 | 必填 | 中文名称 | 说明 |
|-------|------|-----|---------|------|
| preferred_district | string | 否 | 偏好行政区 | 偏好的行政区 |
| preferred_price_min | float | 否 | 最低价格偏好 | 价格偏好下限 |
| preferred_price_max | float | 否 | 最高价格偏好 | 价格偏好上限 |
| travel_purpose | string | 否 | 出行目的 | 情侣/家庭/商务/考研 |
| required_facilities | array | 否 | 必备设施 | 必须具备的设施列表 |

---

## 四、标签体系

### 4.1 标签分类

系统支持以下四类标签，用于房源筛选和特征提取：

| 标签类别 | 英文Key | 示例标签 |
|---------|--------|---------|
| 风格标签 | style_tags | 欧美风、网红INS风、现代风、日式风、中式风 |
| 设施标签 | facility_tags | 投影、洗衣机、空调、智能门锁、浴缸、冰箱、吹风机 |
| 位置标签 | location_tags | 近地铁、近景点、付费停车位、超市/菜场 |
| 服务标签 | service_tags | 管家服务、立即确认、团建会议 |

### 4.2 热门标签

| 标签名称 | 使用频率 | 平均溢价 |
|---------|---------|---------|
| 近地铁 | 1,755次 | +15% |
| 可做饭 | 1,204次 | +8% |
| 实拍看房 | 2,044次 | - |
| 干湿分离 | 913次 | +5% |
| 有投影 | 456次 | +34% |

---

## 五、错误码说明

### 5.1 HTTP状态码

| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功（无返回内容） |
| 400 | 请求参数错误 |
| 401 | 未授权（未登录或Token过期） |
| 403 | 禁止访问（权限不足） |
| 404 | 资源不存在 |
| 422 | 参数验证失败 |
| 500 | 服务器内部错误 |

### 5.2 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

---

## 六、通用说明

### 6.1 认证方式

所有需要登录的接口，需在请求头中携带Token：

```
Authorization: Bearer {access_token}
```

### 6.2 分页参数

| 参数 | 说明 | 默认值 |
|-----|------|-------|
| page | 页码（从1开始） | 1 |
| size | 每页数量 | 20 |

### 6.3 日期格式

所有日期时间字段使用ISO 8601格式：

```
2026-03-19T10:00:00
```

### 6.4 价格单位

所有价格字段单位为**人民币（元）**。

---

## 七、开发环境

### 7.1 本地启动

```bash
# 启动后端服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7.2 API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 7.3 健康检查

```bash
GET /api/health
```

响应：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "api": "running",
    "hive": "configured",
    "database": "connected"
  }
}
```

---

## 八、版本历史

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| v2.0 | 2026-03-19 | 重构数据层，接入真实Hive数据，新增我的房源模块 |
| v1.0 | 2025-12 | 初始版本，Mock数据实现 |

---

**文档维护**: 后端开发团队  
**联系方式**: 如有问题请联系后端负责人
