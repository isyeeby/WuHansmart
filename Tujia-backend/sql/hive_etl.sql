-- ============================================================
-- Hive ETL脚本 - 数据清洗与分层处理
-- 执行顺序: ODS -> DWD -> DWS -> ADS
-- ============================================================

-- ============================================================
-- 第1步：导入ODS层原始数据
-- ============================================================

-- 导入房源基础信息
LOAD DATA LOCAL INPATH '/data/hive_import/ods_listings.csv'
OVERWRITE INTO TABLE tujia_ods.ods_listings;

-- 导入房源详情标签
LOAD DATA LOCAL INPATH '/data/hive_import/ods_listing_details.csv'
OVERWRITE INTO TABLE tujia_ods.ods_listing_details;

-- 导入价格日历
LOAD DATA LOCAL INPATH '/data/hive_import/ods_price_calendar.csv'
OVERWRITE INTO TABLE tujia_ods.ods_price_calendar;

-- ============================================================
-- 第2步：DWD层 - 数据清洗与关联
-- 从4937条房源和2487条标签中提取2464条核心数据
-- ============================================================

INSERT OVERWRITE TABLE tujia_dwd.dwd_listings
SELECT 
    l.unit_id,
    l.title,
    l.city,
    l.district,
    l.address,
    l.final_price,
    l.original_price,
    CASE 
        WHEN l.original_price > 0 
        THEN ROUND((l.original_price - l.final_price) / l.original_price, 4) 
        ELSE 0 
    END as discount_rate,
    l.rating,
    l.comment_count,
    -- 清洗收藏数（处理k+格式）
    CAST(
        CASE 
            WHEN l.favorite_count LIKE '%k%' 
            THEN CAST(REGEXP_REPLACE(REGEXP_REPLACE(LOWER(l.favorite_count), 'k', ''), '\\+', '') AS DOUBLE) * 1000
            ELSE CAST(l.favorite_count AS DOUBLE)
        END AS INT
    ) as favorite_count,
    l.longitude,
    l.latitude,
    -- 从标题解析户型信息
    COALESCE(CAST(REGEXP_EXTRACT(l.title, '([0-9]+)居', 1) AS INT), 1) as bedroom_count,
    COALESCE(CAST(REGEXP_EXTRACT(l.title, '([0-9]+)床', 1) AS INT), 1) as bed_count,
    COALESCE(CAST(REGEXP_EXTRACT(l.title, '([0-9]+)卫', 1) AS INT), 1) as bathroom_count,
    d.house_name,
    d.pic_count,
    d.house_pics,
    d.video_url,
    d.house_tags,
    d.comment_overall,
    d.comment_brief,
    d.comment_total_count,
    d.area_name,
    d.trade_area
FROM tujia_ods.ods_listings l
INNER JOIN tujia_ods.ods_listing_details d ON l.unit_id = d.unit_id
WHERE l.final_price > 0 
  AND l.rating > 0
  AND l.district IS NOT NULL;

-- ============================================================
-- 第3步：DWS层 - 汇总统计
-- ============================================================

-- 商圈统计
INSERT OVERWRITE TABLE tujia_dws.dws_district_stats
SELECT 
    district,
    trade_area,
    COUNT(*) as listing_count,
    ROUND(AVG(final_price), 2) as avg_price,
    ROUND(AVG(rating), 2) as avg_rating,
    ROUND(AVG(favorite_count), 2) as avg_favorite_count,
    ROUND(AVG(comment_total_count), 2) as avg_comment_count,
    ROUND(AVG(bedroom_count), 1) as avg_bedroom_count,
    MIN(final_price) as min_price,
    MAX(final_price) as max_price
FROM tujia_dwd.dwd_listings
GROUP BY district, trade_area;

-- 标签统计（需要先展开标签数组）
-- 注意：这里使用LATERAL VIEW展开JSON数组
INSERT OVERWRITE TABLE tujia_dws.dws_tag_stats
SELECT 
    tag_text,
    CASE 
        WHEN tag_text IN ('欧美风', '网红INS风', '现代风', '日式风', '中式风') THEN 'style'
        WHEN tag_text IN ('可做饭', '有洗衣机', '全天热水', '智能门锁', '冷暖空调', '有冰箱', '吹风机', '有麻将机') THEN 'facility'
        WHEN tag_text IN ('近地铁', '付费停车位', '超市/菜场', '近景点') THEN 'location'
        WHEN tag_text IN ('团建会议', '大客厅', '管家服务', '立即确认') THEN 'service'
        ELSE 'other'
    END as tag_category,
    COUNT(*) as listing_count,
    ROUND(AVG(final_price), 2) as avg_price,
    ROUND(AVG(rating), 2) as avg_rating,
    ROUND(AVG(favorite_count), 2) as avg_favorite_count
FROM tujia_dwd.dwd_listings
LATERAL VIEW EXPLODE(
    SPLIT(REGEXP_REPLACE(REGEXP_REPLACE(house_tags, '\\[|\\]', ''), '\\},\\{', '\\}\\|\\{'), '\\|')
) t AS tag_json
LATERAL VIEW EXPLODE(
    SPLIT(REGEXP_EXTRACT(tag_json, '"tagText":\\{"text":"([^"]+)"', 1), ',')
) t2 AS tag_text
WHERE tag_text != ''
GROUP BY tag_text;

-- 价格趋势（按月汇总）
INSERT OVERWRITE TABLE tujia_dws.dws_price_trend
SELECT 
    unit_id,
    SUBSTR(calendar_date, 1, 7) as month,
    ROUND(AVG(price), 2) as avg_month_price,
    MIN(price) as min_price,
    MAX(price) as max_price,
    COUNT(*) as days_count
FROM tujia_ods.ods_price_calendar
WHERE can_booking = true
GROUP BY unit_id, SUBSTR(calendar_date, 1, 7);

-- ============================================================
-- 第4步：ADS层 - 应用数据
-- ============================================================

-- 房源展示数据
INSERT OVERWRITE TABLE tujia_ads.ads_listing_display
SELECT 
    unit_id,
    title,
    district,
    trade_area,
    final_price,
    original_price,
    discount_rate,
    rating,
    favorite_count,
    pic_count,
    -- 提取第一张图片作为封面
    CASE 
        WHEN house_pics IS NOT NULL AND house_pics != ''
        THEN REGEXP_EXTRACT(house_pics, '"url":"([^"]+)"', 1)
        ELSE ''
    END as cover_image,
    house_tags,
    comment_brief,
    bedroom_count,
    bed_count,
    longitude,
    latitude
FROM tujia_dwd.dwd_listings;

-- 模型训练数据
INSERT OVERWRITE TABLE tujia_ads.ads_training_data
SELECT 
    l.unit_id,
    l.district,
    l.final_price as target_price,
    l.rating,
    l.comment_count,
    l.favorite_count,
    l.bedroom_count,
    l.bed_count,
    l.bathroom_count,
    l.pic_count,
    l.discount_rate,
    -- 设施特征（从标签中提取）
    CASE WHEN l.house_tags LIKE '%近地铁%' THEN 1 ELSE 0 END as has_metro,
    CASE WHEN l.house_tags LIKE '%可做饭%' THEN 1 ELSE 0 END as has_kitchen,
    CASE WHEN l.house_tags LIKE '%投影%' THEN 1 ELSE 0 END as has_projector,
    CASE WHEN l.house_tags LIKE '%洗衣机%' THEN 1 ELSE 0 END as has_washer,
    CASE WHEN l.house_tags LIKE '%智能门锁%' THEN 1 ELSE 0 END as has_smart_lock,
    CASE WHEN l.house_tags LIKE '%冷暖空调%' OR l.house_tags LIKE '%空调%' THEN 1 ELSE 0 END as has_air_conditioner,
    CASE WHEN l.house_tags LIKE '%浴缸%' THEN 1 ELSE 0 END as has_bathtub,
    CASE WHEN l.house_tags LIKE '%停车位%' THEN 1 ELSE 0 END as has_parking,
    CASE WHEN l.house_tags LIKE '%阳台%' OR l.house_tags LIKE '%露台%' THEN 1 ELSE 0 END as has_balcony,
    -- 商圈基准价格
    d.avg_price as district_avg_price
FROM tujia_dwd.dwd_listings l
LEFT JOIN tujia_dws.dws_district_stats d 
    ON l.district = d.district AND l.trade_area = d.trade_area;

-- 推荐特征数据
INSERT OVERWRITE TABLE tujia_ads.ads_recommendation_features
SELECT 
    unit_id,
    district,
    trade_area,
    final_price,
    rating,
    favorite_count,
    bedroom_count,
    pic_count,
    house_tags,
    -- 构建特征向量JSON
    CONCAT('{"price":', final_price, 
           ',"rating":', rating, 
           ',"favorite":', favorite_count,
           ',"bedroom":', bedroom_count, '}') as feature_vector
FROM tujia_dwd.dwd_listings;

-- ============================================================
-- ETL完成 - 验证数据量
-- ============================================================

SELECT 'ODS层' as layer, '房源基础' as table_name, COUNT(*) as count FROM tujia_ods.ods_listings
UNION ALL
SELECT 'ODS层', '房源详情', COUNT(*) FROM tujia_ods.ods_listing_details
UNION ALL
SELECT 'DWD层', '清洗后房源', COUNT(*) FROM tujia_dwd.dwd_listings
UNION ALL
SELECT 'DWS层', '商圈统计', COUNT(*) FROM tujia_dws.dws_district_stats
UNION ALL
SELECT 'ADS层', '展示数据', COUNT(*) FROM tujia_ads.ads_listing_display
UNION ALL
SELECT 'ADS层', '训练数据', COUNT(*) FROM tujia_ads.ads_training_data;
