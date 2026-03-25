import os
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta

# ====== RSS ======
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

# ====== OpenAI ======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ====== 获取新闻 ======
def fetch_news():
    items = []
    seen = set()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", url)

        for entry in feed.entries[:4]:
            title = entry.get("title", "")
            link = entry.get("link", "")

            norm = re.sub(r"\s+", " ", title.lower())
            if norm in seen:
                continue
            seen.add(norm)

            items.append({
                "title": title,
                "link": link,
                "source": source
            })

    return items[:6]


# ====== 价格 ======
def fetch_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum",
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        r = requests.get(url, params=params, timeout=10).json()

        return (
            r["bitcoin"]["usd"],
            r["bitcoin"]["usd_24h_change"],
            r["ethereum"]["usd"],
            r["ethereum"]["usd_24h_change"],
        )
    except:
        return None, None, None, None


# ====== AI总结 ======
def ai_summary(news):
    if not OPENAI_API_KEY:
        return "AI summary unavailable"

    titles = "\n".join([f"- {n['title']}" for n in news])

    prompt = f"""
You are a crypto industry analyst.

Based on the following news headlines, produce:

1. Key themes (2-3 points)
2. Industry trend insight
3. Risk or opportunity signals

Keep it concise, professional, and insightful.

News:
{titles}
"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=20
        )

        result = response.json()
        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"AI summary error: {e}"


# ====== 构建消息 ======
def build_message(news):
    tz = timezone(timedelta(hours=9))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M JST")

    btc, btc_chg, eth, eth_chg = fetch_prices()

    if btc:
        price_text = (
            f"BTC {btc:.0f}（{btc_chg:+.2f}%）\n"
            f"ETH {eth:.0f}（{eth_chg:+.2f}%）"
        )
    else:
        price_text = "N/A"

    ai_text = ai_summary(news)

    lines = [
        "【每日加密行业简报】",
        f"📅 {now}",
        "",
        "💰 市场：",
        price_text,
        "",
        "🧠 行业洞察：",
        ai_text,
        "",
        "📰 关键新闻：",
    ]

    for i, n in enumerate(news, 1):
        lines.append(f"{i}. {n['title']}")
        lines.append(n["link"])
        lines.append("")

    return "\n".join(lines)


# ====== 发送 ======
def send_lark(webhook, text):
    payload = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }
    requests.post(webhook, json=payload, timeout=20)


# ====== 主程序 ======
def main():
    webhook = os.getenv("LARK_WEBHOOK")
    if not webhook:
        raise ValueError("Missing LARK_WEBHOOK")

    news = fetch_news()
    message = build_message(news)
    send_lark(webhook, message)


if __name__ == "__main__":
    main()
