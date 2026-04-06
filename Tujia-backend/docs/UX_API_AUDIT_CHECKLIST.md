# 页面 × API × 口径 审查清单

用于迭代中**人工勾选**的一致性检查；无法替代自动化测试。权威口径见 [METRICS_GLOSSARY.md](./METRICS_GLOSSARY.md)、[BACKEND_API_SPEC.md](./BACKEND_API_SPEC.md)；模块风险总表见 [MODULE_AUDIT_AND_SMOKE.md](./MODULE_AUDIT_AND_SMOKE.md)。

## 使用方式

- 发版或大改某页时，勾选对应行并记录日期/执行人。
- **P0**：文案是否把代理指标说成「真实入住率/确定 ROI/因果溢价」等。
- **P1**：价格字段是否混用（`final_price` / `current_price` / 日历当日价）而未在 UI 披露。

## 矩阵（前端路由 → 主要 API → 关注口径）

| 页面（路由） | 主要 API | 关注口径 / 已知注意点 |
|--------------|----------|------------------------|
| 首页 `/` | `/api/home/*`、`/api/home/recommendations` | 推荐条 **≠** `/api/recommend`；热力/统计样本量 |
| 经营驾驶舱 `/dashboard` | `/api/dashboard/*`、`/api/analysis/districts`、`/api/analysis/facility-premium`、等 | KPI 热度非入住率；设施溢价非因果；`price_change` 来自日历对比 |
| 重定向 `/analysis` | — | 应跳到 `/dashboard?tab=districts` |
| 房源列表 `/listings` | `/api/listings` | `personalized` 为规则重排；关键词/分页 |
| 详情 `/listing/:id` | `/api/listings/*`、日历、相似 | `display_price` 与 `final_price` 说明 |
| 智能定价 `/prediction` | `/api/predict/*` | 日级模型 503；无 `/predict/trend` |
| 推荐 `/recommendation` | `/api/recommend/*` | 与首页 recommendations 区分 |
| 投资 `/investment`、机会 `/opportunities` | `/api/investment/*`、`/api/analysis/price-opportunities` | 洼地同源；`calculation_basis` / `methodology` |
| 对比 `/comparison` | `/api/compare` | 评分归一化范围限于本次选集 |
| 我的房源 `/my-listings` | `/api/my-listings/*` | 竞品：分位混价口径；相似度为分项加权，非 predict 竞品算法 |
| 竞品情报 `/competitor` | `/api/my-listings/.../competitors` | Tooltip 以 `selection_note` 为准 |
| 收藏 `/favorites` | `/api/favorites` | 登录态 |

## 已知技术债（待产品决策或排期）

| 项 | 说明 |
|----|------|
| 竞品严格定义 | 未按户型过滤；候选池依赖行政区 + 距离 |

---

*本清单随架构迭代更新；重大变更请同步 [BACKEND_API_SPEC.md](./BACKEND_API_SPEC.md) §8.1。*
