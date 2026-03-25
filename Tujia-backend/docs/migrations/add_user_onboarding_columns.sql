-- 已有 users 表时追加首登调研与用户画像字段（勿与 DROP 重建的 schema_mysql 混用）
ALTER TABLE users ADD COLUMN user_role VARCHAR(20) NULL COMMENT 'operator|investor|guest';
ALTER TABLE users ADD COLUMN onboarding_completed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否完成首登调研';
ALTER TABLE users ADD COLUMN onboarding_skipped_at DATETIME NULL COMMENT '跳过调研时间';
ALTER TABLE users ADD COLUMN persona_answers TEXT NULL COMMENT '问卷JSON';
ALTER TABLE users ADD COLUMN persona_summary TEXT NULL COMMENT '用户画像摘要';
