-- Hive数据仓库建表和数据导入脚本
-- 适用于: 民宿价格分析系统
-- 执行方式: hive -f sql/hive_load_data.hql

-- ============================================
-- 1. 创建数据库
-- ============================================
CREATE DATABASE IF NOT EXISTS tujia_dw
COMMENT '途家民宿数据仓库'
LOCATION '/user/hive/warehouse/tujia_dw.db';

USE tujia_dw;

-- ============================================
-- 2. ODS层 - 原始数据层 (贴源存储)
-- ============================================

-- 2.1 房源信息表
DROP TABLE IF EXISTS ods_listings;
CREATE EXTERNAL TABLE IF NOT EXISTS ods_listings (
    unit_id STRING COMMENT '房源ID',
    title STRING COMMENT '房源标题',
    district STRING COMMENT '商圈',
    address STRING COMMENT '地址',
    price DECIMAL(10,2) COMMENT '价格',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    tags STRING COMMENT '标签字符串',
    image_urls STRING COMMENT '图片URL',
    data_quality_score INT COMMENT '数据质量分',
    bedroom_count INT COMMENT '卧室数量',
    bathroom_count INT COMMENT '客厅数量',
    area_sqm INT COMMENT '面积',
    heat_score FLOAT COMMENT '热度分',
    has_projector INT COMMENT '是否有投影(0/1)',
    has_kitchen INT COMMENT '是否有厨房(0/1)',
    has_washing_machine INT COMMENT '是否有洗衣机(0/1)',
    has_bathtub INT COMMENT '是否有浴缸(0/1)',
    has_smart_lock INT COMMENT '是否有智能锁(0/1)',
    has_floor_window INT COMMENT '是否有落地窗(0/1)',
    has_ac INT COMMENT '是否有空调(0/1)',
    has_wifi INT COMMENT '是否有WiFi(0/1)',
    has_tv INT COMMENT '是否有电视(0/1)',
    has_heater INT COMMENT '是否有暖气(0/1)',
    created_at TIMESTAMP COMMENT '创建时间',
    facility_module_json STRING COMMENT 'facilityModule JSON',
    comment_module_json STRING COMMENT 'commentModule JSON',
    landlord_module_json STRING COMMENT 'landlordModule JSON'
)
COMMENT 'ODS层: 房源原始数据'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
LINES TERMINATED BY '\n'
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/tujia_dw.db/ods_listings';

-- 2.2 价格日历表
DROP TABLE IF EXISTS ods_price_calendar;
CREATE EXTERNAL TABLE IF NOT EXISTS ods_price_calendar (
    id INT COMMENT '自增ID',
    unit_id STRING COMMENT '房源ID',
    `date` STRING COMMENT '日期(YYYY-MM-DD)',
    price DECIMAL(10,2) COMMENT '当日价格',
    created_at TIMESTAMP COMMENT '创建时间'
)
COMMENT 'ODS层: 价格日历原始数据'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
LINES TERMINATED BY '\n'
STORED AS TEXTFILE
LOCATION '/user/hive/warehouse/tujia_dw.db/ods_price_calendar';

-- ============================================
-- 3. 从CSV加载数据到ODS层
-- ============================================

-- 与 docker-compose 挂载一致：宿主机 Tujia-backend/data/hive_import -> 容器内 /opt/hive/data/hive_import
-- 由 scripts/export_mysql_for_hive.py 生成无表头的 TSV（见 listings_for_hive.tsv / price_calendar_for_hive.tsv）
LOAD DATA LOCAL INPATH '/opt/hive/data/hive_import/listings_for_hive.tsv'
OVERWRITE INTO TABLE ods_listings;

LOAD DATA LOCAL INPATH '/opt/hive/data/hive_import/price_calendar_for_hive.tsv'
OVERWRITE INTO TABLE ods_price_calendar;

-- ============================================
-- 4. DWD层 - 明细数据层 (清洗和标准化)
-- ============================================

DROP TABLE IF EXISTS dwd_listing_details;
CREATE TABLE IF NOT EXISTS dwd_listing_details (
    unit_id STRING COMMENT '房源ID',
    district STRING COMMENT '商圈',
    price DECIMAL(10,2) COMMENT '价格',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    bedroom_count INT COMMENT '卧室数量',
    bathroom_count INT COMMENT '客厅数量',
    area_sqm INT COMMENT '面积',
    heat_score FLOAT COMMENT '热度分',
    price_level STRING COMMENT '价格等级(低/中/高)',
    rating_level STRING COMMENT '评分等级(低/中/高)',
    facility_count INT COMMENT '设施数量',
    has_projector INT COMMENT '是否有投影',
    has_kitchen INT COMMENT '是否有厨房',
    has_washing_machine INT COMMENT '是否有洗衣机',
    has_bathtub INT COMMENT '是否有浴缸',
    has_smart_lock INT COMMENT '是否有智能锁',
    has_floor_window INT COMMENT '是否有落地窗',
    has_ac INT COMMENT '是否有空调',
    has_wifi INT COMMENT '是否有WiFi',
    has_tv INT COMMENT '是否有电视',
    has_heater INT COMMENT '是否有暖气',
    created_at TIMESTAMP COMMENT '创建时间'
)
COMMENT 'DWD层: 清洗后的房源明细数据'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

-- 插入清洗后的数据到DWD层
INSERT OVERWRITE TABLE dwd_listing_details PARTITION (dt='${hiveconf:process_date}')
SELECT
    unit_id,
    district,
    -- 清洗异常价格
    CASE
        WHEN price IS NULL OR price <= 0 OR price > 5000 THEN NULL
        ELSE price
    END as price,
    rating,
    comment_count,
    bedroom_count,
    bathroom_count,
    area_sqm,
    heat_score,
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
    (has_projector + has_kitchen + has_washing_machine +
     has_bathtub + has_smart_lock + has_floor_window +
     has_ac + has_wifi + has_tv + has_heater) as facility_count,
    has_projector,
    has_kitchen,
    has_washing_machine,
    has_bathtub,
    has_smart_lock,
    has_floor_window,
    has_ac,
    has_wifi,
    has_tv,
    has_heater,
    created_at
FROM ods_listings
WHERE data_quality_score >= 50;  -- 只保留质量分>=50的数据

-- ============================================
-- 5. DWS层 - 汇总数据层 (统计分析)
-- ============================================

-- 5.1 商圈统计表
DROP TABLE IF EXISTS dws_district_stats;
CREATE TABLE IF NOT EXISTS dws_district_stats (
    district STRING COMMENT '商圈',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    median_price DECIMAL(10,2) COMMENT '价格中位数',
    min_price DECIMAL(10,2) COMMENT '最低价格',
    max_price DECIMAL(10,2) COMMENT '最高价格',
    std_price DECIMAL(10,2) COMMENT '价格标准差',
    total_listings INT COMMENT '房源总数',
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    avg_heat_score FLOAT COMMENT '平均热度分',
    avg_bedroom_count DECIMAL(3,1) COMMENT '平均卧室数',
    avg_area DECIMAL(6,2) COMMENT '平均面积'
)
COMMENT 'DWS层: 商圈统计指标'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

INSERT OVERWRITE TABLE dws_district_stats PARTITION (dt='${hiveconf:process_date}')
SELECT
    district,
    ROUND(AVG(price), 2) as avg_price,
    ROUND(PERCENTILE_APPROX(price, 0.5), 2) as median_price,
    MIN(price) as min_price,
    MAX(price) as max_price,
    ROUND(STDDEV(price), 2) as std_price,
    COUNT(*) as total_listings,
    ROUND(AVG(rating), 2) as avg_rating,
    ROUND(AVG(heat_score), 2) as avg_heat_score,
    ROUND(AVG(bedroom_count), 1) as avg_bedroom_count,
    ROUND(AVG(area_sqm), 2) as avg_area
FROM dwd_listing_details
WHERE dt = '${hiveconf:process_date}'
  AND price IS NOT NULL
GROUP BY district;

-- 5.2 设施溢价分析表
DROP TABLE IF EXISTS dws_facility_analysis;
CREATE TABLE IF NOT EXISTS dws_facility_analysis (
    facility_name STRING COMMENT '设施名称',
    has_count INT COMMENT '拥有的房源数',
    no_count INT COMMENT '没有的房源数',
    avg_price_with DECIMAL(10,2) COMMENT '有该设施的平均价格',
    avg_price_without DECIMAL(10,2) COMMENT '无该设施的平均价格',
    price_premium DECIMAL(10,2) COMMENT '价格溢价(元)',
    premium_rate DECIMAL(5,2) COMMENT '溢价率(%)'
)
COMMENT 'DWS层: 设施价格溢价分析'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

INSERT OVERWRITE TABLE dws_facility_analysis PARTITION (dt='${hiveconf:process_date}')
SELECT
    facility,
    SUM(has_facility) as has_count,
    SUM(1-has_facility) as no_count,
    ROUND(AVG(CASE WHEN has_facility=1 THEN price END), 2) as avg_price_with,
    ROUND(AVG(CASE WHEN has_facility=0 THEN price END), 2) as avg_price_without,
    ROUND(AVG(CASE WHEN has_facility=1 THEN price END) - AVG(CASE WHEN has_facility=0 THEN price END), 2) as price_premium,
    ROUND((AVG(CASE WHEN has_facility=1 THEN price END) - AVG(CASE WHEN has_facility=0 THEN price END)) / AVG(CASE WHEN has_facility=0 THEN price END) * 100, 2) as premium_rate
FROM (
    SELECT '投影' as facility, has_projector as has_facility, price
    FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
    UNION ALL
    SELECT '浴缸', has_bathtub, price FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
    UNION ALL
    SELECT '智能锁', has_smart_lock, price FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
    UNION ALL
    SELECT '落地窗', has_floor_window, price FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
    UNION ALL
    SELECT '厨房', has_kitchen, price FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
    UNION ALL
    SELECT '洗衣机', has_washing_machine, price FROM dwd_listing_details WHERE dt = '${hiveconf:process_date}'
) t
GROUP BY facility;

-- 5.3 价格分布表
DROP TABLE IF EXISTS dws_price_distribution;
CREATE TABLE IF NOT EXISTS dws_price_distribution (
    district STRING COMMENT '商圈',
    price_range STRING COMMENT '价格区间',
    listing_count INT COMMENT '房源数量',
    percentage DECIMAL(5,2) COMMENT '占比(%)'
)
COMMENT 'DWS层: 价格区间分布'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

INSERT OVERWRITE TABLE dws_price_distribution PARTITION (dt='${hiveconf:process_date}')
SELECT
    district,
    CASE
        WHEN price < 100 THEN '0-100'
        WHEN price < 200 THEN '100-200'
        WHEN price < 300 THEN '200-300'
        WHEN price < 500 THEN '300-500'
        ELSE '500+'
    END as price_range,
    COUNT(*) as listing_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY district), 2) as percentage
FROM dwd_listing_details
WHERE dt = '${hiveconf:process_date}'
  AND price IS NOT NULL
GROUP BY district,
    CASE
        WHEN price < 100 THEN '0-100'
        WHEN price < 200 THEN '100-200'
        WHEN price < 300 THEN '200-300'
        WHEN price < 500 THEN '300-500'
        ELSE '500+'
    END;

-- ============================================
-- 6. ADS层 - 应用数据层 (面向API查询)
-- ============================================

-- 6.1 价格洼地候选房源
DROP TABLE IF EXISTS ads_price_opportunities;
CREATE TABLE IF NOT EXISTS ads_price_opportunities (
    unit_id STRING COMMENT '房源ID',
    district STRING COMMENT '商圈',
    current_price DECIMAL(10,2) COMMENT '当前价格',
    predicted_price DECIMAL(10,2) COMMENT '预测价格',
    price_gap DECIMAL(10,2) COMMENT '价格差',
    gap_rate DECIMAL(5,2) COMMENT '价差率(%)',
    rating DECIMAL(2,1) COMMENT '评分',
    tags STRING COMMENT '标签',
    reason STRING COMMENT '推荐理由'
)
COMMENT 'ADS层: 价格洼地挖掘结果'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

-- 使用商圈均价作为简单预测值（后续用XGBoost替换）
-- 子查询 + ORDER BY：部分 Hive 版本对 INSERT 直接 ORDER BY 不友好
INSERT OVERWRITE TABLE ads_price_opportunities PARTITION (dt='${hiveconf:process_date}')
SELECT
    unit_id,
    district,
    current_price,
    predicted_price,
    price_gap,
    gap_rate,
    rating,
    tags,
    reason
FROM (
    SELECT
        d.unit_id,
        d.district,
        d.price as current_price,
        s.avg_price as predicted_price,
        s.avg_price - d.price as price_gap,
        ROUND((s.avg_price - d.price) / d.price * 100, 2) as gap_rate,
        d.rating,
        CONCAT_WS(',',
            CASE WHEN d.has_projector=1 THEN '投影' END,
            CASE WHEN d.has_bathtub=1 THEN '浴缸' END,
            CASE WHEN d.has_smart_lock=1 THEN '智能锁' END
        ) as tags,
        CONCAT('低于商圈均价', ROUND(s.avg_price - d.price, 0), '元') as reason
    FROM dwd_listing_details d
    JOIN dws_district_stats s ON d.district = s.district
    WHERE d.dt = '${hiveconf:process_date}'
      AND s.dt = '${hiveconf:process_date}'
      AND d.price IS NOT NULL
      AND d.price < s.avg_price * 0.8
) t
ORDER BY gap_rate DESC
LIMIT 100;

-- 6.2 ROI排行榜
DROP TABLE IF EXISTS ads_roi_ranking;
CREATE TABLE IF NOT EXISTS ads_roi_ranking (
    district STRING COMMENT '商圈',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    estimated_monthly_revenue DECIMAL(10,2) COMMENT '预估月收益',
    estimated_occupancy DECIMAL(5,2) COMMENT '预估入住率',
    estimated_roi DECIMAL(5,2) COMMENT '预估年化收益率(%)',
    investment_score INT COMMENT '投资评分(1-100)',
    risk_level STRING COMMENT '风险等级',
    recommendation STRING COMMENT '投资建议'
)
COMMENT 'ADS层: 投资收益率排名'
PARTITIONED BY (dt STRING)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

INSERT OVERWRITE TABLE ads_roi_ranking PARTITION (dt='${hiveconf:process_date}')
SELECT
    district,
    avg_price,
    estimated_monthly_revenue,
    estimated_occupancy,
    estimated_roi,
    investment_score,
    risk_level,
    recommendation
FROM (
    SELECT
        district,
        avg_price,
        ROUND(avg_price * 20, 2) as estimated_monthly_revenue,
        66.67 as estimated_occupancy,
        ROUND((avg_price * 20 * 12 - 50000) / 150000 * 100, 2) as estimated_roi,
        CASE
            WHEN avg_price > 300 THEN 90
            WHEN avg_price > 200 THEN 80
            WHEN avg_price > 150 THEN 70
            ELSE 60
        END as investment_score,
        CASE
            WHEN avg_price > 400 THEN '高风险'
            WHEN avg_price > 250 THEN '中风险'
            ELSE '低风险'
        END as risk_level,
        CASE
            WHEN avg_price > 300 THEN '高收益潜力，建议关注'
            WHEN avg_price > 200 THEN '稳健收益，适合投资'
            ELSE '入门级投资，风险可控'
        END as recommendation
    FROM dws_district_stats
    WHERE dt = '${hiveconf:process_date}'
) x
ORDER BY estimated_roi DESC
LIMIT 50;

-- ============================================
-- 7. 验证数据加载
-- ============================================
SELECT '数据加载完成!' as status;
SELECT CONCAT('ODS层房源数: ', COUNT(*)) as count FROM ods_listings;
SELECT CONCAT('DWD层清洗后: ', COUNT(*)) as count FROM dwd_listing_details WHERE dt='${hiveconf:process_date}';
SELECT CONCAT('商圈统计数: ', COUNT(*)) as count FROM dws_district_stats WHERE dt='${hiveconf:process_date}';
SELECT CONCAT('价格洼地数: ', COUNT(*)) as count FROM ads_price_opportunities WHERE dt='${hiveconf:process_date}';
