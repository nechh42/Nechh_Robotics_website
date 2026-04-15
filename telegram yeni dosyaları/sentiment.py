"""
NECHH ROBOTICS — sentiment.py
Ücretsiz API: Fear&Greed + CryptoPanic
Kurulum: pip install requests
Kullanım: from sentiment import get_sentiment
"""

import requests

CRYPTOPANIC_TOKEN = "BURAYA_TOKENI_YAZ"  # https://cryptopanic.com/developers/api/


def fear_greed() -> dict:
    """0-100 arası index, label ve dün ile geçen haftayla karşılaştırma"""
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
        return {"value": -1, "label": "N/A", "error": str(e)}


def crypto_news(filter: str = "hot", limit: int = 5) -> list:
    """
    CryptoPanic'ten son haberler
    filter: "hot" | "rising" | "bullish" | "bearish" | "important"
    """
    try:
        url = (
            f"https://cryptopanic.com/api/v1/posts/"
            f"?auth_token={CRYPTOPANIC_TOKEN}"
            f"&filter={filter}&public=true&limit={limit}"
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
        return [{"error": str(e)}]


def get_sentiment() -> dict:
    """
    Ana fonksiyon — formatter.py ile birlikte kullan:
    s = get_sentiment()
    msg = fmt.health_report(..., sentiment=s["value"])
    """
    fg = fear_greed()
    news = crypto_news(filter="hot", limit=3)

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


# Test
if __name__ == "__main__":
    s = get_sentiment()
    print(f"Sentiment: {s['value']} — {s['label_tr']}")
    print(f"Dün: {s['yesterday']} | Geçen hafta: {s['week_ago']}")
    print("\nSon haberler:")
    for n in s["news"]:
        print(f"  - {n.get('title','')[:80]}")
