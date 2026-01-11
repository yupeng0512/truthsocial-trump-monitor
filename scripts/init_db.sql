-- Truth Social Trump Monitor 数据库初始化脚本
-- 注意：SQLAlchemy 会自动创建表，此脚本仅用于手动初始化或参考

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS truthsocial_monitor
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE truthsocial_monitor;

-- 帖子表
CREATE TABLE IF NOT EXISTS posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Truth Social 帖子 ID',
    username VARCHAR(128) NOT NULL COMMENT '发帖用户名',
    content TEXT COMMENT '帖子内容',
    url VARCHAR(512) COMMENT '帖子链接',
    
    -- 互动数据
    reblogs_count INT DEFAULT 0 COMMENT '转发数',
    favourites_count INT DEFAULT 0 COMMENT '点赞数',
    replies_count INT DEFAULT 0 COMMENT '回复数',
    
    -- 转发相关
    is_reblog BOOLEAN DEFAULT FALSE COMMENT '是否为转发',
    reblog_content TEXT COMMENT '转发的原帖内容',
    
    -- JSON 数据
    media_attachments JSON COMMENT '媒体附件',
    raw_data JSON COMMENT 'API 返回的原始数据',
    
    -- LLM 分析
    llm_analysis JSON COMMENT 'LLM 分析结果',
    llm_analyzed_at DATETIME COMMENT 'LLM 分析时间',
    
    -- 时间戳
    posted_at DATETIME COMMENT '帖子发布时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    
    -- 通知状态
    notified BOOLEAN DEFAULT FALSE COMMENT '是否已发送通知',
    notified_at DATETIME COMMENT '通知发送时间',
    
    -- 索引
    INDEX idx_post_id (post_id),
    INDEX idx_username (username),
    INDEX idx_posted_at (posted_at),
    INDEX idx_notified (notified),
    INDEX idx_llm_analyzed (llm_analyzed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 采集日志表
CREATE TABLE IF NOT EXISTS scrape_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(128) NOT NULL COMMENT '采集的用户名',
    status VARCHAR(32) NOT NULL COMMENT '采集状态: success/failed/partial',
    
    -- 统计信息
    total_fetched INT DEFAULT 0 COMMENT '获取的帖子总数',
    new_posts INT DEFAULT 0 COMMENT '新增帖子数',
    updated_posts INT DEFAULT 0 COMMENT '更新帖子数',
    
    -- 错误信息
    error_message TEXT COMMENT '错误信息',
    
    -- 时间
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    finished_at DATETIME COMMENT '结束时间',
    duration_seconds INT COMMENT '耗时（秒）',
    
    -- 索引
    INDEX idx_scrape_username (username),
    INDEX idx_scrape_status (status),
    INDEX idx_scrape_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 系统配置表（运行时配置）
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键名',
    config_value JSON NOT NULL COMMENT '配置值（JSON 格式）',
    description VARCHAR(255) COMMENT '配置描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 翻译字段（添加到 posts 表）
ALTER TABLE posts ADD COLUMN IF NOT EXISTS translated_content TEXT COMMENT '翻译后的内容';
ALTER TABLE posts ADD COLUMN IF NOT EXISTS translated_at DATETIME COMMENT '翻译时间';

-- 创建用户（可选，根据实际情况调整）
-- CREATE USER IF NOT EXISTS 'truthsocial'@'%' IDENTIFIED BY 'your_password';
-- GRANT ALL PRIVILEGES ON truthsocial_monitor.* TO 'truthsocial'@'%';
-- FLUSH PRIVILEGES;
