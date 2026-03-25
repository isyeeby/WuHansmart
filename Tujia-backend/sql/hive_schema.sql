-- ============================================
-- 途家民宿数据仓库 - Hive建表脚本
-- 分层设计：ODS -> DWD -> DWS -> ADS
-- ============================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS tujia_dw
COMMENT '途家民宿数据仓库'
LOCATION '/user/hive/warehouse/tujia_dw.db';

USE tujia_dw;

-- ============================================
-- ODS层：原始数据存储（贴源层）
-- 直接存储从爬虫获取的原始数据
-- ============================================

-- 1. 房源基础信息表（贴源）
-- 对应tujia_calendar_data_tags.json的字段
CREATE TABLE IF NOT EXISTS ods_listings (
    unit_id STRING COMMENT '房源唯一ID',
    title STRING COMMENT '房源标题（包含户型信息）',
    district STRING COMMENT '所属商圈/区域',
    address STRING COMMENT '详细地址',
    price DECIMAL(10,2) COMMENT '当前价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    rating DECIMAL(2,1) COMMENT '评分（1-5分）',
    comment_count INT COMMENT '评论数',
    tags STRING COMMENT '房源标签JSON（设施、特色等）',
    image_urls STRING COMMENT '图片URL列表',
    room_type STRING COMMENT '房型（整租/合租）',
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    max_guests INT COMMENT '最大入住人数',
    area_sqm INT COMMENT '面积（平方米）',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    subway_info STRING COMMENT '地铁信息',
    check_in_time STRING COMMENT '入住时间',
    check_out_time STRING COMMENT '退房时间',
    min_stay_days INT COMMENT '最少入住天数',
    cancellation_policy STRING COMMENT '退订政策',
    host_id STRING COMMENT '房东ID',
    host_name STRING COMMENT '房东名称',
    host_rating DECIMAL(2,1) COMMENT '房东评分',
    superhost BOOLEAN COMMENT '是否超赞房东',
    business_district STRING COMMENT '所属核心商圈',
    crawl_time TIMESTAMP COMMENT '爬取时间',
    source_url STRING COMMENT '数据来源URL'
) COMMENT 'ODS层-房源基础信息表'
PARTITIONED BY (dt STRING COMMENT '日期分区，格式yyyy-MM-dd')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZLIB');

-- 2. 房源价格日历表（贴源）
-- 对应tujia_calendar_data.json的字段
CREATE TABLE IF NOT EXISTS ods_price_calendar (
    unit_id STRING COMMENT '房源ID',
    calendar_date DATE COMMENT '日期',
    price DECIMAL(10,2) COMMENT '当日价格',
    is_available BOOLEAN COMMENT '是否可预订',
    min_stay_days INT COMMENT '当日最少入住天数',
    special_tag STRING COMMENT '特殊标签（节假日等）',
    crawl_time TIMESTAMP COMMENT '爬取时间'
) COMMENT 'ODS层-房源价格日历表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZLIB');

-- 3. 房东信息表
CREATE TABLE IF NOT EXISTS ods_hosts (
    host_id STRING COMMENT '房东ID',
    host_name STRING COMMENT '房东名称',
    host_type STRING COMMENT '房东类型（个人/机构）',
    total_listings INT COMMENT '房源总数',
    response_rate DECIMAL(5,2) COMMENT '回复率',
    response_time_minutes INT COMMENT '平均回复时间（分钟）',
    register_date DATE COMMENT '注册时间',
    host_rating DECIMAL(2,1) COMMENT '房东评分',
    verification_status STRING COMMENT '认证状态',
    crawl_time TIMESTAMP COMMENT '爬取时间'
) COMMENT 'ODS层-房东信息表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

-- ============================================
-- DWD层：明细数据层（清洗+标准化）
-- 对ODS数据进行清洗、标准化、类型转换
-- ============================================

-- 1. 房源明细表（清洗后）
CREATE TABLE IF NOT EXISTS dwd_listing_details (
    unit_id STRING COMMENT '房源ID',
    district STRING COMMENT '商圈',
    business_district STRING COMMENT '核心商圈',
    address STRING COMMENT '地址',
    -- 价格相关
    current_price DECIMAL(10,2) COMMENT '当前价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    discount_rate DECIMAL(3,2) COMMENT '折扣率',
    -- 评分相关
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    heat_score DECIMAL(8,2) COMMENT '热度分 = 评论数/上架天数',
    -- 户型信息（从title解析）
    room_type STRING COMMENT '房型',
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    max_guests INT COMMENT '最大入住人数',
    area_sqm INT COMMENT '面积',
    -- 地理位置
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    subway_distance_meters INT COMMENT '距地铁距离（米）',
    -- 设施标签（从tags解析为结构化）
    has_projector BOOLEAN COMMENT '是否有投影',
    has_kitchen BOOLEAN COMMENT '是否有厨房',
    has_washer BOOLEAN COMMENT '是否有洗衣机',
    has_aircon BOOLEAN COMMENT '是否有空调',
    has_wifi BOOLEAN COMMENT '是否有WiFi',
    has_tv BOOLEAN COMMENT '是否有电视',
    has_bathtub BOOLEAN COMMENT '是否有浴缸',
    has_balcony BOOLEAN COMMENT '是否有阳台',
    has_parking BOOLEAN COMMENT '是否有停车位',
    has_elevator BOOLEAN COMMENT '是否有电梯',
    has_smart_lock BOOLEAN COMMENT '是否有智能锁',
    has_floor_window BOOLEAN COMMENT '是否有落地窗',
    has_mahjong BOOLEAN COMMENT '是否有麻将机',
    facility_count INT COMMENT '设施总数',
    -- 房东信息
    host_id STRING COMMENT '房东ID',
    host_rating DECIMAL(2,1) COMMENT '房东评分',
    is_superhost BOOLEAN COMMENT '是否超赞房东',
    -- 时间相关
    listing_days INT COMMENT '上架天数（估算）',
    last_update_time TIMESTAMP COMMENT '最后更新时间',
    -- 数据质量标记
    data_quality_score INT COMMENT '数据质量评分（0-100）'
) COMMENT 'DWD层-房源明细表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZLIB');

-- 2. 价格明细表（清洗后）
CREATE TABLE IF NOT EXISTS dwd_price_details (
    unit_id STRING COMMENT '房源ID',
    price_date DATE COMMENT '日期',
    price DECIMAL(10,2) COMMENT '价格',
    is_available BOOLEAN COMMENT '是否可预订',
    day_type STRING COMMENT '日期类型（平日/周末/节假日）',
    price_level STRING COMMENT '价格水平（低/中/高/极高）',
    price_change_pct DECIMAL(5,2) COMMENT '相比前一日价格变化%',
    is_peak_season BOOLEAN COMMENT '是否旺季',
    special_event STRING COMMENT '特殊事件（如展会）'
) COMMENT 'DWD层-价格明细表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC
TBLPROPERTIES ('orc.compress'='ZLIB');

-- 3. 设施标签明细表
CREATE TABLE IF NOT EXISTS dwd_facility_tags (
    unit_id STRING COMMENT '房源ID',
    facility_name STRING COMMENT '设施名称',
    facility_category STRING COMMENT '设施分类（娱乐/厨卫/安全/便利）',
    is_present BOOLEAN COMMENT '是否具备'
) COMMENT 'DWD层-设施标签明细表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- ============================================
-- DWS层：汇总数据层（轻度聚合）
-- 按维度汇总，支撑上层应用
-- ============================================

-- 1. 商圈统计汇总表
CREATE TABLE IF NOT EXISTS dws_district_stats (
    district STRING COMMENT '商圈名称',
    stat_date DATE COMMENT '统计日期',
    -- 房源统计
    total_listings INT COMMENT '房源总数',
    new_listings_7d INT COMMENT '7天新增房源',
    inactive_listings INT COMMENT ' inactive房源数',
    -- 价格统计
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    median_price DECIMAL(10,2) COMMENT '中位数价格',
    price_std DECIMAL(10,2) COMMENT '价格标准差',
    min_price DECIMAL(10,2) COMMENT '最低价格',
    max_price DECIMAL(10,2) COMMENT '最高价格',
    price_trend STRING COMMENT '价格趋势（上升/下降/平稳）',
    price_change_7d_pct DECIMAL(5,2) COMMENT '7天价格变化%',
    -- 评分统计
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    rating_distribution MAP<STRING, INT> COMMENT '评分分布（如{"5星":100, "4星":50}）',
    -- 设施统计
    top_facilities ARRAY<STRING> COMMENT '热门设施Top5',
    avg_facility_count DECIMAL(4,1) COMMENT '平均设施数',
    -- 热度统计
    total_comments_30d INT COMMENT '30天总评论数',
    avg_heat_score DECIMAL(8,2) COMMENT '平均热度分',
    -- 竞争度
    competition_level STRING COMMENT '竞争程度（高/中/低）',
    saturation_score DECIMAL(5,2) COMMENT '饱和度评分（0-1）'
) COMMENT 'DWS层-商圈统计汇总表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 2. 设施溢价分析表
CREATE TABLE IF NOT EXISTS dws_facility_analysis (
    facility_name STRING COMMENT '设施名称',
    stat_date DATE COMMENT '统计日期',
    -- 价格影响
    avg_price_with DECIMAL(10,2) COMMENT '有该设施的平均价格',
    avg_price_without DECIMAL(10,2) COMMENT '无该设施的平均价格',
    price_premium DECIMAL(10,2) COMMENT '价格溢价金额',
    price_premium_pct DECIMAL(5,2) COMMENT '价格溢价率%',
    -- 统计显著性
    sample_count_with INT COMMENT '有该设施的样本数',
    sample_count_without INT COMMENT '无该设施的样本数',
    confidence_level DECIMAL(3,2) COMMENT '置信水平',
    -- 评级
    impact_score DECIMAL(5,2) COMMENT '影响力评分（0-100）',
    roi_rating STRING COMMENT 'ROI评级（高/中/低）',
    -- 细分分析
    premium_by_district MAP<STRING, DECIMAL(10,2)>> COMMENT '各商圈溢价情况'
) COMMENT 'DWS层-设施溢价分析表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 3. 节假日价格分析表
CREATE TABLE IF NOT EXISTS dws_seasonal_analysis (
    district STRING COMMENT '商圈',
    date_type STRING COMMENT '日期类型（平日/周末/节假日）',
    holiday_name STRING COMMENT '节假日名称（如国庆、春节）',
    stat_date DATE COMMENT '统计日期',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    price_premium_pct DECIMAL(5,2) COMMENT '相比平日溢价%',
    occupancy_rate DECIMAL(5,2) COMMENT '预订率（根据可预订情况估算）',
    peak_start_date DATE COMMENT '旺季开始日期',
    peak_end_date DATE COMMENT '旺季结束日期',
    optimal_booking_days ARRAY<INT> COMMENT '最佳预订提前天数'
) COMMENT 'DWS层-节假日价格分析表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 4. 房源聚类结果表
CREATE TABLE IF NOT EXISTS dws_listing_clusters (
    cluster_id INT COMMENT '聚类ID',
    cluster_name STRING COMMENT '聚类名称（如高端商务型）',
    cluster_description STRING COMMENT '聚类描述',
    stat_date DATE COMMENT '统计日期',
    -- 聚类特征
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    avg_bedrooms DECIMAL(3,1) COMMENT '平均卧室数',
    avg_area DECIMAL(6,1) COMMENT '平均面积',
    top_facilities ARRAY<STRING> COMMENT '代表性设施',
    price_range_low DECIMAL(10,2) COMMENT '价格区间下限',
    price_range_high DECIMAL(10,2) COMMENT '价格区间上限',
    -- 聚类统计
    listing_count INT COMMENT '聚类内房源数',
    percentage DECIMAL(5,2) COMMENT '占比%',
    representative_units ARRAY<STRING> COMMENT '代表性房源ID'
) COMMENT 'DWS层-房源聚类结果表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 5. 投资收益率分析表
CREATE TABLE IF NOT EXISTS dws_investment_analysis (
    district STRING COMMENT '商圈',
    stat_date DATE COMMENT '统计日期',
    -- 投资指标
    avg_daily_price DECIMAL(10,2) COMMENT '平均日租价格',
    estimated_occupancy_rate DECIMAL(5,2) COMMENT '预估入住率',
    estimated_monthly_revenue DECIMAL(12,2) COMMENT '预估月收入',
    estimated_annual_revenue DECIMAL(12,2) COMMENT '预估年收入',
    -- ROI计算（假设装修成本10万，月租3000）
    roi_1y DECIMAL(5,2) COMMENT '1年投资回报率',
    roi_2y DECIMAL(5,2) COMMENT '2年投资回报率',
    payback_period_months INT COMMENT '回本周期（月）',
    -- 风险评估
    risk_level STRING COMMENT '风险等级（高/中/低）',
    risk_factors ARRAY<STRING> COMMENT '风险因素',
    -- 投资建议
    investment_rating STRING COMMENT '投资评级（A/B/C/D）',
    recommendation STRING COMMENT '投资建议'
) COMMENT 'DWS层-投资收益率分析表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- ============================================
-- ADS层：应用数据层（重度聚合/算法结果）
-- 直接支撑API接口，高度优化查询性能
-- ============================================

-- 1. 房源特征向量表（用于相似度计算）
CREATE TABLE IF NOT EXISTS ads_listing_features (
    unit_id STRING COMMENT '房源ID',
    feature_vector ARRAY<FLOAT> COMMENT '特征向量（标准化后）',
    feature_names ARRAY<STRING> COMMENT '特征名称列表',
    district_encoded ARRAY<FLOAT> COMMENT '区域One-Hot编码',
    price_normalized FLOAT COMMENT '价格标准化值',
    rating_normalized FLOAT COMMENT '评分标准化值',
    facility_vector ARRAY<FLOAT> COMMENT '设施特征向量',
    -- 便于快速查询
    district STRING COMMENT '商圈',
    price_bucket STRING COMMENT '价格分桶（低/中/高/豪华）',
    update_time TIMESTAMP COMMENT '更新时间'
) COMMENT 'ADS层-房源特征向量表'
STORED AS ORC;

-- 2. 房源相似度矩阵（Top N相似房源）
CREATE TABLE IF NOT EXISTS ads_similarity_matrix (
    unit_id STRING COMMENT '房源ID',
    similar_unit_id STRING COMMENT '相似房源ID',
    similarity_score DECIMAL(4,3) COMMENT '相似度分数（0-1）',
    similarity_factors MAP<STRING, DECIMAL(4,3)>> COMMENT '相似因子（如{"价格":0.9, "设施":0.8}）',
    rank INT COMMENT '相似度排名'
) COMMENT 'ADS层-房源相似度矩阵'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 3. 价格预测结果表
CREATE TABLE IF NOT EXISTS ads_price_predictions (
    unit_id STRING COMMENT '房源ID',
    prediction_date DATE COMMENT '预测日期',
    predicted_price DECIMAL(10,2) COMMENT '预测价格',
    confidence_lower DECIMAL(10,2) COMMENT '置信区间下限',
    confidence_upper DECIMAL(10,2) COMMENT '置信区间上限',
    confidence_level DECIMAL(3,2) COMMENT '置信水平',
    -- 预测因子分解
    base_price DECIMAL(10,2) COMMENT '基础价格',
    district_premium DECIMAL(10,2) COMMENT '区域溢价',
    facility_premium DECIMAL(10,2) COMMENT '设施溢价',
    seasonality_factor DECIMAL(4,2) COMMENT '季节性因子',
    -- 模型信息
    model_version STRING COMMENT '模型版本',
    feature_importance MAP<STRING, DECIMAL(4,3)>> COMMENT '特征重要性'
) COMMENT 'ADS层-价格预测结果表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- 4. 推荐结果缓存表
CREATE TABLE IF NOT EXISTS ads_recommendations (
    user_id STRING COMMENT '用户ID（或session_id）',
    unit_id STRING COMMENT '推荐房源ID',
    rank INT COMMENT '推荐排名',
    match_score DECIMAL(4,3) COMMENT '匹配分数',
    algorithm STRING COMMENT '推荐算法（cf/content/hybrid）',
    recommend_reason STRING COMMENT '推荐理由',
    is_clicked BOOLEAN COMMENT '是否点击',
    is_booked BOOLEAN COMMENT '是否预订',
    generate_time TIMESTAMP COMMENT '生成时间'
) COMMENT 'ADS层-推荐结果缓存表'
PARTITIONED BY (dt STRING COMMENT '日期分区')
STORED AS ORC;

-- ============================================
-- 视图：便于查询
-- ============================================

-- 1. 房源完整信息视图
CREATE OR REPLACE VIEW v_listing_full_info AS
SELECT
    l.unit_id,
    l.district,
    l.business_district,
    l.current_price,
    l.original_price,
    l.rating,
    l.comment_count,
    l.heat_score,
    l.bedroom_count,
    l.area_sqm,
    l.facility_count,
    l.has_projector,
    l.has_kitchen,
    l.has_bathtub,
    d.avg_price as district_avg_price,
    d.competition_level,
    CASE
        WHEN l.current_price < d.avg_price * 0.8 THEN 'low'
        WHEN l.current_price > d.avg_price * 1.2 THEN 'high'
        ELSE 'medium'
    END as price_level
FROM dwd_listing_details l
LEFT JOIN dws_district_stats d ON l.district = d.district
WHERE l.dt = (SELECT MAX(dt) FROM dwd_listing_details);

-- 2. 价格洼地视图（低于区域均价20%）
CREATE OR REPLACE VIEW v_price_opportunities AS
SELECT
    l.*,
    d.avg_price as district_avg_price,
    ROUND((d.avg_price - l.current_price) / d.avg_price * 100, 2) as discount_pct
FROM dwd_listing_details l
JOIN dws_district_stats d ON l.district = d.district
WHERE l.current_price < d.avg_price * 0.8
  AND l.rating >= 4.0
  AND l.dt = (SELECT MAX(dt) FROM dwd_listing_details)
ORDER BY discount_pct DESC;

-- 3. 投资推荐视图
CREATE OR REPLACE VIEW v_investment_recommendations AS
SELECT
    district,
    roi_2y,
    payback_period_months,
    risk_level,
    investment_rating,
    recommendation,
    ROW_NUMBER() OVER (ORDER BY roi_2y DESC) as roi_rank
FROM dws_investment_analysis
WHERE dt = (SELECT MAX(dt) FROM dws_investment_analysis)
ORDER BY roi_2y DESC;

-- ============================================
-- 初始化注释
-- ============================================

COMMENT ON DATABASE tujia_dw IS '途家民宿数据仓库，包含房源、价格、用户行为等数据';
