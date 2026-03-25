# 机器学习数据流程说明

## 📊 为什么选择从Hive DWD层加载训练数据？

### 数据分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  ODS层 (原始数据)                                            │
│  ├─ 数据: 从爬虫直接导入的原始JSON数据                       │
│  ├─ 质量: 未经清洗，可能包含异常值、缺失值                   │
│  └─ 用途: 数据备份，追溯原始数据                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 数据清洗 (Hive SQL)
┌─────────────────────────────────────────────────────────────┐
│  DWD层 (明细数据层) ⭐ 推荐从这里加载                        │
│  ├─ 数据: 清洗后的明细数据                                   │
│  ├─ 清洗: 价格异常过滤、等级分类、设施标准化                 │
│  ├─ 质量: 数据质量分>=50，价格合理范围                       │
│  └─ 用途: 机器学习训练、特征工程                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 聚合统计 (Hive SQL)
┌─────────────────────────────────────────────────────────────┐
│  DWS层 (汇总数据层)                                          │
│  ├─ 数据: 商圈统计、设施溢价分析、价格分布                   │
│  └─ 用途: API报表查询、快速统计                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 业务计算 (Hive SQL)
┌─────────────────────────────────────────────────────────────┐
│  ADS层 (应用数据层)                                          │
│  ├─ 数据: 价格洼地、ROI排名、推荐结果                        │
│  └─ 用途: 直接支撑API查询                                    │
└─────────────────────────────────────────────────────────────┘
```

### 从DWD层加载的优势

| 优势 | 说明 |
|------|------|
| **数据质量** | DWD层已完成清洗，过滤了异常价格和低质量数据 |
| **特征标准化** | 价格等级、评分等级、设施数量已预计算 |
| **一致性** | 训练和预测使用相同的数据标准 |
| **可复现** | Hive SQL清洗逻辑可审计、可追溯 |
| **扩展性** | 数据量增加时，Hive分布式计算能力更强 |

### 数据清洗流程（Hive SQL）

```sql
-- DWD层数据清洗示例（已在hive_load_data.hql中定义）
INSERT OVERWRITE TABLE dwd_listing_details
SELECT
    unit_id, district,
    -- 清洗异常价格
    CASE
        WHEN price IS NULL OR price <= 0 OR price > 5000 THEN NULL
        ELSE price
    END as price,
    -- 价格等级分类
    CASE
        WHEN price < 150 THEN '低'
        WHEN price < 300 THEN '中'
        ELSE '高'
    END as price_level,
    -- 评分等级分类
    CASE
        WHEN rating < 4.0 THEN '低'
        WHEN rating < 4.7 THEN '中'
        ELSE '高'
    END as rating_level,
    -- 计算设施总数
    (has_projector + has_kitchen + ...) as facility_count,
    ...
FROM ods_listings
WHERE data_quality_score >= 50;  -- 只保留高质量数据
```

## 🚀 训练脚本使用说明

### 默认从Hive加载（推荐）

```bash
# 方式1: 默认从Hive DWD层加载
python scripts/train_xgboost_model.py

# 方式2: 显式指定从Hive加载
python scripts/train_xgboost_model.py --source hive

# 输出示例:
# ============================================================
# XGBoost价格预测模型训练
# ============================================================
#
# 数据源: HIVE
# 目标: tujia_dw.dwd_listing_details (Hive清洗后的明细数据)
# ============================================================
#
# 从Hive DWD层加载清洗后的数据...
#   ✓ 从Hive加载 4872 条清洗后的记录
#   ✓ 数据来源: tujia_dw.dwd_listing_details
#   ✓ 数据质量: 已过滤异常价格和质量分<50的数据
#
# 验证数据质量...
#   ✓ 初始记录数: 4872
#   ✓ 有效记录数: 4821
#   ✓ 过滤比例: 1.0%
#   ✓ 价格范围: 68 - 4999 元
#   ✓ 平均价格: 312 元
#   ✓ 覆盖商圈: 15 个
#
# 执行特征工程...
#   → 商圈独热编码...
#   → 提取数值特征...
#   → 提取设施特征...
#   → 构建组合特征...
#
#   ✓ 特征工程完成
#   ✓ 特征维度: 38
#   ✓ 数值特征: 9
#   ✓ 设施特征: 10
#   ✓ 商圈特征: 15
#   ✓ 训练样本: 4821 条
```

### 从MySQL加载（备选）

```bash
# 当Hive不可用时，从MySQL加载
python scripts/train_xgboost_model.py --source mysql

# 输出示例:
# ============================================================
# XGBoost价格预测模型训练
# ============================================================
#
# 数据源: MYSQL
# 目标: tujia_dw.dwd_listing_details (Hive清洗后的明细数据)
# ============================================================
#
# 从MySQL加载数据...
#   ✓ 从MySQL加载 4937 条记录
```

### 命令行参数

```bash
python scripts/train_xgboost_model.py --help

# 输出:
# usage: train_xgboost_model.py [-h] [--source {hive,mysql}] [--output OUTPUT]
#
# XGBoost价格预测模型训练
#
# optional arguments:
#   -h, --help            show this help message and exit
#   --source {hive,mysql}, -s {hive,mysql}
#                         数据源选择: hive (推荐,默认) 或 mysql (备选)
#   --output OUTPUT, -o OUTPUT
#                         模型输出目录 (默认: models/)
#
# 示例:
#     python scripts/train_xgboost_model.py              # 从Hive加载（默认）
#     python scripts/train_xgboost_model.py --source hive    # 从Hive加载
#     python scripts/train_xgboost_model.py --source mysql   # 从MySQL加载
#
# 说明:
#     推荐从Hive DWD层加载，数据已经过清洗和标准化处理。
#     如果Hive连接失败，会自动回退到MySQL数据源。
```

## 📁 输出文件

训练完成后，会在 `models/` 目录生成以下文件：

| 文件 | 说明 |
|------|------|
| `xgboost_price_model_YYYYMMDD_HHMMSS.pkl` | 时间戳版本模型文件 |
| `xgboost_price_model_latest.pkl` | 最新模型（始终指向最新版本） |
| `feature_names_YYYYMMDD_HHMMSS.json` | 特征名列表 |
| `model_metrics_YYYYMMDD_HHMMSS.json` | 模型评估指标和元数据 |
| `feature_importance_YYYYMMDD_HHMMSS.json` | 特征重要性分析 |

### 模型元数据示例

```json
{
  "metrics": {
    "mae": 35.2,      // 平均绝对误差
    "rmse": 48.5,     // 均方根误差
    "r2": 0.8524,     // R² 决定系数
    "mape": 12.3      // 平均绝对百分比误差
  },
  "trained_at": "2026-03-17T14:30:00",
  "model_type": "XGBoost",
  "data_source": "hive",              // 数据来源
  "hive_table": "tujia_dw.dwd_listing_details",  // Hive表名
  "feature_count": 38,                // 特征维度
  "district_count": 15,               // 商圈数量
  "training_info": {
    "algorithm": "XGBRegressor",
    "objective": "reg:squarederror",
    "eval_metric": "rmse"
  }
}
```

## 🔧 特征工程说明

### 特征分类

| 特征类别 | 特征数量 | 来源 | 说明 |
|----------|----------|------|------|
| **区域位置** | 15 | Hive DWD | 商圈独热编码 (district_xxx) |
| **房屋户型** | 2 | Hive DWD | bedroom_count, bathroom_count |
| **房屋面积** | 1 | Hive DWD | area_sqm |
| **设施配置** | 10 | Hive DWD | has_projector, has_bathtub 等 |
| **评分热度** | 3 | Hive DWD | rating, comment_count, heat_score |
| **组合特征** | 3 | 训练脚本 | facility_count, price_per_area, price_per_bedroom |

### 特征重要性输出示例

```
📊 价格影响因素排名 (基于Hive DWD层清洗数据):
--------------------------------------------------
  1. 区域位置   | ██████████████████████████████  42.5%
  2. 房屋面积   | ██████████████                  18.2%
  3. 设施配置   | ██████████                      12.8%
  4. 房屋户型   | ███████                          9.5%
  5. 评分热度   | █████                            6.8%
  6. 价格特征   | ██                               3.2%
--------------------------------------------------

🔝 Top 10 重要特征:
--------------------------------------------------
   1. 商圈:江汉路            0.1256
   2. 商圈:楚河汉街          0.0987
   3. area_sqm               0.0892
   4. 商圈:光谷              0.0765
   5. bedroom_count          0.0654
   6. 浴缸                   0.0543
   7. 投影                   0.0487
   8. heat_score             0.0421
   9. 商圈:黄鹤楼            0.0389
  10. facility_count         0.0356
--------------------------------------------------
```

## 📊 数据对比

### Hive DWD vs MySQL raw_listings

| 对比项 | Hive DWD层 | MySQL raw_listings |
|--------|------------|-------------------|
| **数据状态** | 已清洗 | 原始数据 |
| **价格过滤** | 已过滤异常值 | 需要过滤 |
| **等级分类** | 已预计算 | 需要计算 |
| **设施统计** | 已统计 | 需要统计 |
| **数据质量** | 质量分>=50 | 可能包含低质量数据 |
| **加载速度** | 稍慢（需连接Hive） | 快（本地MySQL） |
| **扩展性** | 好（分布式） | 一般（单机） |
| **毕设展示** | ✅ 体现Hive价值 | 基础功能 |

## 🎯 毕设亮点

1. **完整的数据仓库流程**
   - 数据从ODS → DWD → DWS → ADS的分层处理
   - 训练数据从DWD层加载，体现数据清洗的价值

2. **Hive与机器学习结合**
   - Hive负责大数据清洗和特征工程
   - Python负责模型训练和推理
   - 展示离线数据仓库与在线ML的协作

3. **可追溯的数据血缘**
   - 模型元数据记录数据来源（Hive表名）
   - 特征重要性可以映射回Hive字段
   - 便于模型效果分析和问题定位

## 📝 注意事项

1. **Hive连接失败自动回退**
   - 如果Hive连接失败，会自动从MySQL加载
   - 控制台会显示警告信息

2. **数据量要求**
   - 训练需要至少100条有效数据
   - 少于100条会报错退出

3. **模型质量**
   - R² > 0.7: 模型质量良好 ✓
   - R² > 0.5: 模型质量一般 ⚠
   - R² < 0.5: 模型质量较差 ✗

## 🔗 相关文档

- `docs/HIVE_GUIDE.md` - Hive数据仓库使用指南
- `sql/hive_load_data.hql` - Hive表结构和清洗SQL
- `scripts/hive_docker_import.py` - Hive数据导入脚本
- `app/services/hive_service.py` - Hive查询服务
