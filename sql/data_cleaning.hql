-- ============================================
-- 途家民宿数据清洗 - Hive SQL
-- 毕业设计：基于Hive的数据仓库构建与价格预测
-- ============================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS tujia_dw
COMMENT '途家民宿数据仓库'
LOCATION '/user/hive/warehouse/tujia_dw.db';

USE tujia_dw;

-- ============================================
-- 第一步：创建ODS层原始数据表
-- ============================================

-- 1.1 房源基础信息表（4937条原始数据）
CREATE TABLE IF NOT EXISTS ods_listings (
    unit_id STRING COMMENT '房源唯一ID',
    title STRING COMMENT '房源标题',
    city STRING COMMENT '城市',
    district STRING COMMENT '商圈/区域',
    address STRING COMMENT '详细地址',
    final_price DECIMAL(10,2) COMMENT '最终价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    rating DECIMAL(2,1) COMMENT '评分（1-5分）',
    comment_count INT COMMENT '评论数',
    favorite_count STRING COMMENT '收藏数（原始字符串）',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    cover_image STRING COMMENT '封面图URL',
    tags STRING COMMENT '标签（|分隔）',
    detail_url STRING COMMENT '详情页URL',
    crawled_at STRING COMMENT '爬取时间'
) COMMENT 'ODS层-房源基础信息表'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ('skip.header.line.count'='1');

-- 1.2 房源标签表（2487条带标签数据）
CREATE TABLE IF NOT EXISTS ods_listing_tags (
    unit_id STRING COMMENT '房源ID',
    favorite_count INT COMMENT '收藏数',
    pic_count INT COMMENT '图片数量',
    facilities STRING COMMENT '设施标签（|分隔）',
    created_at STRING COMMENT '创建时间'
) COMMENT 'ODS层-房源标签表'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
TBLPROPERTIES ('skip.header.line.count'='1');

-- ============================================
-- 第二步：导入原始数据
-- ============================================

-- 导入房源基础数据
LOAD DATA LOCAL INPATH 'data/hive_import/ods_listings_raw.csv' 
OVERWRITE INTO TABLE ods_listings;

-- 导入标签数据
LOAD DATA LOCAL INPATH 'data/hive_import/ods_listing_tags_raw.csv' 
OVERWRITE INTO TABLE ods_listing_tags;

-- 验证导入
SELECT 'ODS层数据导入完成' as status;
SELECT 'ods_listings' as table_name, COUNT(*) as count FROM ods_listings;
SELECT 'ods_listing_tags' as table_name, COUNT(*) as count FROM ods_listing_tags;

-- ============================================
-- 第三步：数据清洗 - 关联两表得到核心数据（2464条）
-- ============================================

CREATE TABLE IF NOT EXISTS dwd_listings_core AS
SELECT 
    l.unit_id,
    l.title,
    l.city,
    l.district,
    l.address,
    l.final_price,
    l.original_price,
    l.rating,
    l.comment_count,
    -- 清洗收藏数（处理 '1k+' 等格式）
    CASE 
        WHEN l.favorite_count LIKE '%k%' THEN CAST(REPLACE(REPLACE(LOWER(l.favorite_count), 'k', ''), '+', '') AS INT) * 1000
        ELSE CAST(l.favorite_count AS INT)
    END as favorite_count,
    l.longitude,
    l.latitude,
    l.cover_image,
    l.tags,
    l.crawled_at,
    -- 标签表数据
    t.pic_count,
    t.facilities as detail_facilities
FROM ods_listings l
INNER JOIN ods_listing_tags t ON l.unit_id = t.unit_id
WHERE l.final_price > 0  -- 过滤无效价格
  AND l.rating > 0        -- 过滤无效评分
  AND l.district IS NOT NULL;

-- 验证核心数据
SELECT 'dwd_listings_core' as table_name, COUNT(*) as count FROM dwd_listings_core;

-- ============================================
-- 第四步：特征工程 - 从标题解析户型信息
-- ============================================

CREATE TABLE IF NOT EXISTS dwd_listings_features AS
SELECT 
    unit_id,
    title,
    city,
    district,
    address,
    final_price,
    original_price,
    rating,
    comment_count,
    favorite_count,
    longitude,
    latitude,
    pic_count,
    
    -- 从标题解析卧室数（如"3居"）
    CASE 
        WHEN title REGEXP '([0-9]+)居' THEN CAST(REGEXP_EXTRACT(title, '([0-9]+)居', 1) AS INT)
        WHEN title REGEXP '([0-9]+)室' THEN CAST(REGEXP_EXTRACT(title, '([0-9]+)室', 1) AS INT)
        ELSE 1
    END as bedroom_count,
    
    -- 从标题解析床位数（如"3床"）
    CASE 
        WHEN title REGEXP '([0-9]+)床' THEN CAST(REGEXP_EXTRACT(title, '([0-9]+)床', 1) AS INT)
        ELSE 1
    END as bed_count,
    
    -- 从标题解析卫生间数（如"2卫"）
    CASE 
        WHEN title REGEXP '([0-9]+)卫' THEN CAST(REGEXP_EXTRACT(title, '([0-9]+)卫', 1) AS INT)
        ELSE 1
    END as bathroom_count,
    
    -- 计算折扣率
    CASE 
        WHEN original_price > 0 THEN ROUND((original_price - final_price) / original_price, 2)
        ELSE 0
    END as discount_rate,
    
    -- 设施特征（从标题判断）
    CASE WHEN title LIKE '%投影%' OR title LIKE '%投屏%' OR title LIKE '%百寸%' THEN 1 ELSE 0 END as has_projector,
    CASE WHEN title LIKE '%厨房%' OR title LIKE '%做饭%' OR title LIKE '%可烹饪%' THEN 1 ELSE 0 END as has_kitchen,
    CASE WHEN title LIKE '%WiFi%' OR title LIKE '%wifi%' OR title LIKE '%无线%' THEN 1 ELSE 0 END as has_wifi,
    CASE WHEN title LIKE '%空调%' THEN 1 ELSE 0 END as has_ac,
    CASE WHEN title LIKE '%洗衣机%' OR title LIKE '%洗衣%' THEN 1 ELSE 0 END as has_washer,
    CASE WHEN title LIKE '%浴缸%' THEN 1 ELSE 0 END as has_bathtub,
    CASE WHEN title LIKE '%智能锁%' OR title LIKE '%密码锁%' THEN 1 ELSE 0 END as has_smart_lock,
    CASE WHEN title LIKE '%停车%' OR title LIKE '%车位%' THEN 1 ELSE 0 END as has_parking,
    CASE WHEN title LIKE '%阳台%' THEN 1 ELSE 0 END as has_balcony,
    
    -- 设施总数
    (CASE WHEN title LIKE '%投影%' OR title LIKE '%投屏%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%厨房%' OR title LIKE '%做饭%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%WiFi%' OR title LIKE '%wifi%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%空调%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%洗衣机%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%浴缸%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%智能锁%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%停车%' THEN 1 ELSE 0 END +
     CASE WHEN title LIKE '%阳台%' THEN 1 ELSE 0 END
    ) as facility_count,
    
    -- 热度分（评论数作为热度指标）
    comment_count as heat_score
    
FROM dwd_listings_core;

-- 验证特征表
SELECT 'dwd_listings_features' as table_name, COUNT(*) as count FROM dwd_listings_features;

-- ============================================
-- 第五步：DWS层 - 商圈汇总统计
-- ============================================

CREATE TABLE IF NOT EXISTS dws_district_stats AS
SELECT 
    district,
    COUNT(*) as total_listings,
    ROUND(AVG(final_price), 2) as avg_price,
    ROUND(PERCENTILE_APPROX(final_price, 0.5), 2) as median_price,
    MIN(final_price) as min_price,
    MAX(final_price) as max_price,
    ROUND(STDDEV(final_price), 2) as price_std,
    ROUND(AVG(rating), 2) as avg_rating,
    ROUND(AVG(comment_count), 2) as avg_comment_count,
    ROUND(AVG(bedroom_count), 1) as avg_bedroom_count,
    ROUND(AVG(facility_count), 1) as avg_facility_count
FROM dwd_listings_features
GROUP BY district;

-- 验证汇总表
SELECT 'dws_district_stats' as table_name, COUNT(*) as count FROM dws_district_stats;

-- ============================================
-- 第六步：导出训练数据（用于XGBoost模型）
-- ============================================

CREATE TABLE IF NOT EXISTS ads_training_data AS
SELECT 
    unit_id,
    district,
    final_price as target_price,
    rating,
    comment_count,
    favorite_count,
    bedroom_count,
    bed_count,
    bathroom_count,
    facility_count,
    discount_rate,
    has_projector,
    has_kitchen,
    has_wifi,
    has_ac,
    has_washer,
    has_bathtub,
    has_smart_lock,
    has_parking,
    has_balcony,
    heat_score,
    -- 商圈平均价格（用于特征）
    d.avg_price as district_avg_price,
    -- 价格相对商圈的位置（0-1标准化）
    CASE 
        WHEN d.avg_price > 0 THEN ROUND((f.final_price - d.min_price) / (d.max_price - d.min_price), 2)
        ELSE 0.5
    END as price_position_in_district
FROM dwd_listings_features f
LEFT JOIN dws_district_stats d ON f.district = d.district;

-- 验证训练数据
SELECT 'ads_training_data' as table_name, COUNT(*) as count FROM ads_training_data;

-- 查看样本
SELECT * FROM ads_training_data LIMIT 5;

-- ============================================
-- 数据质量报告
-- ============================================

SELECT '=== 数据清洗报告 ===' as report;

SELECT 
    '原始数据' as stage,
    'ods_listings' as table_name,
    COUNT(*) as record_count,
    '4937条原始房源' as description
FROM ods_listings
UNION ALL
SELECT 
    '原始数据' as stage,
    'ods_listing_tags' as table_name,
    COUNT(*) as record_count,
    '2487条带标签房源' as description
FROM ods_listing_tags
UNION ALL
SELECT 
    '清洗后核心数据' as stage,
    'dwd_listings_core' as table_name,
    COUNT(*) as record_count,
    '关联后的核心房源' as description
FROM dwd_listings_core
UNION ALL
SELECT 
    '特征工程' as stage,
    'dwd_listings_features' as table_name,
    COUNT(*) as record_count,
    '带特征的房源数据' as description
FROM dwd_listings_features
UNION ALL
SELECT 
    '汇总统计' as stage,
    'dws_district_stats' as table_name,
    COUNT(*) as record_count,
    '商圈汇总统计' as description
FROM dws_district_stats
UNION ALL
SELECT 
    '训练数据' as stage,
    'ads_training_data' as table_name,
    COUNT(*) as record_count,
    '模型训练数据集' as description
FROM ads_training_data;
