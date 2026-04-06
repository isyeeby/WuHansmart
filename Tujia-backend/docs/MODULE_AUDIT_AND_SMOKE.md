# 全模块严谨性说明 + 烟测与手工验收

本文档对应「全模块严谨性二次排查 + 前后端功能测试计划」的**答辩用简表**与**执行说明**；计划文件请勿修改，以本文档为仓库内落地物。

## 1. 模块 × 口径/依据风险 × 建议表述

| 模块 | 前端路由（参考） | 主要 API 前缀 | 口径/依据风险 | 答辩/文档建议 |
|------|------------------|---------------|----------------|----------------|
| 认证与安全 | `/login` | `/api/auth` | 无 token 时 `get_current_user_id` 仍等价于演示用户；多租户隔离不成立 | 写明「演示环境」；生产需严格 JWT |
| 首页 | `/` | `/api/home`、`/api/home/recommendations` | 统计等走 `home`；**智能推荐条**专走 `recommendations`（SQL+场景/设施重排），**非** `/api/recommend` | 与 DATA_LAYER 对照样本量；勿与推荐页算法混称 |
| 驾驶舱 | `/dashboard` | `/api/dashboard` | KPI、趋势中部分为启发式或日历代理指标 | 以接口 `kpi_definitions`/`series_note` 为准，勿当真实入住率 |
| 房源列表/详情 | `/listings`, `/listing/:id` | `/api/listings`（含 `keyword`、`sort_by=personalized`） | 依赖库内 listings；`personalized` 为规则区域重排，见 [`LISTINGS_PERSONALIZED_SORT.md`](./LISTINGS_PERSONALIZED_SORT.md) | 论文声明分析母体 |
| 经营驾驶舱（含原「数据分析」） | `/dashboard`（Tab：`overview`/`districts`/`facilities`）；`/analysis` **重定向** 至 `/dashboard?tab=districts` | `/api/dashboard`、`/api/analysis` | 总览 KPI/趋势走 dashboard；名录与设施溢价走 analysis；分布/机会/ROI 为统计或规则聚合，非订单事实；`/roi-ranking` 返回 `{ data, field_glossary }` | 侧栏选中键仍为 `/dashboard`；脚注「平台挂牌口径」；glossary 区分综合分与财务 ROI |
| 价格预测 | `/prediction` | `/api/predict` | 节假日硬编码、forecast 无模型时 503；**无** `/predict/trend` | 看 `methodology`/`data_kind` |
| 推荐 | `/recommendation` | `/api/recommend` | 默认带出行目的时主路径为条件匹配+读库 `scene_scores`；矩阵用于扩展/协同；无模型时扩展弱、可热门兜底 | 见 RECOMMENDATION_ONLINE_BEHAVIOR |
| 投资与机会 | `/investment`, `/opportunities` | `/api/investment`、`/api/analysis/price-opportunities` | 价格洼地与投资列表**同源**日级模型+区中位数（`price_opportunity_scan`）；`opportunities` 的 `max_budget`(万元) 按日价×20×12 过滤；敏感性矩阵分母可传 `baseline_capital_yuan` | 见 `methodology`、`calculation_basis` |
| 对比 | `/comparison` | `/api/compare` | 评分基于本次选集归一化 | 响应内 `scoring_methodology` |
| 我的房源/竞品页 | `/my-listings`, `/competitor` | `/api/my-listings`（竞品分析走 `.../competitors`） | 我的房源竞品：池=同区；先距离/区取 10 条再按多维相似度排序；非「同户型竞品」 | 称「周边参照」或后续加户型过滤；`GET /api/predict/competitors/{unit_id}` 仅后端保留，前端未接 |
| 收藏与历史 | `/favorites` | `/api/favorites`, `/api/user/me/*` | 与 user 路由并存 | 实现以 favoritesApi 为准 |
| 地理编码 | 我的房源表单 | `/api/geocode` | Nominatim 频率与精度限制 | 可换国内图商 |
| Hive | — | `hive.py` / `hive_service` | 分析类优先 DWS/ADS（HS2 或 Docker CLI），失败则 MySQL；`HIVE_ANALYTICS_PRIMARY=false` 可全 MySQL | 见 DATA_LAYER_AND_RUNTIME |

## 2. 竞品选取与相似度（`GET /api/my-listings/{id}/competitors`，当前实现）

- **候选池**：`Listing.district` 与「我的房源」行政区相同。
- **排序（先选池内 10 条）**：双方有有效经纬度且池内存在坐标时，按 **Haversine 直线距离** 升序取最近 10 条；否则同区取前 10 条（库顺序不定）。响应含 `selection_note` / `geo_ranking_used`。
- **展示排序**：返回的 `competitors` 数组按 **`similarity_score` 降序**、**`distance_km` 升序**（无距离则靠后）。
- **相似度分数**：价格（`current_price` vs `final_price`）与卧室/床/可住人数/面积分项 0–100 加权，缺失维度自动重加权；全不可算时 50。与 `/api/predict/competitors/{unit_id}`（平台内竞品、另一套余弦特征）**不是**同一算法。
- **价格分位**：竞品用 `final_price`，我的房源用 `current_price` 参与排序分位，混口径——对外说明见 `BACKEND_API_SPEC` 3.5.3 与响应 `market_position.price_percentile_methodology`。
- **严格竞品**（未实现）：可先过滤 `bedroom_count` / `max_guests` 等再按距离排序。

## 3. 自动化烟测

- **推荐**：后端 `pytest tests/test_smoke_routes.py`（见第 5 节）；CI 或发版前执行。
- 原前端 **`/api-test` 一键烟测页已移除**，避免与真实业务页重复维护；联调以业务路径 + pytest 为主。

## 4. 静态检查命令

```bash
# 前端
cd TuJiaFeature && npx tsc --noEmit && npm run build

# 后端
cd Tujia-backend && python -c "from main import app"
```

## 5. 后端 pytest 烟测（可选）

```bash
cd Tujia-backend
pip install pytest httpx
pytest tests/test_smoke_routes.py -v
```

不保证 DB 有数据时仍全部 200；断言以「非 500」或「预期 404/422」为主，见测试文件注释。

## 6. 手工 E2E 清单（浏览器）

按顺序执行，关注 **无连续 401/500** 与 **文案与口径一致**。

1. 登录（`demo` / `demo123` 或你的账号）。
2. **首页**：统计、推荐、热力图区域加载。
3. **Dashboard**：summary、kpi、图表、热力图说明。
4. **房源列表 → 详情**：分页、关键词筛选、排序含「按偏好」、详情、收藏按钮（若启用）。
5. **收藏 / 浏览**：列表、文件夹（若有）；详情加载后写入浏览历史（供列表 `personalized` 与推荐侧使用）。
6. **推荐**：换区/刷新有结果。
7. **经营驾驶舱**：切换 **市场总览 / 商圈名录 / 设施溢价** Tab，名录与溢价有数据或空态；直接访问 `/analysis` 应跳到 `/dashboard?tab=districts`。
8. **价格预测**：单次预测、趋势/因子等子功能。
9. **对比**：选两套房源对比；保存对比（登录态）。
10. **投资**：计算、现金流、敏感性、排行、机会。
11. **机会**页：与 analysis/investment 数据一致性感知。
12. **我的房源**：新建（地图选点/解析坐标/手输经纬度）、编辑、竞品分析、定价建议。
13. **竞品**页：选择房源、表格距离列、`selection_note`。

## 7. 烟测结果记录（模板）

| 日期 | 执行人 | tsc | build | pytest | 备注 |
|------|--------|-----|-------|--------|------|
| 2026-03-24 | Agent | 通过 | 通过 | **21 passed**（`tests/test_smoke_routes.py`） | 修复了 `/api/dashboard/heatmap` 在 MySQL Decimal 下的 TypeError |

**手工 E2E**：见第 6 节清单，由你在浏览器逐项勾选；与自动化互补，不可替代（尤其地图选点、表单校验等）。

---

*与数据层说明互补：[`DATA_LAYER_AND_RUNTIME.md`](./DATA_LAYER_AND_RUNTIME.md)*  
*页面级审查矩阵：[`UX_API_AUDIT_CHECKLIST.md`](./UX_API_AUDIT_CHECKLIST.md)*
