# 民宿日价预测：日级数据处理与 XGBoost 建模（论文体例说明）

本文档描述**线上定价**采用的**日级**样本与模型管线，与实现 `scripts/train_model_daily_mysql.py`、`app/ml/daily_calendar_features.py`、`app/ml/daily_price_inference.py`、`app/services/daily_price_service.py` 对齐。指标以当次训练导出的 `models/model_metrics_daily.json` 为准。

---

## 1 问题形式化

对日历中每一「房源–日期」样本，给定该日 \(d\) 的静态属性、区位编码与统计、节假日与 horizon 等日期特征，预测当日价格 \(y\)。训练目标采用 \(\log(1+y)\)，推理阶段 \(\mathrm{expm1}\) 还原为元。

---

## 2 数据与划分

- **来源**：MySQL `listings` 与 `price_calendars` 合并；价格过滤与脚本一致（如 \(50\le y \le 5000\)）。
- **时间划分**：默认按全局日期轴 70% / 15% / 15% 切分训练、验证、测试，避免未来信息泄漏。
- **可选**：`--split-mode per_unit` 按每套房源各自日历切分。

---

## 3 特征概要

- **静态**：面积、卧室/床/可住人数、评分、收藏、经纬度、设施二值列、`facility_count`、`is_budget` 等（与 `price_feature_config` 一致）。
- **区位**：行政区/商圈/房型编码及训练集聚合的 `dist_*`、`ta_*` 统计（见训练脚本 `preprocess_daily`）。
- **日历与日期**：`add_daily_date_features`、`add_holiday_proximity_features`、horizon（未来第几天）等。

---

## 4 模型与训练

- **基学习器**：XGBoost 回归，`reg:squarederror`，Booster 参数可由环境变量 `TRAIN_XGB_*` 配置（与 `train_model_mysql._build_booster_params_from_env` 共用约定）。
- **验证早停**：验证集为时间切分中间段；`TRAIN_XGB_NUM_BOOST_ROUND`、`TRAIN_XGB_EARLY_STOPPING_ROUNDS` 控制轮数与早停。
- **分位数（可选）**：`reg:quantileerror` 训练 Q20/Q50/Q80，供 14 天区间；缺失时用验证 MAE 误差带兜底。

---

## 5 产物与线上加载

训练脚本写入（节选）：

- `models/xgboost_price_daily_model.pkl`
- `models/feature_names_daily.json`
- `models/xgboost_price_daily_q020.pkl` 等（若未 `--skip-quantiles`）
- `models/*_encoder_daily.pkl`、`district_stats_daily.json`、`daily_forecast_meta.json` 等

API 通过 `DailyPriceForecastService` 加载上述文件，构造与训练一致的特征矩阵后逐日预测。

---

## 6 复现命令

在 `Tujia-backend` 目录：

```bash
python scripts/train_model_daily_mysql.py
python scripts/train_model_daily_mysql.py --split-mode per_unit
```

建议安装 `chinesecalendar` 以完整节假日特征。

---

## 7 与推荐模块的关系

房源**相似度推荐**使用 `listing_similarity_*.npz`（`ModelManager`），与定价模型文件相互独立。
