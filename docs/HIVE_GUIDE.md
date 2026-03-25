# Hive数据仓库使用指南

## 📋 概述

本系统使用双层数据架构：
- **MySQL**: 在线事务处理(OLTP)，存储用户数据、收藏夹等
- **Hive**: 离线数据分析(OLAP)，存储房源大数据，用于统计分析和机器学习

## 🏗️ 数据分层架构

```
┌─────────────────────────────────────────────────────────┐
│  数据源层                                                │
│  tujia_calendar_data.json → MySQL → Hive                │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  ODS层 (原始数据层)                                      │
│  ├─ ods_listings: 房源原始数据 (4937条)                  │
│  └─ ods_price_calendar: 价格日历 (94万条)               │
│  用途: 贴源存储，保留原始数据                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼ (清洗转换)
┌─────────────────────────────────────────────────────────┐
│  DWD层 (明细数据层)                                      │
│  ├─ dwd_listing_details: 清洗后的房源明细                │
│  处理: 价格异常过滤、等级分类、设施统计                  │
│  用途: 统一数据标准，供上层使用                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼ (聚合统计)
┌─────────────────────────────────────────────────────────┐
│  DWS层 (汇总数据层)                                      │
│  ├─ dws_district_stats: 商圈统计指标                     │
│  ├─ dws_facility_analysis: 设施溢价分析                 │
│  └─ dws_price_distribution: 价格分布                    │
│  用途: 预计算统计指标，加速查询                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼ (业务应用)
┌─────────────────────────────────────────────────────────┐
│  ADS层 (应用数据层)                                      │
│  ├─ ads_price_opportunities: 价格洼地房源               │
│  └─ ads_roi_ranking: 投资收益率排名                     │
│  用途: 直接支撑API查询                                   │
└─────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

数仓脚本 [`sql/hive_load_data.hql`](../sql/hive_load_data.hql) 按 **四层** 顺序执行：**ODS → DWD → DWS → ADS**（与上文架构图一致）。Docker 单机使用本地 `file:///` 作为 warehouse，重复跑脚本前会自动清理 DWD/DWS/ADS 目录，避免 ORC 分区残留导致 `MoveTask rename` 失败（可用 `python scripts/hive_docker_import.py --no-clean` 关闭清理）。

### 前提条件
- Docker Desktop 已启动
- MySQL 中已有 `listings`、`price_calendars`（与线上一致即可）

### 1. 从 MySQL 导出 Hive ODS 用 TSV

在仓库根目录 `Tujia-backend` 下：

```bash
python scripts/export_mysql_for_hive.py
```

生成无表头制表符文件：`data/hive_import/listings_for_hive.tsv`、`price_calendar_for_hive.tsv`。

### 2. 启动容器并执行四层建表与导入

```bash
docker compose -f docker-compose-hive.yml up -d
python scripts/hive_docker_import.py --skip-up --skip-schema-init
```

首次在本机 PostgreSQL 元库为空时，请**不要**加 `--skip-schema-init`，直接：

```bash
python scripts/hive_docker_import.py
```

脚本会执行 `schematool -initSchema` 并重启 metastore / hiveserver2。容器已启动且元数据已初始化时，用 `--skip-up --skip-schema-init` 仅重跑 HQL 即可。

### 3. 验证数据

```bash
# 进入 Hive 容器（容器名为 hive-server）
docker exec -it hive-server hive

# 查看数据库
hive> SHOW DATABASES;
OK
default
tujia_dw

# 使用数据仓库
hive> USE tujia_dw;

# 查看表
hive> SHOW TABLES;
OK
ods_listings
ods_price_calendar
dwd_listing_details
dws_district_stats
dws_facility_analysis
ads_price_opportunities
...

# 查询房源数量
hive> SELECT COUNT(*) FROM ods_listings;
4937

# 查看商圈统计
hive> SELECT district, avg_price, total_listings
      FROM dws_district_stats
      WHERE dt='2026-03-17'
      ORDER BY avg_price DESC
      LIMIT 10;
```

## 📊 常用查询示例

### 1. 商圈平均价格排名

```sql
SELECT
    district,
    avg_price,
    total_listings,
    avg_rating
FROM dws_district_stats
WHERE dt='2026-03-17'
ORDER BY avg_price DESC
LIMIT 10;
```

### 2. 设施溢价分析

```sql
SELECT
    facility_name,
    avg_price_with,
    avg_price_without,
    price_premium,
    CONCAT(premium_rate, '%') as premium_rate
FROM dws_facility_analysis
WHERE dt='2026-03-17'
ORDER BY price_premium DESC;
```

### 3. 价格洼地房源

```sql
SELECT
    unit_id,
    district,
    current_price,
    predicted_price,
    gap_rate,
    reason
FROM ads_price_opportunities
WHERE dt='2026-03-17'
ORDER BY gap_rate DESC
LIMIT 20;
```

### 4. 按卧室数量统计

```sql
SELECT
    bedroom_count,
    COUNT(*) as listing_count,
    ROUND(AVG(price), 2) as avg_price
FROM dwd_listing_details
WHERE dt='2026-03-17'
GROUP BY bedroom_count
ORDER BY bedroom_count;
```

## 🔧 手动执行 Hive 脚本

`docker-compose-hive.yml` 已将 `./sql` 挂载为容器内 `/opt/hive/data/sql`，`./data/hive_import` 挂载为 `/opt/hive/data/hive_import`。请先本地执行 `python scripts/export_mysql_for_hive.py` 生成 TSV，再在容器内执行（容器名 **`hive-server`**）：

```bash
docker exec -T hive-server mkdir -p /user/hive/warehouse
docker exec -T hive-server bash -lc 'rm -rf /user/hive/warehouse/tujia_dw.db/dwd_listing_details /user/hive/warehouse/tujia_dw.db/dws_* /user/hive/warehouse/tujia_dw.db/ads_*'
docker exec -T hive-server hive -hiveconf process_date=2026-03-24 -f /opt/hive/data/sql/hive_load_data.hql
```

## 🐍 Python查询Hive

```python
from pyhive import hive

# 连接Hive
conn = hive.Connection(
    host='localhost',
    port=10000,
    database='tujia_dw',
    auth='NOSASL',
)

# 查询数据
cursor = conn.cursor()
cursor.execute("""
    SELECT district, avg_price, total_listings
    FROM dws_district_stats
    WHERE dt='2026-03-17'
""")

for row in cursor.fetchall():
    print(row)
```

## 📝 数据更新流程

当有新数据时：

```bash
# 1. 重新从 MySQL 导出 TSV
python scripts/export_mysql_for_hive.py

# 2. 重新导入 Hive（四层全量）
python scripts/hive_docker_import.py --skip-up --skip-schema-init

# 或指定分区日期
# python scripts/hive_docker_import.py --skip-up --skip-schema-init --date 2026-03-18
```

## 🎯 毕设亮点

1. **完整的数据仓库分层**: ODS/DWD/DWS/ADS 四层架构
2. **数据清洗流程**: 异常值过滤、等级分类、特征提取
3. **预计算统计**: 商圈统计、设施溢价、价格分布
4. **业务应用层**: 价格洼地挖掘、ROI排名
5. **支持增量更新**: 按日期分区，可每日更新

## 📚 参考文档

- Hive官方文档: https://hive.apache.org/
- 数据仓库理论: Kimball维度建模
- 本项目PRD: docs/PRD.md
