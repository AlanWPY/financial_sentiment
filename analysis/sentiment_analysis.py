"""
金融舆情分析模块。

方法组合：
- SnowNLP 输出中文文本情感先验概率；
- 金融领域词典对“增持、预增、承压、退市”等词进行方向修正；
- LDA 对新闻、公告、评论进行无监督主题抽取。
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter, defaultdict

import jieba
import numpy as np
from snownlp import SnowNLP
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import silhouette_score

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from backend.database import get_conn


STOP_WORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到',
    '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '里', '来', '他', '把',
    '用', '对', '但', '还', '如果', '因为', '而', '与', '及', '或', '等', '从', '中', '对于', '通过',
    '并', '可以', '已经', '将', '其', '这些', '那些', '表示', '认为', '指出', '显示', '记者', '报道',
    '消息', '据悉', '方面', '相关', '目前', '同时', '此外', '由于', '根据', '按照', '超过', '约',
    '万元', '亿元', '公司', '市场', '投资者', '今日', '昨日', '最新', '发布', '公告'
}

POSITIVE_WORDS = {
    '上涨', '上行', '走强', '反弹', '增长', '改善', '修复', '利好', '增持', '买入', '盈利', '预增',
    '突破', '创新高', '扩张', '回暖', '净流入', '分红', '稳健', '超预期', '降准', '降息', '复苏',
    '活跃', '领涨', '增长率', '景气', '中标', '订单', '现金流', '低估值'
}

NEGATIVE_WORDS = {
    '下跌', '回落', '走弱', '承压', '亏损', '减持', '利空', '风险', '退市', '处罚', '调查', '违约',
    '暴跌', '收窄', '低迷', '净流出', '不及预期', '下修', '下滑', '放缓', '担忧', '波动', '压力',
    '监管函', '问询函', '亏损扩大', '债务', '逾期'
}

TOPIC_NAMES = {
    0: '货币政策与流动性',
    1: '股票市场与资金流',
    2: '银行保险与资管',
    3: '公司公告与业绩',
    4: '监管政策与治理',
    5: '宏观经济与通胀',
    6: '国际金融与汇率',
    7: '产业趋势与科技成长',
}


def preprocess_text(text: str | None) -> list[str]:
    if not text:
        return []
    text = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]+', ' ', text)
    words = jieba.lcut(text)
    return [w for w in words if len(w) >= 2 and w not in STOP_WORDS]


def lexicon_adjustment(text: str) -> float:
    """返回金融词典修正项，范围约束在 [-0.25, 0.25]。"""
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    if pos + neg == 0:
        return 0.0
    raw = (pos - neg) / math.sqrt(pos + neg)
    return max(-0.25, min(0.25, raw * 0.12))


def analyze_sentiment(text: str | None) -> tuple[float, str, float, float]:
    text = text or ''
    try:
        snownlp_score = float(SnowNLP(text[:2000]).sentiments)
    except Exception:
        snownlp_score = 0.5
    lex_score = lexicon_adjustment(text)
    score = max(0.0, min(1.0, snownlp_score + lex_score))
    if score >= 0.60:
        label = 'positive'
    elif score <= 0.40:
        label = 'negative'
    else:
        label = 'neutral'
    confidence = abs(score - 0.5) * 2
    return score, label, snownlp_score, lex_score if lex_score else 0.0, confidence


def batch_sentiment_analysis() -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT n.id, n.title, n.content FROM news n
        LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        WHERE sr.id IS NULL
    """)
    rows = cursor.fetchall()
    results = []
    for news_id, title, content in rows:
        text = f"{title or ''}。{content or ''}"
        score, label, snownlp_score, lex_score, confidence = analyze_sentiment(text)
        results.append((news_id, label, score, snownlp_score, lex_score, confidence))

    if results:
        cursor.executemany(
            """
            INSERT INTO sentiment_result(
                news_id, sentiment_label, sentiment_score, snownlp_score, lexicon_score, confidence
            ) VALUES(%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                sentiment_label=VALUES(sentiment_label),
                sentiment_score=VALUES(sentiment_score),
                snownlp_score=VALUES(snownlp_score),
                lexicon_score=VALUES(lexicon_score),
                confidence=VALUES(confidence),
                analyzed_time=CURRENT_TIMESTAMP
            """,
            results
        )
        conn.commit()
    cursor.close()
    conn.close()
    return len(results)


def infer_topic_label(keywords: list[str], topic_idx: int) -> str:
    joined = ''.join(keywords)
    rules = [
        ('货币政策与流动性', ['央行', '流动性', '利率', '降准', '降息', '贷款', '社融']),
        ('股票市场与资金流', ['指数', 'A股', '资金', '涨停', '沪指', '板块', '北向']),
        ('银行保险与资管', ['银行', '保险', '理财', '基金', '分红', '资管']),
        ('公司公告与业绩', ['公告', '业绩', '利润', '股东', '订单', '披露']),
        ('监管政策与治理', ['监管', '证监会', '退市', '处罚', '合规', '治理']),
        ('宏观经济与通胀', ['CPI', 'PPI', '通胀', '消费', '出口', '经济']),
        ('国际金融与汇率', ['美元', '美股', '汇率', '人民币', '美联储', '海外']),
        ('产业趋势与科技成长', ['科技', '新能源', '半导体', 'AI', '汽车', '产业']),
    ]
    for label, keys in rules:
        if any(k in joined for k in keys):
            return label
    return TOPIC_NAMES.get(topic_idx, f'主题{topic_idx + 1}')


def train_lda_model(n_topics: int = 8):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content FROM news ORDER BY publish_time DESC, id DESC LIMIT 3000")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    if len(rows) < 5:
        return None, None, {}

    ids = [r[0] for r in rows]
    texts = [' '.join(preprocess_text(f"{r[1] or ''} {r[2] or ''}")) for r in rows]
    texts = [t if t.strip() else '金融 市场' for t in texts]
    min_df = 2 if len(rows) >= 20 else 1
    vectorizer = CountVectorizer(max_df=0.95, min_df=min_df, max_features=5000)
    X = vectorizer.fit_transform(texts)
    topic_count = max(2, min(n_topics, len(rows) // 2, X.shape[1], 8))

    lda = LatentDirichletAllocation(
        n_components=topic_count,
        max_iter=30,
        learning_method='online',
        learning_offset=50.0,
        random_state=42,
    )
    lda.fit(X)
    doc_topics = lda.transform(X)
    feature_names = vectorizer.get_feature_names_out()

    topic_keywords = {}
    topic_labels = {}
    for topic_idx, topic in enumerate(lda.components_):
        words = [feature_names[i] for i in topic.argsort()[:-11:-1]]
        topic_keywords[topic_idx] = words
        topic_labels[topic_idx] = infer_topic_label(words, topic_idx)

    conn = get_conn()
    cursor = conn.cursor()
    inserts = []
    for i, news_id in enumerate(ids):
        dominant_topic = int(np.argmax(doc_topics[i]))
        inserts.append((news_id, dominant_topic, topic_labels[dominant_topic], float(doc_topics[i][dominant_topic])))
    cursor.executemany(
        """
        INSERT INTO topic_result(news_id, topic_id, topic_label, topic_prob)
        VALUES(%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            topic_id=VALUES(topic_id),
            topic_label=VALUES(topic_label),
            topic_prob=VALUES(topic_prob),
            analyzed_time=CURRENT_TIMESTAMP
        """,
        inserts
    )
    conn.commit()
    cursor.close()
    conn.close()
    return lda, vectorizer, topic_keywords


def get_sentiment_stats() -> dict:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT sentiment_label, COUNT(*) FROM sentiment_result GROUP BY sentiment_label")
    sentiment_dist = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT n.source, sr.sentiment_label, COUNT(*)
        FROM sentiment_result sr JOIN news n ON sr.news_id = n.id
        GROUP BY n.source, sr.sentiment_label
    """)
    source_sentiment = defaultdict(dict)
    for source, label, cnt in cursor.fetchall():
        source_sentiment[source][label] = cnt

    cursor.execute("""
        SELECT DATE(n.publish_time), sr.sentiment_label, COUNT(*), AVG(sr.sentiment_score)
        FROM sentiment_result sr JOIN news n ON sr.news_id = n.id
        WHERE n.publish_time >= DATE_SUB(NOW(), INTERVAL 90 DAY)
        GROUP BY DATE(n.publish_time), sr.sentiment_label
        ORDER BY DATE(n.publish_time)
    """)
    trend_data = {}
    for dt, label, cnt, avg_score in cursor.fetchall():
        key = str(dt)
        trend_data.setdefault(key, {'positive': 0, 'negative': 0, 'neutral': 0, 'avg_score': []})
        trend_data[key][label] = cnt
        if avg_score is not None:
            trend_data[key]['avg_score'].append(float(avg_score))

    cursor.execute("""
        SELECT topic_label, COUNT(*) FROM topic_result
        GROUP BY topic_label ORDER BY COUNT(*) DESC
    """)
    topic_dist = [(row[0], row[1]) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT tr.topic_label, sr.sentiment_label, COUNT(*)
        FROM topic_result tr JOIN sentiment_result sr ON tr.news_id = sr.news_id
        GROUP BY tr.topic_label, sr.sentiment_label
        ORDER BY tr.topic_label
    """)
    topic_sentiment = defaultdict(dict)
    for topic, label, cnt in cursor.fetchall():
        topic_sentiment[topic][label] = cnt

    cursor.execute("""
        SELECT n.doc_type, COUNT(*), AVG(sr.sentiment_score)
        FROM news n LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        GROUP BY n.doc_type ORDER BY COUNT(*) DESC
    """)
    doc_type_stats = [
        {'doc_type': row[0] or 'news', 'count': row[1], 'avg_score': round(float(row[2] or 0.5), 4)}
        for row in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT n.id, n.title, n.source, n.category, n.publish_time, n.doc_type,
               sr.sentiment_label, sr.sentiment_score, tr.topic_label
        FROM news n
        LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        LEFT JOIN topic_result tr ON n.id = tr.news_id
        ORDER BY n.publish_time DESC, n.id DESC LIMIT 80
    """)
    latest_news = []
    for row in cursor.fetchall():
        latest_news.append({
            'id': row[0],
            'title': row[1],
            'source': row[2],
            'category': row[3],
            'publish_time': row[4].strftime('%Y-%m-%d %H:%M') if row[4] else '',
            'doc_type': row[5] or 'news',
            'sentiment': row[6] or 'neutral',
            'score': round(float(row[7] or 0.5), 3),
            'topic': row[8] or '未分类',
        })

    cursor.close()
    conn.close()
    return {
        'sentiment_dist': sentiment_dist,
        'source_sentiment': dict(source_sentiment),
        'trend_data': trend_data,
        'topic_dist': topic_dist,
        'topic_sentiment': dict(topic_sentiment),
        'doc_type_stats': doc_type_stats,
        'latest_news': latest_news,
    }


def get_word_frequency(limit: int = 100) -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT title, content FROM news ORDER BY publish_time DESC, id DESC LIMIT 1000")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    counter = Counter()
    for title, content in rows:
        counter.update(preprocess_text(f"{title or ''} {content or ''}"))
    return [{'name': word, 'value': count} for word, count in counter.most_common(limit)]


def get_model_evaluation() -> dict:
    """生成面向报告和前端展示的无监督模型诊断指标。"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT n.title, n.content, sr.sentiment_label, sr.sentiment_score, sr.confidence, tr.topic_label, tr.topic_prob
        FROM news n
        LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        LEFT JOIN topic_result tr ON n.id = tr.news_id
        ORDER BY n.id DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    total = len(rows)
    if not total:
        return {}
    label_counts = Counter(row[2] or 'neutral' for row in rows)
    avg_conf = float(np.mean([float(row[4] or 0) for row in rows]))
    avg_topic_prob = float(np.mean([float(row[6] or 0) for row in rows]))
    entropy = 0.0
    for cnt in label_counts.values():
        p = cnt / total
        entropy -= p * math.log(p + 1e-12)
    return {
        'total_docs': total,
        'sentiment_counts': dict(label_counts),
        'avg_confidence': round(avg_conf, 4),
        'avg_topic_probability': round(avg_topic_prob, 4),
        'sentiment_entropy': round(entropy, 4),
    }
