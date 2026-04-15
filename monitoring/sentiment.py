"""
NECHH ROBOTICS — sentiment.py
Ücretsiz API: Fear & Greed Index + CryptoPanic haberler.
Kullanım: from monitoring.sentiment import get_sentiment
"""

import os
import logging
import requests

log = logging.getLogger("sentiment")

# Token .env'den veya config'ten okunur
CRYPTOPANIC_TOKEN = os.getenv("CRYPTOPANIC_TOKEN", "")


def fear_greed() -> dict:
    """Fear & Greed Index (0-100). Dün ve geçen haftayla karşılaştırma."""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=5)
        data = r.json()["data"]
        now = data[0]
        return {
            "value": int(now["value"]),
            "label": now["value_classification"],
            "yesterday": int(data[1]["value"]),
            "week_ago": int(data[6]["value"]),
        }
    except Exception as e:
        log.warning(f"Fear & Greed API hatası: {e}")
        return {"value": -1, "label": "N/A", "error": str(e)}


def crypto_news(filter_type: str = "hot", limit: int = 5) -> list:
    """CryptoPanic'ten son haberler."""
    if not CRYPTOPANIC_TOKEN:
        return []
    try:
        url = (
            f"https://cryptopanic.com/api/v1/posts/"
            f"?auth_token={CRYPTOPANIC_TOKEN}"
            f"&filter={filter_type}&public=true&limit={limit}"
        )
        r = requests.get(url, timeout=5)
        results = r.json().get("results", [])
        return [
            {
                "title": item["title"],
                "source": item["source"]["title"],
                "url": item["url"],
                "votes": item.get("votes", {}),
            }
            for item in results
        ]
    except Exception as e:
        log.warning(f"CryptoPanic API hatası: {e}")
        return []


def get_sentiment() -> dict:
    """Ana fonksiyon — Fear & Greed + haberler birlikte."""
    fg = fear_greed()
    news = crypto_news(filter_type="hot", limit=3)

    value = fg.get("value", -1)
    if value < 0:
        label_tr = "N/A"
    elif value < 25:
        label_tr = "Aşırı Korku 😱"
    elif value < 45:
        label_tr = "Korku 😰"
    elif value < 55:
        label_tr = "Nötr 😐"
    elif value < 75:
        label_tr = "Açgözlülük 😏"
    else:
        label_tr = "Aşırı Açgözlülük 🤑"

    return {
        "value": value,
        "label_en": fg.get("label", "N/A"),
        "label_tr": label_tr,
        "yesterday": fg.get("yesterday", -1),
        "week_ago": fg.get("week_ago", -1),
        "news": news,
    }


# Uyumluluk: eski health.py'da fear_greed.get_score() / .get_label() çağrılıyor
class FearGreedCompat:
    """health.py ile geriye uyumluluk sağlar."""
    def get_score(self) -> int:
        return fear_greed().get("value", 0)
    def get_label(self) -> str:
        return fear_greed().get("label", "N/A")


fear_greed_compat = FearGreedCompat()


if __name__ == "__main__":
    s = get_sentiment()
    print(f"Sentiment: {s['value']} — {s['label_tr']}")
    print(f"Dün: {s['yesterday']} | Geçen hafta: {s['week_ago']}")
    if s["news"]:
        print("\nSon haberler:")
        for n in s["news"]:
            print(f"  - {n.get('title', '')[:80]}")
