# 武汉民宿价格预测分析系统 (Wuhan B&B Price Analysis System)

## 项目简介

基于大数据的民宿价格分析与预测系统**前端**。面向房东与投资者，展示武汉途家市场行情与智能定价相关能力。

**Monorepo 说明**：本目录在完整仓库中为 **`TuJiaFeature/`**。单独拉「前端部署分支」时，使用远程分支 **`deploy-frontend`**（由 `git subtree split --prefix=TuJiaFeature` 生成，根目录即本前端内容）。详见仓库根目录 [`../deploy/README.md`](../deploy/README.md)。

## 技术栈

- **前端**: React 19, TypeScript, Ant Design 5, ECharts, Tailwind CSS
- **后端**: 见同级目录 [`../Tujia-backend`](../Tujia-backend)；数仓目标 Hive，本地开发将 Vite 代理到 FastAPI，数据层说明见后端 [`docs/DATA_LAYER_AND_RUNTIME.md`](../Tujia-backend/docs/DATA_LAYER_AND_RUNTIME.md)

## 功能模块

1. **经营驾驶舱**：全市宏观概览  
2. **商圈分析**：价格、热度对比  
3. **智能定价预测**：XGBoost 演示  
4. **房源推荐**：首页「智能推荐」走 **`/api/home/recommendations`**（SQL+场景/设施重排）；「个性化推荐」页走 **`/api/recommend`**（条件匹配为主，见后端 `RECOMMENDATION_ONLINE_BEHAVIOR.md`）  
5. **房源列表**：紧凑筛选；关键词搜索（标题/行政区/商圈，参数 `keyword`）；登录用户可选「按偏好排序」（`sort_by=personalized`，**规则区域重排**，原理见后端 [`docs/LISTINGS_PERSONALIZED_SORT.md`](../Tujia-backend/docs/LISTINGS_PERSONALIZED_SORT.md)）；详情页会写入浏览历史（见后端 PRD 1.4）  

## 文档（勿在本仓库重复维护长文）

| 内容 | 位置 |
|------|------|
| API 与接口约定 | [`../Tujia-backend/docs/BACKEND_API_SPEC.md`](../Tujia-backend/docs/BACKEND_API_SPEC.md) |
| 文档总索引 | [`../Tujia-backend/docs/README.md`](../Tujia-backend/docs/README.md) |
| Dashboard 接口细节 | [`../Tujia-backend/docs/DASHBOARD_API.md`](../Tujia-backend/docs/DASHBOARD_API.md) |

## 运行说明

```bash
npm install
npm run dev
```

将 `vite` 代理指向本地后端（默认 `http://localhost:8000`），详见项目内 `vite.config` / 环境配置。
