-- ============================================
-- 途家民宿数据仓库 - Hive表结构设计
-- 适用于MySQL业务库 + Hive数据仓库架构
-- ============================================

-- ============================================
-- MySQL业务库 (tujia_business)
-- 存储事务性强、实时性要求高的数据
-- ============================================

-- 1. 用户表 (已存在，保持兼容)
-- 注意：原有users表结构保持不变，只是扩展字段

-- 2. 我的房源表
CREATE TABLE IF NOT EXISTS my_listings (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    name VARCHAR(100) NOT NULL COMMENT '房源名称',
    district VARCHAR(50) NOT NULL COMMENT '商圈',
    address VARCHAR(200) COMMENT '详细地址',
    price DECIMAL(10,2) NOT NULL COMMENT '当前定价',
    room_type VARCHAR(20) COMMENT '房型：整套/独立房间/合住',
    bedrooms INT DEFAULT 1 COMMENT '卧室数',
    bathrooms INT DEFAULT 1 COMMENT '卫生间数',
    area DECIMAL(8,2) COMMENT '面积(㎡)',
    capacity INT DEFAULT 2 COMMENT '容纳人数',
    facilities JSON COMMENT '设施列表：["WiFi", "投影"]',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT DEFAULT 0 COMMENT '评论数',
    is_monitoring BOOLEAN DEFAULT FALSE COMMENT '是否开启竞品监控',
    monitored_listings JSON COMMENT '监控的竞品ID列表',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_user_id (user_id),
    INDEX idx_district (district),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户自有房源';

-- 3. 收藏夹表
CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    unit_id VARCHAR(50) NOT NULL COMMENT '房源ID（途家系统）',
    listing_data JSON COMMENT '收藏时房源快照',
    folder_name VARCHAR(50) DEFAULT '默认收藏夹' COMMENT '收藏夹名称',
    price_alert_enabled BOOLEAN DEFAULT FALSE COMMENT '价格变动提醒',
    alert_threshold DECIMAL(5,2) DEFAULT 0.10 COMMENT '提醒阈值（如0.1=10%）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_user_unit (user_id, unit_id, folder_name),
    INDEX idx_user_folder (user_id, folder_name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户收藏';

-- 4. 浏览历史表
CREATE TABLE IF NOT EXISTS user_view_history (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    unit_id VARCHAR(50) NOT NULL COMMENT '浏览的房源ID',
    view_duration INT DEFAULT 0 COMMENT '浏览时长（秒）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户浏览历史';

-- 5. 价格预测记录表
CREATE TABLE IF NOT EXISTS price_prediction_logs (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT COMMENT '用户ID（可选）',
    input_features JSON NOT NULL COMMENT '输入特征完整JSON',
    district VARCHAR(50) NOT NULL COMMENT '商圈',
    bedrooms INT COMMENT '卧室数',
    area DECIMAL(8,2) COMMENT '面积',
    facilities JSON COMMENT '设施',
    predicted_price DECIMAL(10,2) NOT NULL COMMENT '预测价格',
    confidence_lower DECIMAL(10,2) COMMENT '置信区间下限',
    confidence_upper DECIMAL(10,2) COMMENT '置信区间上限',
    model_version VARCHAR(20) DEFAULT 'v1.0' COMMENT '模型版本',
    is_mock BOOLEAN DEFAULT TRUE COMMENT '是否Mock预测',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_district (district),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='价格预测记录';

-- 6. 竞品动态提醒表
CREATE TABLE IF NOT EXISTS competitor_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    my_listing_id INT NOT NULL COMMENT '我的房源ID',
    competitor_id VARCHAR(50) NOT NULL COMMENT '竞品房源ID',
    alert_type VARCHAR(20) NOT NULL COMMENT '类型：price_change/new_listing/bad_review',
    alert_title VARCHAR(100) NOT NULL COMMENT '提醒标题',
    alert_detail TEXT COMMENT '详细内容',
    old_value DECIMAL(10,2) COMMENT '旧值（如旧价格）',
    new_value DECIMAL(10,2) COMMENT '新值（如新价格）',
    is_read BOOLEAN DEFAULT FALSE COMMENT '是否已读',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_my_listing (my_listing_id),
    INDEX idx_is_read (is_read),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (my_listing_id) REFERENCES my_listings(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='竞品动态提醒';

-- 7. 推荐结果缓存表（协同过滤结果）
CREATE TABLE IF NOT EXISTS recommendation_results (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT COMMENT '用户ID（可选，匿名用户为空）',
    unit_id VARCHAR(50) NOT NULL COMMENT '推荐房源ID',
    match_score DECIMAL(4,3) COMMENT '匹配度分数（0-1）',
    reason VARCHAR(200) COMMENT '推荐理由',
    algorithm VARCHAR(20) DEFAULT 'cf' COMMENT '推荐算法：cf协同过滤/content内容/popular热门',
    is_clicked BOOLEAN DEFAULT FALSE COMMENT '是否被点击',
    is_mock BOOLEAN DEFAULT TRUE COMMENT '是否Mock推荐',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_unit_id (unit_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='推荐结果缓存';

-- 8. API调用日志表
CREATE TABLE IF NOT EXISTS api_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT COMMENT '用户ID',
    endpoint VARCHAR(200) NOT NULL COMMENT '接口路径',
    method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
    request_params JSON COMMENT '请求参数',
    response_status INT COMMENT '响应状态码',
    response_time_ms INT COMMENT '响应时间（毫秒）',
    client_ip VARCHAR(50) COMMENT '客户端IP',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_endpoint (endpoint),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API调用日志';


-- ============================================
-- Hive数据仓库 (tujia_dw)
-- 存储海量离线数据，支持大数据分析
-- ============================================

-- ODS层：原始数据（从爬虫直接导入）

-- ODS1. 房源原始数据表
CREATE TABLE IF NOT EXISTS tujia_dw.ods_listings (
    unit_id STRING COMMENT '房源唯一ID',
    title STRING COMMENT '房源标题',
    city STRING COMMENT '城市',
    district STRING COMMENT '商圈/区域',
    address STRING COMMENT '详细地址',
    final_price DECIMAL(10,2) COMMENT '最终价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    favorite_count STRING COMMENT '收藏数（原始为字符串）',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    cover_image STRING COMMENT '封面图URL',
    tags ARRAY<STRING> COMMENT '标签列表',
    detail_url STRING COMMENT '详情页URL',
    crawled_at TIMESTAMP COMMENT '爬取时间',
    price_calendar STRUCT<trace:STRING, data:ARRAY<STRUCT<price:INT, priceFlag:INT, date:STRING, canBooking:INT>>> COMMENT '价格日历原始数据'
) COMMENT '房源原始数据'
PARTITIONED BY (dt STRING COMMENT '数据日期')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

-- ODS2. 房源详细标签数据
CREATE TABLE IF NOT EXISTS tujia_dw.ods_listing_details (
    unit_id STRING COMMENT '房源ID',
    house_name STRING COMMENT '房源名称',
    favorite_count INT COMMENT '收藏数',
    house_pics ARRAY<STRUCT<
        title:STRING,
        url:STRING,
        albumUrl:STRING,
        orderIndex:INT,
        pictureExplain:STRING,
        enumPictureCategory:INT,
        originUrl:STRING
    >> COMMENT '房源图片列表',
    house_video_url STRING COMMENT '视频URL',
    house_video_time_span INT COMMENT '视频时长(秒)',
    pic_count INT COMMENT '图片数量',
    house_tags ARRAY<STRUCT<
        tagText:STRUCT<text:STRING, color:STRING>,
        tagType:INT,
        tagTypeName:STRING
    >> COMMENT '房源标签列表',
    facilities ARRAY<STRING> COMMENT '设施标签（从houseTags解析）',
    created_at TIMESTAMP COMMENT '创建时间'
) COMMENT '房源详细标签数据'
PARTITIONED BY (dt STRING COMMENT '数据日期')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;

-- ODS3. 价格日历明细表（展开后的价格数据）
CREATE TABLE IF NOT EXISTS tujia_dw.ods_price_calendar (
    unit_id STRING COMMENT '房源ID',
    date STRING COMMENT '日期',
    price INT COMMENT '当日价格',
    price_flag INT COMMENT '价格标记',
    can_booking INT COMMENT '是否可预订'
) COMMENT '价格日历明细'
PARTITIONED BY (dt STRING COMMENT '数据日期')
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS ORC;


-- DWD层：明细数据（清洗后的数据）

-- DWD1. 房源明细表（清洗+特征提取）
CREATE TABLE IF NOT EXISTS tujia_dw.dwd_listing_details (
    unit_id STRING COMMENT '房源ID',
    title STRING COMMENT '标题',
    city STRING COMMENT '城市',
    district STRING COMMENT '商圈',
    address STRING COMMENT '地址',
    price DECIMAL(10,2) COMMENT '当前价格',
    original_price DECIMAL(10,2) COMMENT '原价',
    rating DECIMAL(2,1) COMMENT '评分',
    comment_count INT COMMENT '评论数',
    favorite_count INT COMMENT '收藏数',
    longitude DECIMAL(12,8) COMMENT '经度',
    latitude DECIMAL(12,8) COMMENT '纬度',
    cover_image STRING COMMENT '封面图',

    -- 从title解析的户型特征
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    area DECIMAL(8,2) COMMENT '面积(㎡)',
    max_guests INT COMMENT '最大入住人数',

    -- 设施特征（从tags解析）
    has_projector BOOLEAN COMMENT '是否有投影',
    has_kitchen BOOLEAN COMMENT '是否有厨房',
    has_wifi BOOLEAN COMMENT '是否有WiFi',
    has_air_conditioning BOOLEAN COMMENT '是否有空调',
    has_washing_machine BOOLEAN COMMENT '是否有洗衣机',
    has_bathtub BOOLEAN COMMENT '是否有浴缸',
    has_smart_lock BOOLEAN COMMENT '是否有智能锁',
    has_parking BOOLEAN COMMENT '是否有停车位',
    has_balcony BOOLEAN COMMENT '是否有阳台',
    is_mahjong_room BOOLEAN COMMENT '是否是麻将房',

    -- 派生特征
    heat_score DECIMAL(5,2) COMMENT '热度分 = comment_count/天数',
    discount_rate DECIMAL(4,2) COMMENT '折扣率 = final_price/original_price',

    -- 数据质量标记
    is_parsed_ok BOOLEAN COMMENT '户型解析是否成功',
    data_source STRING COMMENT '数据来源'
) COMMENT '清洗后的房源明细'
PARTITIONED BY (dt STRING COMMENT '数据日期')
STORED AS ORC;

-- DWD2. 价格日历统计表
CREATE TABLE IF NOT EXISTS tujia_dw.dwd_price_stats (
    unit_id STRING COMMENT '房源ID',
    date STRING COMMENT '日期',
    price DECIMAL(10,2) COMMENT '当日价格',
    is_weekend BOOLEAN COMMENT '是否周末',
    is_holiday BOOLEAN COMMENT '是否节假日',
    is_available BOOLEAN COMMENT '是否可预订',
    day_of_week INT COMMENT '星期几（1-7）',
    week_of_year INT COMMENT '一年中第几周',
    month INT COMMENT '月份',
    year INT COMMENT '年份',
    price_rank_in_district INT COMMENT '同商圈价格排名',
    price_percentile DECIMAL(4,3) COMMENT '同商圈价格百分位'
) COMMENT '价格日历统计'
PARTITIONED BY (dt STRING COMMENT '数据日期')
STORED AS ORC;


-- DWS层：汇总数据（按维度聚合）

-- DWS1. 区域统计汇总
CREATE TABLE IF NOT EXISTS tujia_dw.dws_district_stats (
    district STRING COMMENT '商圈',
    city STRING COMMENT '城市',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    median_price DECIMAL(10,2) COMMENT '中位数价格',
    min_price DECIMAL(10,2) COMMENT '最低价格',
    max_price DECIMAL(10,2) COMMENT '最高价格',
    price_std DECIMAL(10,2) COMMENT '价格标准差',
    total_listings INT COMMENT '房源总数',
    avg_rating DECIMAL(2,1) COMMENT '平均评分',
    avg_comment_count DECIMAL(8,2) COMMENT '平均评论数',
    total_favorites INT COMMENT '总收藏数',
    price_trend STRING COMMENT '价格趋势：up/down/stable',
    trend_percent DECIMAL(5,2) COMMENT '趋势变化百分比',
    heat_score DECIMAL(5,2) COMMENT '区域热度分',
    top_facilities ARRAY<STRING> COMMENT '热门设施',
    facility_distribution MAP<STRING, INT> COMMENT '设施分布统计',
    bedroom_distribution MAP<INT, INT> COMMENT '户型分布'
) COMMENT '区域统计汇总'
STORED AS ORC;

-- DWS2. 设施溢价分析
CREATE TABLE IF NOT EXISTS tujia_dw.dws_facility_analysis (
    facility_name STRING COMMENT '设施名称',
    district STRING COMMENT '商圈（可选，全局可为空）',
    avg_with_facility DECIMAL(10,2) COMMENT '有此设施的平均价格',
    avg_without_facility DECIMAL(10,2) COMMENT '无此设施的平均价格',
    premium_amount DECIMAL(10,2) COMMENT '溢价金额',
    premium_percent DECIMAL(5,2) COMMENT '溢价百分比',
    impact_score DECIMAL(4,3) COMMENT '影响力评分（0-1）',
    sample_count INT COMMENT '样本数量',
    correlation_with_rating DECIMAL(4,3) COMMENT '与评分的相关性'
) COMMENT '设施溢价分析'
STORED AS ORC;

-- DWS3. 价格趋势汇总
CREATE TABLE IF NOT EXISTS tujia_dw.dws_price_trends (
    district STRING COMMENT '商圈',
    date STRING COMMENT '日期',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    listing_count INT COMMENT '房源数量',
    weekend_premium DECIMAL(5,2) COMMENT '周末溢价率',
    holiday_premium DECIMAL(5,2) COMMENT '节假日溢价率',
    month_over_month_change DECIMAL(5,2) COMMENT '环比变化',
    year_over_year_change DECIMAL(5,2) COMMENT '同比变化'
) COMMENT '价格趋势汇总'
PARTITIONED BY (dt STRING COMMENT '数据日期')
STORED AS ORC;

-- DWS4. 评销关系分析
CREATE TABLE IF NOT EXISTS tujia_dw.dws_rating_sales_analysis (
    rating_bucket STRING COMMENT '评分区间（如4.5-4.9）',
    district STRING COMMENT '商圈',
    avg_comment_count DECIMAL(8,2) COMMENT '平均评论数',
    avg_price DECIMAL(10,2) COMMENT '平均价格',
    listing_count INT COMMENT '房源数量',
    estimated_occupancy DECIMAL(4,3) COMMENT '预估入住率',
    correlation_coefficient DECIMAL(4,3) COMMENT '相关系数'
) COMMENT '评销关系分析'
STORED AS ORC;


-- ADS层：应用数据（供模型训练和API使用）

-- ADS1. 模型训练特征表（XGBoost用）
CREATE TABLE IF NOT EXISTS tujia_dw.ads_listing_features (
    unit_id STRING COMMENT '房源ID',
    -- 目标变量
    price DECIMAL(10,2) COMMENT '价格',

    -- 数值特征
    bedroom_count INT COMMENT '卧室数',
    bed_count INT COMMENT '床位数',
    bathroom_count INT COMMENT '卫生间数',
    area DECIMAL(8,2) COMMENT '面积',
    max_guests INT COMMENT '最大入住人数',
    comment_count INT COMMENT '评论数',
    favorite_count INT COMMENT '收藏数',
    rating DECIMAL(2,1) COMMENT '评分',
    heat_score DECIMAL(5,2) COMMENT '热度分',
    discount_rate DECIMAL(4,2) COMMENT '折扣率',

    -- 类别特征（已编码）
    district_encoded INT COMMENT '商圈编码',
    city_encoded INT COMMENT '城市编码',

    -- 二元特征
    has_projector INT COMMENT '投影：0/1',
    has_kitchen INT COMMENT '厨房：0/1',
    has_wifi INT COMMENT 'WiFi：0/1',
    has_air_conditioning INT COMMENT '空调：0/1',
    has_washing_machine INT COMMENT '洗衣机：0/1',
    has_bathtub INT COMMENT '浴缸：0/1',
    has_smart_lock INT COMMENT '智能锁：0/1',
    has_parking INT COMMENT '停车位：0/1',
    has_balcony INT COMMENT '阳台：0/1',
    is_mahjong_room INT COMMENT '麻将房：0/1',

    -- 派生特征
    facility_count INT COMMENT '设施数量',
    facility_score DECIMAL(5,2) COMMENT '设施评分',
    price_per_area DECIMAL(10,2) COMMENT '单位面积价格',
    price_per_bedroom DECIMAL(10,2) COMMENT '每卧室价格',

    -- 特征分箱
    price_bucket STRING COMMENT '价格分箱',
    area_bucket STRING COMMENT '面积分箱',
    rating_bucket STRING COMMENT '评分分箱'
) COMMENT '模型训练特征'
STORED AS ORC;

-- ADS2. 房源相似度矩阵（协同过滤用）
CREATE TABLE IF NOT EXISTS tujia_dw.ads_similarity_matrix (
    unit_id_a STRING COMMENT '房源A',
    unit_id_b STRING COMMENT '房源B',
    similarity_score DECIMAL(5,4) COMMENT '相似度分数（0-1）',
    similarity_features ARRAY<STRING> COMMENT '相似特征列表',
    distance_km DECIMAL(8,2) COMMENT '两地距离（公里）'
) COMMENT '房源相似度矩阵'
STORED AS ORC;

-- ADS3. 区域投资建议表
CREATE TABLE IF NOT EXISTS tujia_dw.ads_investment_recommendations (
    district STRING COMMENT '商圈',
    roi_score DECIMAL(5,2) COMMENT 'ROI评分',
    payback_period_months INT COMMENT '回本周期（月）',
    risk_level STRING COMMENT '风险等级：low/medium/high',
    recommendation_tag STRING COMMENT '推荐标签：高收益/稳健型/高风险高回报',
    avg_monthly_revenue DECIMAL(10,2) COMMENT '平均月收益',
    occupancy_forecast DECIMAL(4,3) COMMENT '入住率预测',
    optimal_bedroom_count INT COMMENT '最优卧室数',
    optimal_facilities ARRAY<STRING> COMMENT '推荐设施',
    market_saturity STRING COMMENT '市场成熟度'
) COMMENT '区域投资建议'
STORED AS ORC;


-- ============================================
-- 视图（方便查询）
-- ============================================

-- 热门房源视图
CREATE VIEW IF NOT EXISTS tujia_dw.v_hot_listings AS
SELECT
    unit_id,
    title,
    district,
    price,
    rating,
    comment_count,
    heat_score,
    cover_image,
    ROW_NUMBER() OVER (PARTITION BY district ORDER BY heat_score DESC) as district_rank
FROM tujia_dw.dwd_listing_details
WHERE dt = (SELECT MAX(dt) FROM tujia_dw.dwd_listing_details);

-- 价格洼地视图（实际价格 < 预测价格 * 0.8）
CREATE VIEW IF NOT EXISTS tujia_dw.v_price_opportunities AS
SELECT
    l.unit_id,
    l.title,
    l.district,
    l.price as actual_price,
    p.predicted_price,
    (p.predicted_price - l.price) / p.predicted_price as discount_percent
FROM tujia_dw.dwd_listing_details l
JOIN tujia_dw.ads_price_predictions p ON l.unit_id = p.unit_id
WHERE l.price < p.predicted_price * 0.8;
