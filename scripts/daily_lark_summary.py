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
    "surge", "rise", "rally", "gain", "approval", "inflow", "bull",
    "record", "adoption", "launch", "partnership", "tokenized",
    "growth", "buy", "support", "expansion", "institutional"
]

NEGATIVE_WORDS = [
    "hack", "drop", "fall", "lawsuit", "ban", "crackdown", "exploit",
    "outflow", "bear", "fraud", "ceo departs", "liquidation",
    "risk", "war", "probe", "selloff"
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


def sentiment_label_cn(score: int) -> str:
    if score > 0:
        return "偏多"
    if score < 0:
        return "偏空"
    return "中性"


def sentiment_label_en(score: int) -> str:
    if score > 0:
        return "Bullish"
    if score < 0:
        return "Bearish"
    return "Neutral"


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
            score = score_title(title)

            items.append({
                "title": title,
                "link": link,
                "source": source,
                "score": score
            })

    items.sort(key=lambda x: abs(x["score"]), reverse=True)
    return items[:8]


def build_summary(items):
    tz = timezone(timedelta(hours=9))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M JST")

    total = sum(i["score"] for i in items)

    market_cn = sentiment_label_cn(total)
    market_en = sentiment_label_en(total)

    bullish = sum(1 for i in items if i["score"] > 0)
    bearish = sum(1 for i in items if i["score"] < 0)
    neutral = sum(1 for i in items if i["score"] == 0)

    # 中文结论
    if market_cn == "偏多":
        conclusion_cn = "资讯面偏多，关注资金流入与机构采用。"
    elif market_cn == "偏空":
        conclusion_cn = "资讯面偏谨慎，关注监管与风险事件。"
    else:
        conclusion_cn = "资讯面中性，市场以震荡为主。"

    # 英文结论
    if market_en == "Bullish":
        conclusion_en = "News flow is bullish, watch for inflows and institutional adoption."
    elif market_en == "Bearish":
        conclusion_en = "News flow is cautious, monitor risks and regulatory pressure."
    else:
        conclusion_en = "News flow is neutral, market likely remains range-bound."

    lines = [
        "【每日加密资讯 Daily Crypto Brief】",
        f"时间 Time: {now}",
        f"整体情绪 Sentiment: {market_cn} / {market_en}",
        f"统计 Stats: 🟢 {bullish}  ⚪ {neutral}  🔴 {bearish}",
        ""
    ]

    for i, item in enumerate(items[:5], 1):
        if item["score"] > 0:
            emoji = "🟢"
        elif item["score"] < 0:
            emoji = "🔴"
        else:
            emoji = "⚪"

        lines.append(
            f"{emoji} {i}. {item['title']}\n"
            f"Source: {item['source']}\n"
            f"情绪 Sentiment: {sentiment_label_cn(item['score'])} / {sentiment_label_en(item['score'])}\n"
            f"{item['link']}\n"
        )

    lines.append(f"结论 Conclusion:\n{conclusion_cn}\n{conclusion_en}")

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
