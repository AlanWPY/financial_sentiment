"""
金融舆情数据采集模块。

数据源覆盖三类金融舆情信号：
1. 财经新闻：新浪财经滚动新闻、东方财富财经要闻。
2. 上市公司公告：巨潮资讯公告检索。
3. 投资者评论：东方财富股吧帖子标题与元数据。

所有来源统一写入 news 表，通过 doc_type 标识文本类型。
"""
from __future__ import annotations

import hashlib
import random
import re
import time
from datetime import datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from backend.database import get_conn


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

EASTMONEY_FINANCE_PAGES = [
    ('财经要闻', 'https://finance.eastmoney.com/yaowen.html'),
    ('国内经济', 'https://finance.eastmoney.com/news/cgnjj.html'),
]

GUBA_STOCKS = [
    ('000001', '平安银行'),
    ('600519', '贵州茅台'),
    ('300750', '宁德时代'),
    ('601318', '中国平安'),
]


def _url_hash(url: str, title: str = '') -> str:
    raw = (url or title or str(time.time())).encode('utf-8', errors='ignore')
    return hashlib.md5(raw).hexdigest()


def _clean_text(text: str | None) -> str:
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text).strip()


def _parse_time(value, default: datetime | None = None) -> datetime:
    default = default or datetime.now()
    if not value:
        return default
    if isinstance(value, (int, float)):
        try:
            if value > 10_000_000_000:
                value = value / 1000
            return _cap_future_time(datetime.fromtimestamp(value), default)
        except Exception:
            return default
    value = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return _cap_future_time(datetime.strptime(value[:len(fmt)], fmt), default)
        except Exception:
            pass
    try:
        return _cap_future_time(datetime.fromtimestamp(int(value[:10])), default)
    except Exception:
        return default


def _cap_future_time(dt: datetime, fallback: datetime | None = None) -> datetime:
    """防止网页披露日期被解析成当前采集时点之后的未来新闻。"""
    now = fallback or datetime.now()
    return now if dt > now else dt


def save_record(
    title: str,
    content: str,
    source: str,
    url: str,
    publish_time: datetime,
    category: str = '综合',
    doc_type: str = 'news',
    stock_code: str | None = None,
    stock_name: str | None = None,
    author: str | None = None,
    read_count: int = 0,
    comment_count: int = 0,
    keywords: str | None = None,
) -> int | None:
    """保存一条统一格式舆情记录，按 URL 哈希去重。"""
    title = _clean_text(title)
    content = _clean_text(content) or title
    if not title:
        return None
    url = url or f"memory://{source}/{title}"
    digest = _url_hash(url, title)

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM news WHERE url_hash=%s OR url=%s LIMIT 1", (digest, url))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return None
    cursor.execute(
        """
        INSERT INTO news(
            title, content, source, url, url_hash, publish_time, category,
            doc_type, stock_code, stock_name, author, read_count, comment_count, keywords
        ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            title, content, source, url, digest, publish_time, category,
            doc_type, stock_code, stock_name, author, read_count, comment_count, keywords
        )
    )
    conn.commit()
    news_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return news_id


def log_crawl(source: str, status: str, pages: int, records: int, message: str, started_at: datetime):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO crawl_log(source,status,pages,records,message,started_at)
        VALUES(%s,%s,%s,%s,%s,%s)
        """,
        (source, status, pages, records, message[:1000], started_at)
    )
    conn.commit()
    cursor.close()
    conn.close()


def crawl_sina_finance(pages: int = 3) -> int:
    """抓取新浪财经滚动新闻 JSON 接口。"""
    started = datetime.now()
    count = 0
    try:
        for page in range(1, pages + 1):
            url = (
                "https://feed.mix.sina.com.cn/api/roll/get"
                f"?pageid=153&lid=2516&num=30&page={page}&r={random.random()}"
            )
            resp = requests.get(url, headers={**HEADERS, 'Referer': 'https://finance.sina.com.cn/'}, timeout=12)
            resp.raise_for_status()
            items = resp.json().get('result', {}).get('data', [])
            for item in items:
                title = item.get('title') or item.get('stitle')
                content = item.get('intro') or item.get('summary') or item.get('wapsummary') or title
                pub_time = _parse_time(item.get('mtime') or item.get('ctime'))
                news_id = save_record(
                    title=title,
                    content=content,
                    source='新浪财经',
                    url=item.get('url') or item.get('wapurl') or '',
                    publish_time=pub_time,
                    category=item.get('media_name') or '财经新闻',
                    doc_type='news',
                    author=item.get('author'),
                    keywords=item.get('keywords')
                )
                if news_id:
                    count += 1
            time.sleep(random.uniform(0.4, 0.9))
        log_crawl('新浪财经', 'success', pages, count, '滚动新闻采集完成', started)
    except Exception as exc:
        log_crawl('新浪财经', 'failed', pages, count, str(exc), started)
    return count


def crawl_eastmoney_finance(pages: int = 2) -> int:
    """抓取东方财富财经网页列表。"""
    started = datetime.now()
    count = 0
    errors = []
    for category, page_url in EASTMONEY_FINANCE_PAGES[:max(1, min(pages, len(EASTMONEY_FINANCE_PAGES)))]:
        try:
            resp = requests.get(page_url, headers={**HEADERS, 'Referer': 'https://www.eastmoney.com/'}, timeout=12)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            seen = set()
            for a in soup.select('a[href]'):
                title = _clean_text(a.get_text(' ', strip=True))
                href = a.get('href', '')
                if not href.startswith('http'):
                    continue
                if len(title) < 8 or '/a/' not in href or href in seen:
                    continue
                seen.add(href)
                news_id = save_record(
                    title=title,
                    content=title,
                    source='东方财富',
                    url=href,
                    publish_time=datetime.now(),
                    category=category,
                    doc_type='news'
                )
                if news_id:
                    count += 1
            time.sleep(random.uniform(0.6, 1.2))
        except Exception as exc:
            errors.append(f'{category}: {exc}')
    log_crawl('东方财富', 'partial' if errors and count else ('failed' if errors else 'success'), pages, count, '; '.join(errors) or '网页新闻采集完成', started)
    return count


def crawl_cninfo_announcements(pages: int = 2) -> int:
    """抓取巨潮资讯上市公司公告。"""
    started = datetime.now()
    count = 0
    try:
        url = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
        headers = {
            **HEADERS,
            'Referer': 'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        for page in range(1, pages + 1):
            resp = requests.post(
                url,
                headers=headers,
                data={
                    'pageNum': page,
                    'pageSize': 30,
                    'column': 'szse',
                    'tabName': 'fulltext',
                    'plate': '',
                    'stock': '',
                    'searchkey': '',
                    'secid': '',
                    'category': '',
                    'trade': '',
                    'seDate': '',
                },
                timeout=12,
            )
            resp.raise_for_status()
            for item in resp.json().get('announcements', []) or []:
                sec_code = item.get('secCode')
                sec_name = item.get('secName')
                title = _clean_text(f"{sec_name or ''} {item.get('announcementTitle') or ''}")
                adjunct = item.get('adjunctUrl') or ''
                file_url = 'http://static.cninfo.com.cn/' + adjunct if adjunct and not adjunct.startswith('http') else adjunct
                news_id = save_record(
                    title=title,
                    content=title,
                    source='巨潮资讯公告',
                    url=file_url,
                    publish_time=_parse_time(item.get('announcementTime')),
                    category='上市公司公告',
                    doc_type='announcement',
                    stock_code=sec_code,
                    stock_name=sec_name,
                    keywords=item.get('announcementType')
                )
                if news_id:
                    count += 1
            time.sleep(random.uniform(0.5, 1.0))
        log_crawl('巨潮资讯公告', 'success', pages, count, '上市公司公告采集完成', started)
    except Exception as exc:
        log_crawl('巨潮资讯公告', 'failed', pages, count, str(exc), started)
    return count


def crawl_eastmoney_guba(pages: int = 2, stocks: Iterable[tuple[str, str]] = GUBA_STOCKS) -> int:
    """抓取东方财富股吧帖子列表，作为投资者评论/讨论文本。"""
    started = datetime.now()
    count = 0
    errors = []
    for stock_code, stock_name in stocks:
        for page in range(1, pages + 1):
            url = f'https://guba.eastmoney.com/list,{stock_code},{page},f.html'
            try:
                resp = requests.get(url, headers={**HEADERS, 'Referer': 'https://guba.eastmoney.com/'}, timeout=12)
                resp.raise_for_status()
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('a[href*="/news,"]'):
                    title = _clean_text(a.get_text(' ', strip=True))
                    href = a.get('href', '')
                    if len(title) < 6 or title in {'资讯', '公告', '研报'}:
                        continue
                    if not href.startswith('http'):
                        href = 'https://guba.eastmoney.com' + href
                    parent = a.find_parent()
                    author = ''
                    if parent:
                        author_link = parent.find('a', href=re.compile(r'i\.eastmoney\.com'))
                        author = _clean_text(author_link.get_text(' ', strip=True)) if author_link else ''
                    news_id = save_record(
                        title=title,
                        content=f"{stock_name}股吧讨论：{title}",
                        source='东方财富股吧',
                        url=href,
                        publish_time=datetime.now(),
                        category='投资者评论',
                        doc_type='comment',
                        stock_code=stock_code,
                        stock_name=stock_name,
                        author=author
                    )
                    if news_id:
                        count += 1
                time.sleep(random.uniform(0.7, 1.3))
            except Exception as exc:
                errors.append(f'{stock_code}-{page}: {exc}')
    log_crawl('东方财富股吧', 'partial' if errors and count else ('failed' if errors else 'success'), pages, count, '; '.join(errors) or '股吧评论采集完成', started)
    return count


def inject_sample_data() -> int:
    """注入可复现实验样本，保证网络异常时系统仍可运行。"""
    sample_news = [
        ("央行开展逆回购操作并维持流动性合理充裕", "公开市场操作保持银行体系流动性合理充裕，资金面整体平稳，债券收益率小幅下行。", "实验样本", "sample://macro/liquidity", "2026-06-01 09:10:00", "货币政策", "news", None, None),
        ("A股三大指数集体反弹，科技成长板块领涨", "市场风险偏好改善，半导体、人工智能和高端制造板块成交活跃，北向资金净流入。", "实验样本", "sample://market/rebound", "2026-06-02 15:30:00", "股票市场", "news", None, None),
        ("上市银行分红密集落地，长期资金关注高股息资产", "多家银行披露年度分红方案，稳定现金流和低估值特征强化防御属性。", "实验样本", "sample://bank/dividend", "2026-06-03 10:20:00", "银行理财", "news", None, None),
        ("新能源车销量增长放缓，产业链盈利分化加剧", "头部企业维持规模优势，但中游材料价格回落导致部分企业利润承压。", "实验样本", "sample://industry/ev", "2026-06-04 11:00:00", "产业金融", "news", None, None),
        ("证监会强化退市监管，提升上市公司质量", "监管部门强调严厉打击财务造假和重大违法行为，市场生态有望持续优化。", "实验样本", "sample://policy/delist", "2026-06-05 16:00:00", "监管政策", "news", None, None),
        ("人民币汇率小幅走强，外资配置中国资产意愿回升", "美元指数回落叠加国内经济数据改善，人民币中间价和即期汇率同步上行。", "实验样本", "sample://fx/rmb", "2026-06-06 14:20:00", "外汇市场", "news", None, None),
        ("某上市公司披露业绩预增公告", "公司预计本期净利润同比大幅增长，主要受益于订单交付和成本控制改善。", "实验样本", "sample://ann/profit", "2026-06-07 19:00:00", "上市公司公告", "announcement", "000001", "样本公司"),
        ("股吧投资者热议高股息策略", "投资者认为银行股分红稳定，但也担忧净息差收窄压制估值修复空间。", "实验样本", "sample://comment/bank", "2026-06-08 12:00:00", "投资者评论", "comment", "000001", "平安银行"),
        ("商品价格回落拖累周期板块表现", "铜、原油等大宗商品价格波动加大，周期行业盈利预期有所下修。", "实验样本", "sample://commodity/down", "2026-06-09 10:00:00", "大宗商品", "news", None, None),
        ("基金发行回暖，权益产品关注度上升", "市场反弹带动权益基金净值修复，新发基金募集规模较前期改善。", "实验样本", "sample://fund/recover", "2026-06-10 09:00:00", "基金市场", "news", None, None),
    ]
    count = 0
    for title, content, source, url, pub_time, category, doc_type, code, name in sample_news:
        news_id = save_record(
            title=title,
            content=content,
            source=source,
            url=url,
            publish_time=_parse_time(pub_time),
            category=category,
            doc_type=doc_type,
            stock_code=code,
            stock_name=name
        )
        if news_id:
            count += 1
    return count


def run_all_crawlers(pages: int = 3) -> int:
    """运行全部爬虫，并在数据不足时补充可复现实验样本。"""
    total = 0
    total += crawl_sina_finance(pages)
    total += crawl_eastmoney_finance(pages)
    total += crawl_cninfo_announcements(pages)
    total += crawl_eastmoney_guba(max(1, min(pages, 3)))
    if total < 15:
        total += inject_sample_data()
    return total


if __name__ == '__main__':
    print(f"新增记录：{run_all_crawlers(pages=2)}")
