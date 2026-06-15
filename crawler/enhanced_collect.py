"""增强版数据采集脚本：扩展评论、公告和多频道新闻规模。"""
from __future__ import annotations

import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from crawler.crawlers import HEADERS, _clean_text, _parse_time, log_crawl, save_record


SINA = "\u65b0\u6d6a\u8d22\u7ecf"
EASTMONEY = "\u4e1c\u65b9\u8d22\u5bcc"
GUBA = "\u4e1c\u65b9\u8d22\u5bcc\u80a1\u5427"
CNINFO = "\u5de8\u6f6e\u8d44\u8baf\u516c\u544a"

STOCK_POOL = [
    ("000001", "\u5e73\u5b89\u94f6\u884c"), ("000002", "\u4e07\u79d1A"),
    ("000333", "\u7f8e\u7684\u96c6\u56e2"), ("000568", "\u6cf8\u5dde\u8001\u7a96"),
    ("000651", "\u683c\u529b\u7535\u5668"), ("000725", "\u4eac\u4e1c\u65b9A"),
    ("000858", "\u4e94\u7cae\u6db2"), ("002230", "\u79d1\u5927\u8baf\u98de"),
    ("002415", "\u6d77\u5eb7\u5a01\u89c6"), ("002594", "\u6bd4\u4e9a\u8fea"),
    ("002714", "\u7267\u539f\u80a1\u4efd"), ("300014", "\u4ebf\u7eac\u9502\u80fd"),
    ("300059", "\u4e1c\u65b9\u8d22\u5bcc"), ("300124", "\u6c47\u5ddd\u6280\u672f"),
    ("300274", "\u9633\u5149\u7535\u6e90"), ("300308", "\u4e2d\u9645\u65ed\u521b"),
    ("300750", "\u5b81\u5fb7\u65f6\u4ee3"), ("600000", "\u6d66\u53d1\u94f6\u884c"),
    ("600030", "\u4e2d\u4fe1\u8bc1\u5238"), ("600036", "\u62db\u5546\u94f6\u884c"),
    ("600050", "\u4e2d\u56fd\u8054\u901a"), ("600104", "\u4e0a\u6c7d\u96c6\u56e2"),
    ("600276", "\u6052\u745e\u533b\u836f"), ("600309", "\u4e07\u534e\u5316\u5b66"),
    ("600519", "\u8d35\u5dde\u8305\u53f0"), ("600570", "\u6052\u751f\u7535\u5b50"),
    ("600690", "\u6d77\u5c14\u667a\u5bb6"), ("600887", "\u4f0a\u5229\u80a1\u4efd"),
    ("601012", "\u9686\u57fa\u7eff\u80fd"), ("601166", "\u5174\u4e1a\u94f6\u884c"),
    ("601318", "\u4e2d\u56fd\u5e73\u5b89"), ("601328", "\u4ea4\u901a\u94f6\u884c"),
    ("601398", "\u5de5\u5546\u94f6\u884c"), ("601628", "\u4e2d\u56fd\u4eba\u5bff"),
    ("601668", "\u4e2d\u56fd\u5efa\u7b51"), ("601688", "\u534e\u6cf0\u8bc1\u5238"),
    ("601857", "\u4e2d\u56fd\u77f3\u6cb9"), ("601888", "\u4e2d\u56fd\u4e2d\u514d"),
    ("603259", "\u836f\u660e\u5eb7\u5fb7"), ("603501", "\u97e6\u5c14\u80a1\u4efd"),
]

EASTMONEY_SECTIONS = [
    ("\u8d22\u7ecf\u8981\u95fb", "https://finance.eastmoney.com/yaowen.html"),
    ("\u56fd\u5185\u7ecf\u6d4e", "https://finance.eastmoney.com/news/cgnjj.html"),
    ("\u56fd\u9645\u7ecf\u6d4e", "https://finance.eastmoney.com/news/cgjjj.html"),
    ("\u8bc1\u5238\u8981\u95fb", "https://stock.eastmoney.com/a/czqyw.html"),
    ("\u516c\u53f8\u65b0\u95fb", "https://stock.eastmoney.com/a/cgsxw.html"),
    ("\u884c\u4e1a\u7814\u7a76", "https://stock.eastmoney.com/a/chyyj.html"),
]


def enhanced_sina_roll(pages: int = 90) -> int:
    started = datetime.now()
    count = 0
    for page in range(1, pages + 1):
        url = (
            "https://feed.mix.sina.com.cn/api/roll/get"
            f"?pageid=153&lid=2516&num=30&page={page}&r={random.random()}"
        )
        try:
            resp = requests.get(url, headers={**HEADERS, "Referer": "https://finance.sina.com.cn/"}, timeout=10)
            items = resp.json().get("result", {}).get("data", [])
            if not items:
                continue
            for item in items:
                title = item.get("title") or item.get("stitle")
                content = item.get("intro") or item.get("summary") or item.get("wapsummary") or title
                nid = save_record(
                    title=title,
                    content=content,
                    source=SINA,
                    url=item.get("url") or item.get("wapurl") or "",
                    publish_time=_parse_time(item.get("mtime") or item.get("ctime")),
                    category=item.get("media_name") or "\u8d22\u7ecf\u65b0\u95fb",
                    doc_type="news",
                    author=item.get("author"),
                    keywords=item.get("keywords"),
                )
                if nid:
                    count += 1
            time.sleep(0.12)
        except Exception:
            continue
    log_crawl(SINA, "success", pages, count, "\u589e\u5f3a\u65b0\u6d6a\u6eda\u52a8\u65b0\u95fb\u91c7\u96c6", started)
    return count


def enhanced_eastmoney_sections() -> int:
    started = datetime.now()
    count = 0
    for category, url in EASTMONEY_SECTIONS:
        try:
            resp = requests.get(url, headers={**HEADERS, "Referer": "https://www.eastmoney.com/"}, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            seen = set()
            for a in soup.select("a[href]"):
                title = _clean_text(a.get_text(" ", strip=True))
                href = a.get("href", "")
                if not href.startswith("http") or len(title) < 8 or href in seen:
                    continue
                if "eastmoney.com/a/" not in href:
                    continue
                seen.add(href)
                match = re.search(r"/a/(\d{8})", href)
                pub_time = datetime.now()
                if match:
                    try:
                        pub_time = _parse_time(match.group(1), datetime.now())
                    except Exception:
                        pass
                nid = save_record(title, title, EASTMONEY, href, pub_time, category, "news")
                if nid:
                    count += 1
            time.sleep(0.18)
        except Exception:
            continue
    log_crawl(EASTMONEY, "success", len(EASTMONEY_SECTIONS), count, "\u589e\u5f3a\u4e1c\u65b9\u8d22\u5bcc\u591a\u9891\u9053\u91c7\u96c6", started)
    return count


def enhanced_guba(pages_per_stock: int = 8) -> int:
    started = datetime.now()
    count = 0
    for stock_code, stock_name in STOCK_POOL:
        for page in range(1, pages_per_stock + 1):
            url = f"https://guba.eastmoney.com/list,{stock_code},{page},f.html"
            try:
                resp = requests.get(url, headers={**HEADERS, "Referer": "https://guba.eastmoney.com/"}, timeout=10)
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.select('a[href*="/news,"]'):
                    title = _clean_text(a.get_text(" ", strip=True))
                    href = a.get("href", "")
                    if len(title) < 6 or title in {"\u8d44\u8baf", "\u516c\u544a", "\u7814\u62a5"}:
                        continue
                    if not href.startswith("http"):
                        href = "https://guba.eastmoney.com" + href
                    parent = a.find_parent()
                    author = ""
                    if parent:
                        author_link = parent.find("a", href=re.compile(r"i\.eastmoney\.com"))
                        author = _clean_text(author_link.get_text(" ", strip=True)) if author_link else ""
                    nid = save_record(
                        title=title,
                        content=f"{stock_name}\u80a1\u5427\u8ba8\u8bba\uff1a{title}",
                        source=GUBA,
                        url=href,
                        publish_time=datetime.now(),
                        category="\u6295\u8d44\u8005\u8bc4\u8bba",
                        doc_type="comment",
                        stock_code=stock_code,
                        stock_name=stock_name,
                        author=author,
                    )
                    if nid:
                        count += 1
                time.sleep(0.08)
            except Exception:
                continue
    log_crawl(GUBA, "success", pages_per_stock * len(STOCK_POOL), count, "\u589e\u5f3a\u80a1\u5427\u8bc4\u8bba\u91c7\u96c6", started)
    return count


def enhanced_cninfo(pages: int = 8) -> int:
    started = datetime.now()
    count = 0
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    headers = {
        **HEADERS,
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    for page in range(1, pages + 1):
        try:
            resp = requests.post(url, headers=headers, data={
                "pageNum": page, "pageSize": 30, "column": "szse", "tabName": "fulltext",
                "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
                "trade": "", "seDate": "",
            }, timeout=10)
            for item in resp.json().get("announcements", []) or []:
                sec_code, sec_name = item.get("secCode"), item.get("secName")
                title = _clean_text(f"{sec_name or ''} {item.get('announcementTitle') or ''}")
                adjunct = item.get("adjunctUrl") or ""
                file_url = "http://static.cninfo.com.cn/" + adjunct if adjunct and not adjunct.startswith("http") else adjunct
                nid = save_record(
                    title=title,
                    content=title,
                    source=CNINFO,
                    url=file_url,
                    publish_time=_parse_time(item.get("announcementTime")),
                    category="\u4e0a\u5e02\u516c\u53f8\u516c\u544a",
                    doc_type="announcement",
                    stock_code=sec_code,
                    stock_name=sec_name,
                    keywords=item.get("announcementType"),
                )
                if nid:
                    count += 1
            time.sleep(0.12)
        except Exception:
            continue
    log_crawl(CNINFO, "success", pages, count, "\u589e\u5f3a\u5de8\u6f6e\u516c\u544a\u91c7\u96c6", started)
    return count


def run_enhanced_collection() -> int:
    total = 0
    total += enhanced_sina_roll(90)
    total += enhanced_eastmoney_sections()
    total += enhanced_guba(8)
    total += enhanced_cninfo(8)
    return total


if __name__ == "__main__":
    print(run_enhanced_collection())
