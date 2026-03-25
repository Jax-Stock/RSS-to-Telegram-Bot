import os
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

POSITIVE_WORDS = [
    "surge", "rise", "rally", "gain", "approval", "inflow", "bull", "record", "adoption"
]
NEGATIVE_WORDS = [
    "hack", "drop", "fall", "lawsuit", "ban", "crackdown", "exploit", "outflow", "bear"
]

def score_title(title: str) -> int:
    t = title.lower()
    score = 0
    for w in POSITIVE_WORDS:
        if w in t:
            score += 1
    for w in NEGATIVE_WORDS:
        if w in t:
            score -= 1
    return score

def sentiment_label(score: int) -> str:
    if score > 0:
        return "偏多"
    if score < 0:
        return "偏空"
    return "中性"

def fetch_news(limit_per_feed=4):
    items = []
    seen = set()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", url)

        for entry in feed.entries[:limit_per_feed]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            norm = re.sub(r"\s+", " ", title.lower())
            if not title or norm in seen:
                continue
            seen.add(norm)
            s = score_title(title)
            items.append({
                "title": title,
                "link": link,
                "source": source,
                "score": s,
                "sentiment": sentiment_label(s),
            })

    items.sort(key=lambda x: abs(x["score"]), reverse=True)
    return items[:8]

def build_summary(items):
    tz = timezone(timedelta(hours=9))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M JST")

    total = sum(i["score"] for i in items)
    market_view = sentiment_label(total)

    lines = [
        "每日加密资讯",
        f"时间：{now}",
        f"整体情绪：{market_view}",
        ""
    ]

    for i, item in enumerate(items[:5], 1):
        lines.append(
            f"{i}. {item['title']}\n"
            f"来源：{item['source']} | 情绪：{item['sentiment']}\n"
            f"{item['link']}\n"
        )

    lines.append("结论：以上为今日重点资讯速览。")
    return "\n".join(lines)

def send_to_lark(webhook: str, text: str):
    payload = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }
    r = requests.post(webhook, json=payload, timeout=20)
    r.raise_for_status()

def main():
    webhook = os.getenv("LARK_WEBHOOK")
    if not webhook:
        raise ValueError("Missing LARK_WEBHOOK")

    items = fetch_news()
    text = build_summary(items)
    send_to_lark(webhook, text)

if __name__ == "__main__":
    main()
