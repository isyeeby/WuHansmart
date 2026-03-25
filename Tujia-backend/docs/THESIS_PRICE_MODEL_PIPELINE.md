# 民宿日价预测：数据处理与 XGBoost 建模流程（论文体例说明）

本文档以学位论文「数据处理—特征工程—模型训练—评估—部署对齐」的常见写法组织，与仓库实现 `scripts/train_model_mysql.py`、`app/ml/hive_training_loader.py`、`app/ml/calendar_features.py`、`app/ml/price_feature_config.py`、`app/services/model_manager.py` 保持一致。文中指标为**某次本地 MySQL 全量训练示例**，复现时以 `models/model_metrics_latest.json` 为准。

---

## 1 问题形式化

设第 \(i\) 套房源在观测时刻的日价（或挂牌等价日价）为 \(y_i \in \mathbb{R}^+\)。给定结构属性、区位与文本标签衍生的设施指示、以及价格日历聚合统计 \(\mathbf{c}_i\)，学习映射 \(f: \mathbf{x}_i \mapsto \hat{y}_i\)，使在**留出测试集**上的绝对误差与相对误差可控。工程上采用对数变换 \(\tilde{y}_i=\log(1+y_i)\)，预测阶段 \(\hat{y}_i=\exp(\tilde{\hat{y}}_i)-1\)，以缓解价格右偏。

---

## 2 数据来源与数仓路径

### 2.1 架构约定

规范情形下，明细与日历数据经 ETL 进入 Hive 数仓 **ODS** 层：`ods_listings`、`ods_price_calendar`（参见 `sql/hive_load_data.hql`）。在线业务库 **MySQL** 承担 OLTP 与 API 读写在 Hive 不可用时的兜底。

### 2.2 训练脚本双路径

脚本 `scripts/train_model_mysql.py` 支持：

| 模式 | 行为 |
|------|------|
| `--data-source auto`（默认） | 优先从 Hive 拉取 ODS；若连接失败、行数不足或过滤后样本不足，则回退 MySQL。 |
| `--data-source hive` | 强制 Hive；失败则退出并提示。 |
| `--data-source mysql` | 强制 MySQL。 |

环境变量 `TRAIN_DATA_SOURCE` 可设默认值；**命令行优先**。

Hive 连接顺序：**impyla**（`app/db/hive.py`）→ **Docker 内 hive CLI**（`HiveDockerService.run_query_dataframe`）。房源与日历聚合 SQL 使用同一成功通道，避免混源。

### 2.3 Hive 与 MySQL 的口径差异（可在论文「局限」中说明）

- **日历周末溢价**：Hive 路径当前在 ODS 聚合阶段未计算周末/工作日分桶时，`cal_weekend_premium` 在 Python 中置 0；MySQL 路径可从 `price_calendars` 明细计算完整统计。二者同属 `CALENDAR_FEATURE_NAMES` 维度，但**语义粒度**不同，可表述为「离线仓聚合口径」与「业务库明细口径」。
- **设施标签**：Hive `ods_listings.tags` 与 MySQL `house_tags` 均需经同一 `parse_house_tags` 解析为关键词集合，再映射为二值设施列（`FACILITY_KEYWORDS`）。

---

## 3 特征工程

### 3.1 结构与市场属性

面积、卧室数、床位数、可住人数、评分、收藏量、房型、经纬度等由基础表直接给出或简单派生（如 `area_per_bedroom`、`heat_score`）。

### 3.2 防泄漏的区位统计

**行政区**层面的均价、中位数、标准差、样本量等 **仅在训练子集上** 估计，再 merge 回训练与测试集；测试集未见类别在 `district` / `trade_area` / `house_type` 整数编码中映射为 0。该流程在 `preprocess_after_split` 中实现，对应论文中「目标编码/统计特征不得使用测试集标签」的表述。

### 3.3 经济型指示 `is_budget`

采用**结构定义**（面积与卧室数阈值，见 `compute_is_budget_structural`），**不**使用真实成交价构造，避免以因变量定义自变量。

### 3.4 设施与 `facility_count`

设施为与线上一致的二值列集合；`facility_count` 为上述列之和，与 `model_manager` 推理侧一致。

### 3.5 价格日历聚合特征

十维：`cal_n_days`、`cal_mean`、`cal_std`、`cal_min`、`cal_max`、`cal_median`、`cal_cv`、`cal_range_ratio`、`cal_bookable_ratio`、`cal_weekend_premium`。缺失日历在划分后由训练集条件统计填充（`impute_calendar_train_test`），默认值写入 `calendar_feature_defaults.json` 供线上缺日历时使用。

---

## 4 数据集划分与过滤

- 保留 \(50 \le y_i \le 5000\)（元）的样本，抑制极端值对度量与梯度的影响；可在论文中说明为业务量级与鲁棒性处理。
- 按价格分桶（低价/中价/高价三档）做 **分层留出**，取 `StratifiedKFold` 第一折作为 80%/20% 训练/测试划分，保证各桶比例稳定。
- 剔除训练子集中样本数少于 5 的行政区，再同步约束测试集，减少稀有区估计方差。

---

## 5 模型与训练细节

- **基学习器**：XGBoost 回归，`objective=reg:squarederror`；`n_estimators=600`，`max_depth=6` 等见脚本 `params`。
- **样本权重**：低价段与高价段略增权，以平衡长尾。
- **早停说明**：部分环境中 `sklearn` 封装 `XGBRegressor.fit` 不支持 `early_stopping_rounds` / `callbacks`；当前仅用 `eval_set` 监控对数目标上的验证表现，**不**启用早停，论文可如实写明环境约束或固定迭代次数策略。

---

## 6 评估指标与示例结果

在**原始价格尺度**上报告：MAE、RMSE、\(R^2\)、MAPE；并分价格区间汇报测试集表现。

**示例（MySQL 路径，与某次运行一致，仅供引用格式）**：

- 测试集：MAE ≈ 23.67 元，\(R^2\) ≈ 0.7625，MAPE ≈ 10.4%。
- 分区间 MAE/MAPE 见训练日志「分价格区间评估」。

正式撰写时，应替换为**你本人复现**时 `model_metrics_latest.json` 中的 `metrics` 与 `train_metrics`，并注明 `data_source` 字段（如 `MySQL Database` 或 `Hive ODS (hive_impyla)`）。

---

## 7 与服务端一致性

训练产物包括：

- `xgboost_price_model_latest.pkl`
- `feature_names_latest.json`
- `district_encoder_latest.pkl`、`trade_area_encoder_latest.pkl`、`house_type_encoder_latest.pkl`
- `district_stats.json`、`calendar_feature_defaults.json`

API 推理路径应加载上述文件，并对 `cal_*`、`is_budget`、`facility_count` 等与训练对齐。若请求携带 `unit_id`，可从 MySQL 拉取日历并合并特征（见 `price_predictor`）。

---

## 8 复现实验命令

在 `Tujia-backend` 目录下：

```bash
# 优先 Hive，失败则 MySQL
python scripts/train_model_mysql.py --data-source auto

# 仅 MySQL（当前离线环境常用）
python scripts/train_model_mysql.py --data-source mysql

# 仅 Hive（需 impyla 或 Docker hive-server 可用且 ODS 有数据）
python scripts/train_model_mysql.py --data-source hive
```

训练完成后可与测试集真实价对比抽样脚本（若已配置）核对推理一致性。

---

## 9 结论性表述建议

可在论文小结中强调：（1）划分优先与训练集限定统计量，控制标签泄漏；（2）对数目标与样本权重改善偏态与长尾；（3）日历聚合与挂牌价互补；（4）Hive 为主、MySQL 为备的数据管线符合数仓规范且保证 Hive 故障时可训练。若 Hive 与 MySQL 指标存在差异，归因于**样本时间切片、缺失模式与日历口径**，而非模型结构本身。

---

*文档版本与脚本同步维护；特征或划分逻辑变更后须重新训练并更新本节中的指标引用。*
