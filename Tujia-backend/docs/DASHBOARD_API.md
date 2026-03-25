# Dashboard API 接口文档

首页 Dashboard 数据接口文档，提供 KPI 指标、商圈热力图、热门商圈排行等数据。

---

## 接口概览

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| KPI 核心指标 | GET | `/api/dashboard/kpi` | 获取平台核心运营指标 |
| 商圈热力图 | GET | `/api/dashboard/heatmap` | 获取商圈地理热力分布数据 |
| 热门商圈排行 | GET | `/api/dashboard/top-districts` | 获取热门商圈排行榜 |
| 首页推荐卡片 | GET | `/api/home/recommendations` | 短列表；登录用户按问卷出行目的（`scene_scores`）与必带设施重排，见 [USER_SURVEY_AND_RECOMMENDATION.md](./USER_SURVEY_AND_RECOMMENDATION.md) |

---

## 1. KPI 核心指标

### 接口信息

- **URL**: `/api/dashboard/kpi`
- **Method**: `GET`
- **Content-Type**: `application/json`

### 响应参数

| 字段名 | 类型 | 说明 | 数据来源 |
|--------|------|------|----------|
| total_listings | integer | 平台总房源数 | 数据库实时统计 |
| avg_price | number | 全市平均房价（元/晚） | 数据库实时计算 |
| price_change_percent | number | 价格环比变化百分比 | 基于当前数据估算 |
| district_count | integer | 覆盖商圈/行政区数量 | 数据库实时统计 |
| occupancy_rate | number | 平均入住率（百分比） | 基于评分和收藏数估算 |
| avg_roi | number | 平均投资回报率（百分比） | 基于价格和入住率估算 |

### 响应示例

```json
{
  "total_listings": 2307,
  "avg_price": 200.2,
  "price_change_percent": 7.2,
  "district_count": 11,
  "occupancy_rate": 78.0,
  "avg_roi": 25.0
}
```

### 数据说明

- **total_listings**: 数据库中房源总数
- **avg_price**: 所有房源价格的算术平均值
- **price_change_percent**: 模拟数据，实际应基于历史价格对比计算
- **occupancy_rate**: 估算值，基于评分（权重高）和收藏数综合计算
- **avg_roi**: 估算值，基于平均价格和估算入住率计算得出

---

## 2. 商圈热力图

### 接口信息

- **URL**: `/api/dashboard/heatmap`
- **Method**: `GET`
- **Content-Type**: `application/json`

### 响应参数

| 字段名 | 类型 | 说明 |
|--------|------|------|
| data | array | 热力图数据点列表 |
| data[].name | string | 商圈名称 |
| data[].x | integer | 横坐标位置（0-100） |
| data[].y | integer | 纵坐标位置（0-100） |
| data[].value | integer | 热度值（0-100） |

### 响应示例

```json
{
  "data": [
    { "name": "洪山区", "x": 90, "y": 43, "value": 100 },
    { "name": "武昌区", "x": 66, "y": 45, "value": 100 },
    { "name": "江岸区", "x": 54, "y": 60, "value": 100 },
    { "name": "江汉区", "x": 47, "y": 55, "value": 100 },
    { "name": "黄陂区", "x": 36, "y": 90, "value": 100 }
  ]
}
```

### 坐标映射说明

- **x, y 坐标**: 基于商圈的真实经纬度映射到 0-100 的网格坐标系
- **映射规则**: 
  - 经度范围映射到 x 轴（10-90，留边距）
  - 纬度范围映射到 y 轴（10-90，留边距）
- **热度值计算**: 
  - 房源数量贡献（最多40分）
  - 平均评分贡献（最多30分）
  - 平均收藏数贡献（最多30分）

---

## 3. 热门商圈排行

### 接口信息

- **URL**: `/api/dashboard/top-districts`
- **Method**: `GET`
- **Content-Type**: `application/json`

### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| limit | integer | 否 | 10 | 返回数量限制（1-20） |

### 响应参数

| 字段名 | 类型 | 说明 |
|--------|------|------|
| items | array | 商圈排行列表 |
| items[].name | string | 商圈名称 |
| items[].heat | integer | 热度值（0-100） |
| items[].avg_price | number | 该商圈平均房价 |
| items[].price_trend | number | 价格趋势（百分比，可为负数） |
| items[].listing_count | integer | 该商圈房源数量 |

### 响应示例

```json
{
  "items": [
    {
      "name": "洪山区",
      "heat": 100,
      "avg_price": 200.3,
      "price_trend": 9.5,
      "listing_count": 486
    },
    {
      "name": "武昌区",
      "heat": 100,
      "avg_price": 228.2,
      "price_trend": 1.9,
      "listing_count": 622
    }
  ]
}
```

### 热度计算规则

热度值综合以下因素计算：
- 房源数量权重（1.5分/套）
- 平均评分权重（10分/星）
- 平均收藏数权重（0.3分/个）

结果取整并限制在 0-100 范围内。

---

## 前端调用示例

### JavaScript / TypeScript

```typescript
// KPI 指标
const kpiData = await fetch('/api/dashboard/kpi').then(r => r.json());
console.log(`总房源: ${kpiData.total_listings}, 平均价格: ¥${kpiData.avg_price}`);

// 热力图
const heatmapData = await fetch('/api/dashboard/heatmap').then(r => r.json());
heatmapData.data.forEach(point => {
  console.log(`${point.name}: (${point.x}, ${point.y}) 热度: ${point.value}`);
});

// 热门商圈排行
const topDistricts = await fetch('/api/dashboard/top-districts?limit=5').then(r => r.json());
topDistricts.items.forEach(district => {
  console.log(`${district.name}: 热度${district.heat}, 均价¥${district.avg_price}`);
});
```

---

## 注意事项

1. **数据实时性**: KPI 指标和热力图数据基于数据库实时统计，可能存在秒级延迟
2. **模拟数据**: `price_change_percent`、`occupancy_rate`、`avg_roi`、`price_trend` 为基于现有数据估算的模拟值
3. **坐标系统**: 热力图使用相对坐标（0-100），前端需要根据实际画布尺寸进行缩放
4. **性能优化**: 热门商圈排行接口支持 limit 参数，建议根据实际展示需求合理设置

---

## 错误处理

所有接口在错误情况下返回标准的 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 500 | 服务器内部错误 |

错误响应格式：
```json
{
  "detail": "错误描述信息"
}
```
