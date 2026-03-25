-- ============================================================
-- Hive数仓表结构 V2 - 民宿价格数据分析系统
-- 分层：ODS -> DWD -> DWS -> ADS
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS tujia_ods;
CREATE DATABASE IF NOT EXISTS tujia_dwd;
CREATE DATABASE IF NOT EXISTS tujia_dws;
CREATE DATABASE IF NOT EXISTS tujia_ads;

-- ============================================================
-- ODS层 - 原始数据层（贴源层）
-- ============================================================

-- ODS: 房源基础信息（来自tujia_calendar_data.json）
CREATE TABLE IF NOT EXISTS tujia_ods.ods_listings (
    unit_id STRING COMMENT '房源ID',
    title STRING COMMENT '房源标题',
    city STRING COMMENT '城市',
    district STRING COMMENT '行政区',
    address STRING COMMENT '详细地址',
    final_price DECIMAL(10,2) COMMENT '最终价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    favorite_count STRING COMMENT '收藏数（可能含k+）',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    cover_image STRING COMMENT '封面图URL',
    tags STRING COMMENT '标签JSON'
)
COMMENT '房源基础信息原始表'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

-- ODS: 房源详情标签（来自tujia_calendar_data_tags.json）
CREATE TABLE IF NOT EXISTS tujia_ods.ods_listing_details (
    unit_id STRING COMMENT '房源ID',
    house_name STRING COMMENT '房源名称',
    favorite_count INT COMMENT '收藏数',
    pic_count INT COMMENT '图片数量',
    house_pics STRING COMMENT '图片列表JSON',
    video_url STRING COMMENT '视频URL',
    house_tags STRING COMMENT '标签列表JSON',
    comment_overall DECIMAL(2,1) COMMENT '总体评分',
    comment_brief STRING COMMENT '评论摘要',
    comment_total_count INT COMMENT '评论总数',
    area_name STRING COMMENT '区域名称',
    trade_area STRING COMMENT '商圈',
    nearby_position STRING COMMENT '周边位置JSON'
)
COMMENT '房源详情标签原始表'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

-- ODS: 价格日历
CREATE TABLE IF NOT EXISTS tujia_ods.ods_price_calendar (
    unit_id STRING COMMENT '房源ID',
    calendar_date STRING COMMENT '日期',
    price INT COMMENT '价格',
    can_booking BOOLEAN COMMENT '是否可预订',
    price_flag INT COMMENT '价格标记'
)
COMMENT '价格日历原始表'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

-- ============================================================
-- DWD层 - 明细数据层（清洗后）
-- ============================================================

-- DWD: 清洗后的房源明细（2464条核心数据）
CREATE TABLE IF NOT EXISTS tujia_dwd.dwd_listings (
    unit_id STRING COMMENT '房源ID',
    title STRING COMMENT '房源标题',
    city STRING COMMENT '城市',
    district STRING COMMENT '行政区',
    address STRING COMMENT '详细地址',
    final_price DECIMAL(10,2) COMMENT '最终价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    discount_rate DECIMAL(5,4) COMMENT '折扣率',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    favorite_count INT COMMENT '收藏数（清洗后）',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    house_name STRING COMMENT '房源名称',
    pic_count INT COMMENT '图片数量',
    house_pics STRING COMMENT '图片列表JSON',
    video_url STRING COMMENT '视频URL',
    house_tags STRING COMMENT '标签列表JSON',
    comment_overall DECIMAL(2,1) COMMENT '总体评分',
    comment_brief STRING COMMENT '评论摘要',
    comment_total_count INT COMMENT '评论总数',
    area_name STRING COMMENT '区域名称',
    trade_area STRING COMMENT '商圈'
)
COMMENT '房源明细清洗表'
STORED AS ORC;

-- ============================================================
-- DWS层 - 汇总数据层
-- ============================================================

-- DWS: 商圈统计
CREATE TABLE IF NOT EXISTS tujia_dws.dws_district_stats (
    district STRING COMMENT '行政区',
    trade_area STRING COMMENT '商圈',
    listing_count INT COMMENT '房源数量',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    avg_favorite_count DECIMAL(10,2) COMMENT '平均收藏数',
    avg_comment_count DECIMAL(10,2) COMMENT '平均评论数',
    avg_bedroom_count DECIMAL(3,1) COMMENT '平均卧室数',
    min_price DECIMAL(10,2) COMMENT '最低价格',
    max_price DECIMAL(10,2) COMMENT '最高价格'
)
COMMENT '商圈统计汇总表'
STORED AS ORC;

-- DWS: 标签统计
CREATE TABLE IF NOT EXISTS tujia_dws.dws_tag_stats (
    tag_text STRING COMMENT '标签文本',
    tag_category STRING COMMENT '标签类别',
    listing_count INT COMMENT '房源数量',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    avg_favorite_count DECIMAL(10,2) COMMENT '平均收藏数'
)
COMMENT '标签统计汇总表'
STORED AS ORC;

-- DWS: 价格趋势（按月）
CREATE TABLE IF NOT EXISTS tujia_dws.dws_price_trend (
    unit_id STRING COMMENT '房源ID',
    month STRING COMMENT '月份',
    avg_month_price DECIMAL(10,2) COMMENT '月平均价格',
    min_price DECIMAL(10,2) COMMENT '最低价格',
    max_price DECIMAL(10,2) COMMENT '最高价格',
    days_count INT COMMENT '天数'
)
COMMENT '价格趋势汇总表'
STORED AS ORC;

-- ============================================================
-- ADS层 - 应用数据层
-- ============================================================

-- ADS: 房源展示数据（前端列表用）
CREATE TABLE IF NOT EXISTS tujia_ads.ads_listing_display (
    unit_id STRING COMMENT '房源ID',
    title STRING COMMENT '房源标题',
    district STRING COMMENT '行政区',
    trade_area STRING COMMENT '商圈',
    final_price DECIMAL(10,2) COMMENT '最终价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    discount_rate DECIMAL(5,4) COMMENT '折扣率',
    rating DECIMAL(2,1) COMMENT '评分',
    favorite_count INT COMMENT '收藏数',
    pic_count INT COMMENT '图片数量',
    cover_image STRING COMMENT '封面图',
    house_tags STRING COMMENT '标签JSON',
    comment_brief STRING COMMENT '评论摘要',
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度'
)
COMMENT '房源展示应用表'
STORED AS ORC;

-- ADS: 模型训练数据
CREATE TABLE IF NOT EXISTS tujia_ads.ads_training_data (
    unit_id STRING COMMENT '房源ID',
    district STRING COMMENT '行政区',
    target_price DECIMAL(10,2) COMMENT '目标价格',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    favorite_count INT COMMENT '收藏数',
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    pic_count INT COMMENT '图片数',
    discount_rate DECIMAL(5,4) COMMENT '折扣率',
    has_metro INT COMMENT '是否有地铁',
    has_kitchen INT COMMENT '是否有厨房',
    has_projector INT COMMENT '是否有投影',
    has_washer INT COMMENT '是否有洗衣机',
    has_smart_lock INT COMMENT '是否有智能锁',
    has_air_conditioner INT COMMENT '是否有空调',
    has_bathtub INT COMMENT '是否有浴缸',
    has_parking INT COMMENT '是否有停车位',
    has_balcony INT COMMENT '是否有阳台',
    district_avg_price DECIMAL(10,2) COMMENT '商圈平均价格'
)
COMMENT '模型训练数据集'
STORED AS ORC;

-- ADS: 推荐特征数据
CREATE TABLE IF NOT EXISTS tujia_ads.ads_recommendation_features (
    unit_id STRING COMMENT '房源ID',
    district STRING COMMENT '行政区',
    trade_area STRING COMMENT '商圈',
    final_price DECIMAL(10,2) COMMENT '价格',
    rating DECIMAL(2,1) COMMENT '评分',
    favorite_count INT COMMENT '收藏数',
    bedroom_count INT COMMENT '卧室数',
    pic_count INT COMMENT '图片数',
    house_tags STRING COMMENT '标签JSON',
    feature_vector STRING COMMENT '特征向量JSON'
)
COMMENT '推荐算法特征表'
STORED AS ORC;
