# 房源场景标签：弱监督 + TF-IDF + 多标签逻辑回归

本文说明 **`listings.scene_scores`**、**`listings.nearest_hospital_km`** 的含义、**八类**场景标签、医院 POI 弱监督与训练流水线，以及**在线推荐是否使用**。

## 是否已经在使用

| 环节 | 是否使用 | 说明 |
|------|----------|------|
| **离线训练** | 是 | 运行 `python scripts/listing_scene_pipeline.py` 时，用 MySQL 中房源文本训练模型，并将每套房的概率字典写回 **`listings.scene_scores`**。 |
| **API 请求路径** | 否（不实时推理） | **不在**每次 `/api/recommend` 请求里加载 `joblib` 做 TF-IDF 推理；线上只读库中已存好的 JSON。 |
| **条件推荐打分** | 是（在已回写的前提下） | **策略 1（条件匹配）**：请求带 `travel_purpose`（含登录用户由问卷注入、经 `travel_purpose_for_condition_recommend` 转为英文 key）时，在综合分上叠加 **场景概率加分** 与 **医疗距离加分**（见下两行）。 |
| **`scene_scores` 加分** | 读库 | `scene_scores` 为有效 JSON 时增加 **`0.03 × scene_scores[travel_purpose]`**（概率截断在 \([0,1]\)）；缺失键或列为空则该项为 0。 |
| **`nearest_hospital_km` 加分** | 读库 | 仅 **`travel_purpose=medical`** 时生效：按库中距离加分（≤2km 满幅、2–5km 线性衰减、≥5km 为 0；公式见下文「医疗目的距离加分」）。**不在线**重算 POI。列为 `NULL` 则该项为 0。 |
| **`nearest_hospital_km` 写入** | 离线 | 流水线根据 [`data/hospital_poi_wuhan.json`](../data/hospital_poi_wuhan.json) 与房源经纬度 **Haversine** 写回该列。 |

结论：**`scene_scores` 与 `nearest_hospital_km` 均离线入库；推荐只读库加分（含医疗目的距离项），不在线跑 sklearn、不在线算医院距离。** 距离同时参与弱标签 `medical`（见下）。

## 提炼的标签是什么（与前端「出行目的」一致）

多标签共 **8 个维度**，键名为英文，与 `GET /api/recommend` 的 `travel_purpose` 及问卷中文（经 `recommend_travel` 映射）一致：

| 键名 (`travel_purpose`) | 含义（产品文案） | 问卷中文（存用户表时） |
|-------------------------|------------------|-------------------------|
| `couple` | 情侣出游 | 情侣 |
| `family` | 家庭亲子 | 家庭 |
| `business` | 商务差旅 | 商务 |
| `exam` | 学生考研 | 考研 |
| `team_party` | 团建聚会 | 团建聚会 |
| `medical` | 医疗陪护 | 医疗陪护 |
| `pet_friendly` | 宠物友好 | 宠物友好 |
| `long_stay` | 长租 | 长租 |

每条房源的 `scene_scores` 为 JSON 对象（**增加新标签后须重训流水线**，否则旧行可能只有前四维键）：

```json
{"couple":0.1,"family":0.2,"business":0.05,"exam":0.02,"team_party":0.3,"medical":0.01,"pet_friendly":0.15,"long_stay":0.08}
```

表示模型对「该房更偏哪类场景」的估计概率（各维独立二分类经 OneVsRest 后的正类概率，**不必和为 1**）。弱监督词表版本见 `WEAK_RULE_VERSION`（当前为 `4`：在 v3 词表基础上增加 **医院 POI 距离≤2km → `medical` 弱标签为 1**（与文本关键词 OR）；改词表或 POI 后须重训流水线）。

**弱监督训练标签**（0/1）主要由关键词在拼接文本上命中生成；**`medical`** 另与 [`app/ml/hospital_poi.py`](../app/ml/hospital_poi.py) 计算的最近医院距离叠加（`MEDICAL_HOSPITAL_PROXIMITY_KM`，默认 2km）。词表维护在 [`app/ml/listing_scene_weak_labels.py`](../app/ml/listing_scene_weak_labels.py) 的 `KEYWORDS_*`；医院点位维护在 `data/hospital_poi_wuhan.json`（可增删城市或换文件路径需在流水线中调整 `HOSPITAL_POI_PATH`）。版本号 `WEAK_RULE_VERSION` 会写入 `models/listing_scene_tfidf_meta.json`。

## 输入文本（特征来源）

与入库展示一致，每条房源拼接：

- `listings.title`
- `listings.house_tags` 解析出的可读标签（与 [`app/ml/house_tags_text.py`](../app/ml/house_tags_text.py) 的 `parse_house_tags` 一致）
- `listings.comment_brief`

弱标签中的地理信号另读取 **`listings.latitude` / `listings.longitude`**（与 POI 算距）。

**不**依赖整文件加载仓库根目录的 `tujia_calendar_data*.json`；以当前 **MySQL `listings`** 为准。

## 模型与方法（论文可写）

- **特征**：`TfidfVectorizer`；默认 **`--mode word`** 使用 **jieba** 分词（analyzer 定义在 [`app/ml/listing_scene_text.py`](../app/ml/listing_scene_text.py)，便于 `joblib` 反序列化）；可选 **`--mode char`** 字 n-gram，无分词依赖。
- **分类器**：`sklearn.multiclass.OneVsRestClassifier` + `LogisticRegression(class_weight='balanced', solver='saga')`。
- **评估**：随机划分验证集，输出 Hamming loss、micro/macro F1（见训练日志与 `listing_scene_tfidf_meta.json`）。

## 一键执行

在 **`Tujia-backend`** 目录：

```bash
pip install -r requirements.txt
python scripts/listing_scene_pipeline.py
```

- 默认：**训练 →** 写入 `models/listing_scene_tfidf.joblib` 与 `models/listing_scene_tfidf_meta.json` **→** 批量更新 `listings.scene_scores`、**`nearest_hospital_km`**、**`nearest_hospital_name`**。
- 若表上缺少上述列，脚本在需要写库时会尝试 **自动 `ALTER TABLE`**（亦提供 [`sql/add_listing_scene_scores.sql`](../sql/add_listing_scene_scores.sql)、[`sql/add_listing_nearest_hospital_km.sql`](../sql/add_listing_nearest_hospital_km.sql)、[`sql/add_listing_nearest_hospital_name.sql`](../sql/add_listing_nearest_hospital_name.sql) 供手工执行）。
- 其它参数：`--dry-run`、`--skip-apply`、`--skip-train`、`--ensure-column` 见脚本 `--help` 与文件头注释。

**数据更新后**建议重跑本脚本，使推荐中的场景加分与最新文案一致。

## 条件推荐：医疗目的距离加分（实现口径）

与弱标签常量 **`MEDICAL_HOSPITAL_PROXIMITY_KM`（默认 2km）** 对齐，代码常量见 `recommender` 中 `_MEDICAL_DISTANCE_BONUS_MAX`、`_MEDICAL_DISTANCE_BONUS_FAR_KM`（默认 5km）：

- 设 \(d\) 为库中 `nearest_hospital_km`（无效则不加）。
- 若 \(d \le 2\)：加分 **`_MEDICAL_DISTANCE_BONUS_MAX`**（当前 **0.018**）。
- 若 \(2 < d < 5\)：加分 **线性衰减** 至 0，即 `0.018 × (5 - d) / 3`。
- 若 \(d \ge 5\)：距离加分为 0。

该加分与 **`0.03 × scene_scores['medical']`** **相加**，均进入条件匹配的总分（仍不加载 joblib）。推荐结果项与房源列表/详情 schema 中可选返回 **`nearest_hospital_km`**、**`nearest_hospital_name`**（最近 POI 的医院名称，来自 `hospital_poi_wuhan.json`）。推荐理由在医疗目的下优先展示 **「距「医院名」约 x km」**（名称过长时在文案中截断，完整名见接口字段）。

## 与推荐文档的关系

条件匹配与 API 形态详见 [`THESIS_RECOMMENDATION_SYSTEM.md`](THESIS_RECOMMENDATION_SYSTEM.md)；本节补充 **场景概率 + 医院距离字段** 的离线写入与在线只读使用方式。
