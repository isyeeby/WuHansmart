# 指标与口径对照（线上以 MySQL 为准）

本文档与 [`DATA_LAYER_AND_RUNTIME.md`](DATA_LAYER_AND_RUNTIME.md) 配合使用；**线上面向用户的聚合与列表数据以 MySQL `listings` 等表为准**（Hive 仅离线层）。

| 名称 | 常见出现位置 | 口径说明 |
|------|----------------|----------|
| 商圈均价（预测/竞争力） | `/api/predict/*`、`competitiveness` | 默认：同**行政区** `district` 下 `listings.final_price` 算术平均；响应中 `district_avg_scope=district_all_listings`。与分析页按 `district+trade_area` 分组均价可能不同。 |
| 商圈均价（分析页） | `/api/analysis/districts` | 按 **`district` + `trade_area`** 分组聚合。 |
| 竞品样本均价 | `/api/my-listings/.../competitors` | 本次选取的**竞品列表**的 `final_price` 均值，非全市均价。 |
| 入住率 / 平台 ROI（KPI） | `/api/dashboard/kpi` | **启发式展示指数**，非订单口径；见响应 `kpi_definitions`。 |
| 首页热门商圈 / 热力图 | `/api/home/hot-districts`、`/heatmap` | 优先 Hive ODS（若可连）；失败或空则用 MySQL 聚合；仍无数据时见 `data_source=demo_fallback`。 |
| 模型合理价 | 智能定价、竞争力 | 日级 XGBoost 对锚定日的估算，与「商圈均价」不同维度，不可混读为同一指标。 |
