-- MySQL 用户表创建脚本
-- 在 Navicat 中执行步骤：
-- 1. 连接你的 MySQL 数据库
-- 2. 新建数据库，命名为: homestay_user_db
-- 3. 右键数据库 -> 新建查询 -> 粘贴以下 SQL -> 运行

-- 创建数据库（如不存在）
CREATE DATABASE IF NOT EXISTS homestay_user_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE homestay_user_db;

-- 删除旧表（如果存在）
DROP TABLE IF EXISTS users;

-- 创建用户表
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
    phone VARCHAR(20) UNIQUE COMMENT '手机号',
    hashed_password VARCHAR(255) NOT NULL COMMENT '加密密码',
    full_name VARCHAR(100) COMMENT '昵称/真实姓名',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    is_superuser BOOLEAN DEFAULT FALSE COMMENT '是否管理员',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    -- 用户偏好设置 (用于推荐系统)
    preferred_district VARCHAR(50) COMMENT '偏好商圈，如"江汉路"',
    preferred_price_min FLOAT COMMENT '最低价格偏好',
    preferred_price_max FLOAT COMMENT '最高价格偏好',

    -- 索引
    INDEX idx_username (username),
    INDEX idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 插入测试用户 (密码都是 '123456')
-- 密码使用 bcrypt 加密，以下 hash 对应 '123456'
INSERT INTO users (username, phone, hashed_password, full_name, preferred_district, preferred_price_min, preferred_price_max) VALUES
('test', '13800138000', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IyK', '测试用户', '江汉路', 200, 500),
('admin', '13900139000', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IyK', '管理员', NULL, NULL, NULL),
('user1', '13700137000', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IyK', '用户一', '光谷', 150, 400),
('龚婷', '13600136000', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IyK', '龚婷', '楚河汉街', 300, 600);

-- 验证数据
SELECT '总用户数:' as info, COUNT(*) as count FROM users;
SELECT id, username, phone, full_name, preferred_district, created_at FROM users;
