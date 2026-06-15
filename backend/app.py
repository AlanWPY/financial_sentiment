"""Flask 后端主程序 - 金融舆情分析系统 API。"""
from __future__ import annotations

import os
import sys

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from analysis.sentiment_analysis import (
    batch_sentiment_analysis,
    get_model_evaluation,
    get_sentiment_stats,
    get_word_frequency,
    train_lda_model,
)
from backend.database import get_conn, init_db
from crawler.crawlers import inject_sample_data, run_all_crawlers


app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'),
)
CORS(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM news")
    total_news = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sentiment_result")
    analyzed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT source) FROM news")
    sources = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT topic_label) FROM topic_result")
    topics = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM news WHERE doc_type='announcement'")
    announcements = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM news WHERE doc_type='comment'")
    comments = cursor.fetchone()[0]
    cursor.execute("SELECT MAX(crawl_time) FROM news")
    last_crawl = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return jsonify({
        'total_news': total_news,
        'analyzed': analyzed,
        'sources': sources,
        'topics': topics,
        'announcements': announcements,
        'comments': comments,
        'last_crawl': last_crawl.strftime('%Y-%m-%d %H:%M') if last_crawl else '',
    })


@app.route('/api/sentiment')
def api_sentiment():
    return jsonify(get_sentiment_stats())


@app.route('/api/model-eval')
def api_model_eval():
    return jsonify(get_model_evaluation())


@app.route('/api/news')
def api_news():
    page = max(1, int(request.args.get('page', 1)))
    size = min(100, max(1, int(request.args.get('size', 20))))
    source = request.args.get('source', '')
    sentiment = request.args.get('sentiment', '')
    keyword = request.args.get('keyword', '')
    doc_type = request.args.get('doc_type', '')

    conn = get_conn()
    cursor = conn.cursor()
    where = ['1=1']
    params = []
    if source:
        where.append('n.source=%s')
        params.append(source)
    if sentiment:
        where.append('sr.sentiment_label=%s')
        params.append(sentiment)
    if doc_type:
        where.append('n.doc_type=%s')
        params.append(doc_type)
    if keyword:
        where.append('(n.title LIKE %s OR n.content LIKE %s OR n.stock_name LIKE %s OR n.stock_code LIKE %s)')
        like = f'%{keyword}%'
        params.extend([like, like, like, like])

    where_str = ' AND '.join(where)
    offset = (page - 1) * size
    cursor.execute(f"""
        SELECT n.id, n.title, n.source, n.category, n.publish_time, n.doc_type,
               n.stock_code, n.stock_name, n.url,
               sr.sentiment_label, sr.sentiment_score, tr.topic_label
        FROM news n
        LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        LEFT JOIN topic_result tr ON n.id = tr.news_id
        WHERE {where_str}
        ORDER BY n.publish_time DESC, n.id DESC
        LIMIT %s OFFSET %s
    """, params + [size, offset])
    rows = cursor.fetchall()
    cursor.execute(f"""
        SELECT COUNT(*) FROM news n
        LEFT JOIN sentiment_result sr ON n.id = sr.news_id
        LEFT JOIN topic_result tr ON n.id = tr.news_id
        WHERE {where_str}
    """, params)
    total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    news_list = [{
        'id': r[0],
        'title': r[1],
        'source': r[2],
        'category': r[3],
        'publish_time': r[4].strftime('%Y-%m-%d %H:%M') if r[4] else '',
        'doc_type': r[5] or 'news',
        'stock_code': r[6] or '',
        'stock_name': r[7] or '',
        'url': r[8] or '',
        'sentiment': r[9] or 'neutral',
        'score': round(float(r[10] or 0.5), 3),
        'topic': r[11] or '未分类',
    } for r in rows]
    return jsonify({'list': news_list, 'total': total, 'page': page, 'size': size})


@app.route('/api/crawl', methods=['POST'])
def api_crawl():
    try:
        payload = request.json or {}
        pages = int(payload.get('pages', 2))
        count = run_all_crawlers(pages=pages)
        return jsonify({'success': True, 'count': count})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    try:
        n_sentiment = batch_sentiment_analysis()
        _, _, topic_keywords = train_lda_model(n_topics=8)
        return jsonify({
            'success': True,
            'sentiment_analyzed': n_sentiment,
            'topic_keywords': {str(k): v for k, v in (topic_keywords or {}).items()},
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/wordcloud')
def api_wordcloud():
    return jsonify(get_word_frequency(100))


@app.route('/api/sources')
def api_sources():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT source FROM news ORDER BY source")
    sources = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(sources)


@app.route('/api/crawl-logs')
def api_crawl_logs():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source, status, pages, records, message, started_at, finished_at
        FROM crawl_log ORDER BY finished_at DESC LIMIT 20
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([{
        'source': r[0],
        'status': r[1],
        'pages': r[2],
        'records': r[3],
        'message': r[4],
        'started_at': r[5].strftime('%Y-%m-%d %H:%M:%S') if r[5] else '',
        'finished_at': r[6].strftime('%Y-%m-%d %H:%M:%S') if r[6] else '',
    } for r in rows])


if __name__ == '__main__':
    print("初始化数据库...")
    init_db()
    print("补充实验样本...")
    inject_sample_data()
    print("执行情感分析...")
    batch_sentiment_analysis()
    print("执行主题建模...")
    train_lda_model()
    print("启动 Web 服务：http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
