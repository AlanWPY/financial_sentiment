"""金融舆情与股票指数相关性研究。"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from backend.database import get_conn


INDEXES = {
    "上证指数": {"eastmoney": "1.000001", "sina": "sh000001"},
    "深证成指": {"eastmoney": "0.399001", "sina": "sz399001"},
    "创业板指": {"eastmoney": "0.399006", "sina": "sz399006"},
}


def fetch_eastmoney_kline(secid: str, beg: str, end: str, klt: int = 101) -> pd.DataFrame:
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt={klt}&fqt=1&beg={beg}&end={end}"
    )
    last_error = None
    for attempt in range(4):
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=20)
            resp.raise_for_status()
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1.0 + attempt * 0.8)
    else:
        raise last_error
    data = resp.json().get("data") or {}
    rows = []
    for line in data.get("klines") or []:
        parts = line.split(",")
        rows.append({
            "time": pd.to_datetime(parts[0]),
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "volume": float(parts[5]),
            "amount": float(parts[6]),
            "amplitude": float(parts[7]),
            "return_pct": float(parts[8]),
            "change": float(parts[9]),
            "turnover": float(parts[10]),
            "index_name": data.get("name", secid),
        })
    return pd.DataFrame(rows)


def fetch_sina_kline(symbol: str, scale: int = 240, datalen: int = 120) -> pd.DataFrame:
    url = (
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}"
    )
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    rows = []
    for item in data:
        rows.append({
            "time": pd.to_datetime(item["day"]),
            "open": float(item["open"]),
            "close": float(item["close"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "volume": float(item.get("volume") or 0),
            "amount": float(item.get("amount") or 0),
        })
    df = pd.DataFrame(rows).sort_values("time")
    if not df.empty:
        df["return_pct"] = df["close"].pct_change() * 100
        df.loc[df["return_pct"].isna(), "return_pct"] = (df["close"] / df["open"] - 1) * 100
        df["amplitude"] = (df["high"] - df["low"]) / df["open"] * 100
        df["change"] = df["close"] - df["open"]
        df["turnover"] = np.nan
    return df


def get_daily_sentiment(start_date: str = "2026-06-08") -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT DATE(n.publish_time) AS date,
               COUNT(*) AS news_count,
               AVG(sr.sentiment_score) AS avg_score,
               SUM(sr.sentiment_label='positive') AS positive_count,
               SUM(sr.sentiment_label='negative') AS negative_count,
               SUM(sr.sentiment_label='neutral') AS neutral_count,
               AVG(sr.confidence) AS avg_confidence
        FROM news n JOIN sentiment_result sr ON n.id = sr.news_id
        WHERE DATE(n.publish_time) >= %s
        GROUP BY DATE(n.publish_time)
        HAVING COUNT(*) >= 20
        ORDER BY date
    """
    df = pd.read_sql(sql, conn, params=[start_date])
    conn.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["sentiment_index"] = (df["positive_count"] - df["negative_count"]) / df["news_count"]
    df["negative_ratio"] = df["negative_count"] / df["news_count"]
    df["positive_ratio"] = df["positive_count"] / df["news_count"]
    return df


def get_hourly_sentiment(start_date: str = "2026-06-08") -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT DATE_FORMAT(n.publish_time, '%%Y-%%m-%%d %%H:00:00') AS hour_time,
               COUNT(*) AS news_count,
               AVG(sr.sentiment_score) AS avg_score,
               SUM(sr.sentiment_label='positive') AS positive_count,
               SUM(sr.sentiment_label='negative') AS negative_count,
               SUM(sr.sentiment_label='neutral') AS neutral_count
        FROM news n JOIN sentiment_result sr ON n.id = sr.news_id
        WHERE DATE(n.publish_time) >= %s
        GROUP BY DATE_FORMAT(n.publish_time, '%%Y-%%m-%%d %%H:00:00')
        HAVING COUNT(*) >= 5
        ORDER BY hour_time
    """
    df = pd.read_sql(sql, conn, params=[start_date])
    conn.close()
    if df.empty:
        return df
    df["hour_time"] = pd.to_datetime(df["hour_time"])
    df["sentiment_index"] = (df["positive_count"] - df["negative_count"]) / df["news_count"]
    df["negative_ratio"] = df["negative_count"] / df["news_count"]
    return df


def persist_daily_market(df: pd.DataFrame):
    if df.empty:
        return
    conn = get_conn()
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute(
            "DELETE FROM market_index WHERE index_name=%s AND trade_date=%s",
            (row["index_name"], row["time"].date()),
        )
        cursor.execute(
            """
            INSERT INTO market_index(index_name,trade_date,open_price,close_price,high_price,low_price,volume,change_pct)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                row["index_name"], row["time"].date(), row["open"], row["close"], row["high"],
                row["low"], int(row["volume"]), row["return_pct"],
            ),
        )
    conn.commit()
    cursor.close()
    conn.close()


def run_correlation_study(out_dir: str | Path | None = None) -> dict:
    out_dir = Path(out_dir or Path(__file__).resolve().parents[2] / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    start, end = "20260608", "20260612"

    daily_sent = get_daily_sentiment("2026-06-08")
    daily_market = []
    hourly_market = []
    for name, ids in INDEXES.items():
        try:
            d = fetch_sina_kline(ids["sina"], scale=240, datalen=80)
            d = d[(d["time"] >= pd.Timestamp("2026-06-08")) & (d["time"] <= pd.Timestamp("2026-06-12"))]
            h = fetch_sina_kline(ids["sina"], scale=60, datalen=160)
            h = h[(h["time"] >= pd.Timestamp("2026-06-08")) & (h["time"] <= pd.Timestamp("2026-06-12 23:59:59"))]
        except Exception:
            d = fetch_eastmoney_kline(ids["eastmoney"], start, end, klt=101)
            h = fetch_eastmoney_kline(ids["eastmoney"], start, end, klt=60)
        if not d.empty:
            d["index_name"] = name
            daily_market.append(d)
            persist_daily_market(d)
        if not h.empty:
            h["index_name"] = name
            hourly_market.append(h)
    daily_market = pd.concat(daily_market, ignore_index=True) if daily_market else pd.DataFrame()
    hourly_market = pd.concat(hourly_market, ignore_index=True) if hourly_market else pd.DataFrame()

    daily_market.to_csv(out_dir / "market_index_daily.csv", index=False, encoding="utf-8-sig")
    daily_sent.to_csv(out_dir / "sentiment_daily.csv", index=False, encoding="utf-8-sig")

    corr_rows = []
    merged_by_index = {}
    for index_name in INDEXES:
        m = daily_market[daily_market["index_name"] == index_name].copy()
        if m.empty or daily_sent.empty:
            continue
        m["date"] = m["time"].dt.normalize()
        merged = pd.merge(daily_sent, m, on="date", how="inner")
        merged = merged.sort_values("date")
        merged["next_return_pct"] = merged["return_pct"].shift(-1)
        merged_by_index[index_name] = merged
        for y in ["return_pct", "next_return_pct", "amplitude"]:
            for x in ["sentiment_index", "avg_score", "negative_ratio", "news_count"]:
                valid = merged[[x, y]].dropna()
                corr = valid[x].corr(valid[y]) if len(valid) >= 3 else np.nan
                corr_rows.append({"index_name": index_name, "x": x, "y": y, "corr": corr, "n": len(valid)})
    corr_df = pd.DataFrame(corr_rows)
    corr_df.to_csv(out_dir / "sentiment_market_correlation.csv", index=False, encoding="utf-8-sig")

    hourly_sent = get_hourly_sentiment("2026-06-08")
    lag_rows = []
    sh_hour = hourly_market[hourly_market["index_name"] == "上证指数"].copy() if not hourly_market.empty else pd.DataFrame()
    if not sh_hour.empty and not hourly_sent.empty:
        sh_hour["hour_time"] = sh_hour["time"].dt.floor("h")
        hmerged = pd.merge(hourly_sent, sh_hour, on="hour_time", how="inner").sort_values("hour_time")
        for lag in range(0, 5):
            x = hmerged["sentiment_index"].shift(lag)
            y = hmerged["return_pct"]
            valid = pd.concat([x.rename("sentiment"), y.rename("return")], axis=1).dropna()
            lag_rows.append({"lag_hours": lag, "corr": valid["sentiment"].corr(valid["return"]) if len(valid) >= 5 else np.nan, "n": len(valid)})
        hmerged.to_csv(out_dir / "hourly_sentiment_market_merged.csv", index=False, encoding="utf-8-sig")
    lag_df = pd.DataFrame(lag_rows)
    lag_df.to_csv(out_dir / "hourly_lag_correlation.csv", index=False, encoding="utf-8-sig")

    return {
        "daily_sentiment": daily_sent,
        "daily_market": daily_market,
        "correlation": corr_df,
        "lag_correlation": lag_df,
        "merged_by_index": merged_by_index,
    }


if __name__ == "__main__":
    result = run_correlation_study()
    print(result["correlation"])
    print(result["lag_correlation"])
