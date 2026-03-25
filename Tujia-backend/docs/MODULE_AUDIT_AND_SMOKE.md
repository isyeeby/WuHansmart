# 全模块严谨性说明 + 烟测与手工验收

本文档对应「全模块严谨性二次排查 + 前后端功能测试计划」的**答辩用简表**与**执行说明**；计划文件请勿修改，以本文档为仓库内落地物。

## 1. 模块 × 口径/依据风险 × 建议表述

| 模块 | 前端路由（参考） | 主要 API 前缀 | 口径/依据风险 | 答辩/文档建议 |
|------|------------------|---------------|----------------|----------------|
| 认证与安全 | `/login` | `/api/auth` | 无 token 时 `get_current_user_id` 仍等价于演示用户；多租户隔离不成立 | 写明「演示环境」；生产需严格 JWT |
| 首页 | `/` | `/api/home`、`/api/home/recommendations` | 统计等走 `home`；**智能推荐条**专走 `recommendations`（SQL+场景/设施重排），**非** `/api/recommend` | 与 DATA_LAYER 对照样本量；勿与推荐页算法混称 |
| 驾驶舱 | `/dashboard` | `/api/dashboard` | KPI、趋势中部分为启发式或日历代理指标 | 以接口 `kpi_definitions`/`series_note` 为准，勿当真实入住率 |
| 房源列表/详情 | `/listings`, `/listing/:id` | `/api/listings` | 依赖库内 listings；与两 JSON 交集定义可能不一致 | 论文声明分析母体 |
| 数据分析 | `/analysis` | `/api/analysis` | 分布/机会/ROI 为统计或规则聚合，非订单事实 | 脚注「平台挂牌口径」 |
| 价格预测 | `/prediction` | `/api/predict` | 节假日硬编码、forecast/trend 示意或随机种子、无模型时启发式 | 看 `methodology`/`data_kind` |
| 推荐 | `/recommendation` | `/api/recommend` | 默认带出行目的时主路径为条件匹配+读库 `scene_scores`；矩阵用于扩展/协同；无模型时扩展弱、可热门兜底 | 见 RECOMMENDATION_ONLINE_BEHAVIOR |
| 投资与机会 | `/investment`, `/opportunities` | `/api/investment` | 假设参数、启发式入住代理 | 敏感性说明 |
| 对比 | `/comparison` | `/api/compare` | 评分基于本次选集归一化 | 响应内 `scoring_methodology` |
| 我的房源/竞品页 | `/my-listings`, `/competitor` | `/api/my-listings` | 竞品池=同区；排序=距离优先；非「同户型竞品」 | 称「周边参照」或后续加户型过滤 |
| 收藏与历史 | `/favorites` | `/api/favorites`, `/api/user/me/*` | 与 user 路由并存 | 实现以 favoritesApi 为准 |
| 地理编码 | 我的房源表单 | `/api/geocode` | Nominatim 频率与精度限制 | 可换国内图商 |
| Hive | — | `hive.py` / `hive_service` | 分析类优先 DWS/ADS（HS2 或 Docker CLI），失败则 MySQL；`HIVE_ANALYTICS_PRIMARY=false` 可全 MySQL | 见 DATA_LAYER_AND_RUNTIME |

## 2. 竞品选取逻辑（当前实现）

- **候选池**：`Listing.district` 与「我的房源」行政区相同。
- **排序**：双方有有效经纬度时，按 **Haversine 直线距离** 升序取 10 条；否则取同区前 10 条。
- **界面「相似度」**：由 **现价与竞品价差** 推导，**不参与排序**。
- **严格竞品**（未实现）：可先过滤 `bedroom_count` / `max_guests` 等再按距离排序。

## 3. 自动化烟测（前端 ApiTest 页）

- 路径：`TuJiaFeature` 中打开 **`/api-test`**，点击运行；或开发时看浏览器控制台 `printResults`。
- 实现文件：[`TuJiaFeature/src/utils/apiTest.ts`](../../TuJiaFeature/src/utils/apiTest.ts)。
- **前置**：后端已启动且 Vite 代理 `/api` 到后端；存在可登录用户（默认脚本使用 `demo` / `demo123`）。
- **说明**：部分用例依赖库内存在至少 2 条 `listings`（用于动态 `unit_id`）；**我的房源**用例会先 POST 创建再使用返回的 **数字 `id`** 调用竞品与定价建议。

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
4. **房源列表 → 详情**：分页、详情、收藏按钮（若启用）。
5. **收藏**：列表、文件夹（若有）、浏览历史写入。
6. **推荐**：换区/刷新有结果。
7. **数据分析**：各 Tab 有数据或空态。
8. **价格预测**：单次预测、趋势/因子等子功能。
9. **对比**：选两套房源对比；保存对比（登录态）。
10. **投资**：计算、现金流、敏感性、排行、机会。
11. **机会**页：与 analysis/investment 数据一致性感知。
12. **我的房源**：新建（地图选点/解析坐标/手输经纬度）、编辑、竞品分析、定价建议。
13. **竞品**页：选择房源、表格距离列、`selection_note`。
14. **ApiTest**：一键烟测，记录失败项。

## 7. 烟测结果记录（模板）

| 日期 | 执行人 | tsc | build | pytest | ApiTest 成功/失败数 | 备注 |
|------|--------|-----|-------|--------|---------------------|------|
| 2026-03-24 | Agent | 通过 | 通过 | **21 passed**（`tests/test_smoke_routes.py`） | 需在本地起前后端后于 `/api-test` 执行 | 修复了 `/api/dashboard/heatmap` 在 MySQL Decimal 下的 TypeError |

**ApiTest 页**：本仓库未在无浏览器会话下跑通一键测试；请在 `TuJiaFeature` 执行 `npm run dev`、后端 `uvicorn` 后打开 `http://localhost:5173/api-test`（或你的前端端口）运行并自行填入上表「ApiTest」列。

**手工 E2E**：见第 6 节清单，由你在浏览器逐项勾选；与自动化互补，不可替代（尤其地图选点、表单校验等）。

---

*与数据层说明互补：[`DATA_LAYER_AND_RUNTIME.md`](./DATA_LAYER_AND_RUNTIME.md)*
