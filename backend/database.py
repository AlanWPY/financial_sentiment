import pymysql
import os
import hashlib

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'wpy123456',
    'database': 'financial_sentiment',
    'charset': 'utf8mb4'
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

def init_db():
    sql_path = os.path.join(os.path.dirname(__file__), 'db_init.sql')
    conn = pymysql.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'],
                           user=DB_CONFIG['user'], password=DB_CONFIG['password'],
                           charset='utf8mb4')
    cursor = conn.cursor()
    with open(sql_path, 'r', encoding='utf-8') as f:
        for stmt in f.read().split(';'):
            stmt = stmt.strip()
            if stmt:
                cursor.execute(stmt)
    ensure_schema(cursor)
    conn.commit()
    cursor.close()
    conn.close()
    print("数据库初始化完成")


def ensure_schema(cursor):
    """兼容旧版本作业库，补齐新增字段和唯一索引。"""
    cursor.execute("USE financial_sentiment")
    columns = {
        'news': {
            'url_hash': "ALTER TABLE news ADD COLUMN url_hash CHAR(32)",
            'doc_type': "ALTER TABLE news ADD COLUMN doc_type VARCHAR(30) DEFAULT 'news' COMMENT 'news/announcement/comment/sample'",
            'stock_code': "ALTER TABLE news ADD COLUMN stock_code VARCHAR(20)",
            'stock_name': "ALTER TABLE news ADD COLUMN stock_name VARCHAR(80)",
            'author': "ALTER TABLE news ADD COLUMN author VARCHAR(120)",
            'read_count': "ALTER TABLE news ADD COLUMN read_count INT DEFAULT 0",
            'comment_count': "ALTER TABLE news ADD COLUMN comment_count INT DEFAULT 0",
        },
        'sentiment_result': {
            'lexicon_score': "ALTER TABLE sentiment_result ADD COLUMN lexicon_score FLOAT DEFAULT 0",
            'confidence': "ALTER TABLE sentiment_result ADD COLUMN confidence FLOAT DEFAULT 0",
        }
    }
    for table, alters in columns.items():
        cursor.execute("""
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA='financial_sentiment' AND TABLE_NAME=%s
        """, (table,))
        existing = {row[0] for row in cursor.fetchall()}
        for col, sql in alters.items():
            if col not in existing:
                cursor.execute(sql)
    cursor.execute("""
        SELECT id, url, title, source, publish_time FROM news
        WHERE url_hash IS NULL OR url_hash = ''
    """)
    rows = cursor.fetchall()
    for row in rows:
        raw = (row[1] or f"{row[2]}{row[3]}{row[4]}").encode('utf-8', errors='ignore')
        cursor.execute("UPDATE news SET url_hash=%s WHERE id=%s", (hashlib.md5(raw).hexdigest(), row[0]))
    for sql in [
        "ALTER TABLE news ADD UNIQUE KEY uk_url_hash (url_hash)",
        "ALTER TABLE sentiment_result ADD UNIQUE KEY uk_sentiment_news (news_id)",
        "ALTER TABLE topic_result ADD UNIQUE KEY uk_topic_news (news_id)"
    ]:
        try:
            cursor.execute(sql)
        except pymysql.err.OperationalError:
            pass

if __name__ == '__main__':
    init_db()
