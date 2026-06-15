CREATE DATABASE IF NOT EXISTS financial_sentiment
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE financial_sentiment;

CREATE TABLE IF NOT EXISTS news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content MEDIUMTEXT,
    source VARCHAR(100),
    url VARCHAR(1000),
    url_hash CHAR(32),
    publish_time DATETIME,
    crawl_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(80) COMMENT '金融板块或内容分类',
    doc_type VARCHAR(30) DEFAULT 'news' COMMENT 'news/announcement/comment/sample',
    stock_code VARCHAR(20),
    stock_name VARCHAR(80),
    author VARCHAR(120),
    read_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    keywords VARCHAR(500),
    UNIQUE KEY uk_url_hash (url_hash),
    INDEX idx_source (source),
    INDEX idx_publish_time (publish_time),
    INDEX idx_category (category),
    INDEX idx_doc_type (doc_type),
    INDEX idx_stock_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sentiment_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    news_id INT NOT NULL,
    sentiment_label VARCHAR(20) COMMENT 'positive/negative/neutral',
    sentiment_score FLOAT,
    snownlp_score FLOAT,
    lexicon_score FLOAT DEFAULT 0,
    confidence FLOAT DEFAULT 0,
    analyzed_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE,
    UNIQUE KEY uk_sentiment_news (news_id),
    INDEX idx_news_id (news_id),
    INDEX idx_label (sentiment_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS topic_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    news_id INT NOT NULL,
    topic_id INT COMMENT 'LDA主题编号',
    topic_label VARCHAR(100) COMMENT '主题标签',
    topic_prob FLOAT,
    analyzed_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE,
    UNIQUE KEY uk_topic_news (news_id),
    INDEX idx_news_id (news_id),
    INDEX idx_topic_id (topic_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crawl_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(100),
    status VARCHAR(30),
    pages INT DEFAULT 0,
    records INT DEFAULT 0,
    message VARCHAR(1000),
    started_at DATETIME,
    finished_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_time (finished_at),
    INDEX idx_log_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_index (
    id INT AUTO_INCREMENT PRIMARY KEY,
    index_name VARCHAR(50),
    trade_date DATE,
    open_price FLOAT,
    close_price FLOAT,
    high_price FLOAT,
    low_price FLOAT,
    volume BIGINT,
    change_pct FLOAT,
    INDEX idx_date (trade_date),
    INDEX idx_name (index_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
