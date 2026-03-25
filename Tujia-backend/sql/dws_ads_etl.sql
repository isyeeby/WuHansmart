-- DWS层：商圈统计
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

-- ADS层：房源展示数据
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
    '' as cover_image,
    house_tags,
    comment_brief,
    bedroom_count,
    bed_count,
    longitude,
    latitude
FROM tujia_dwd.dwd_listings;

-- ADS层：模型训练数据
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
    CASE WHEN l.house_tags LIKE '%近地铁%' THEN 1 ELSE 0 END as has_metro,
    CASE WHEN l.house_tags LIKE '%可做饭%' THEN 1 ELSE 0 END as has_kitchen,
    CASE WHEN l.house_tags LIKE '%投影%' THEN 1 ELSE 0 END as has_projector,
    CASE WHEN l.house_tags LIKE '%洗衣机%' THEN 1 ELSE 0 END as has_washer,
    CASE WHEN l.house_tags LIKE '%智能门锁%' THEN 1 ELSE 0 END as has_smart_lock,
    CASE WHEN l.house_tags LIKE '%空调%' THEN 1 ELSE 0 END as has_air_conditioner,
    CASE WHEN l.house_tags LIKE '%浴缸%' THEN 1 ELSE 0 END as has_bathtub,
    CASE WHEN l.house_tags LIKE '%停车位%' THEN 1 ELSE 0 END as has_parking,
    CASE WHEN l.house_tags LIKE '%阳台%' OR l.house_tags LIKE '%露台%' THEN 1 ELSE 0 END as has_balcony,
    d.avg_price as district_avg_price
FROM tujia_dwd.dwd_listings l
LEFT JOIN tujia_dws.dws_district_stats d ON l.district = d.district AND l.trade_area = d.trade_area;
