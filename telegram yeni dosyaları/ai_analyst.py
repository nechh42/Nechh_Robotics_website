"""
NECHH ROBOTICS — ai_analyst.py
Kurulum: pip install requests ollama
Ollama kurulum: https://ollama.com → ollama pull deepseek-r1:7b
"""

import requests
import logging
import ollama

from sentiment import get_sentiment
from formatter import fmt

log = logging.getLogger("ai_analyst")

# ── YAPILANDIRMA ──────────────────────────────────────────────────────────────
OLLAMA_MODEL = "deepseek-r1:7b"   # ollama pull deepseek-r1:7b
TG_TOKEN     = "BOTTOKEN_BURAYA"
TG_CHANNEL   = "@NechhRobotics_PRO"


def tg_send(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHANNEL, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.error(f"Telegram hata: {e}")


# ── AI ANALİZ FONKSİYONLARI ──────────────────────────────────────────────────

def ask_ollama(prompt: str, system: str = "") -> str:
    """Ollama'ya soru sor, cevabı string olarak döndür"""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        return response["message"]["content"].strip()
    except Exception as e:
        log.error(f"Ollama hata: {e}")
        return ""


SYSTEM_PROMPT = """Sen Nechh Robotics'in yapay zeka piyasa analistsin.
Kripto para piyasalarını analiz ediyorsun.
Türkçe yaz. Kısa ve net ol. Maksimum 5 cümle.
Asla kesin tahmin verme. Yatırım tavsiyesi değil de.
HTML tag kullanma. Sadece düz metin."""


def daily_market_analysis(fear_greed: int, news_headlines: list) -> str:
    """Günlük piyasa yorumu üret"""
    headlines_text = "\n".join([f"- {n.get('title','')}" for n in news_headlines[:5]])

    prompt = f"""
Bugünün kripto piyasa durumunu analiz et:

Fear & Greed Index: {fear_greed}/100
Son haberler:
{headlines_text}

Kısa piyasa yorumu yaz (3-4 cümle, Türkçe):
"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


def coin_analysis(symbol: str, price: float, change_24h: float,
                  volume_24h: float, market_cap: float) -> str:
    """Belirli bir coin için kısa analiz üret"""
    prompt = f"""
{symbol} coin analizi:
- Fiyat: ${price:,.4f}
- 24s değişim: {change_24h:+.2f}%
- 24s hacim: ${volume_24h:,.0f}
- Piyasa değeri: ${market_cap:,.0f}

Bu veriye göre kısa teknik yorum yap (3 cümle, Türkçe):
"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


def trade_context(symbol: str, side: str, entry: float,
                  reason: str = "") -> str:
    """Trade sinyalinin bağlamını açıkla"""
    prompt = f"""
Algoritmik sistem şu pozisyonu açtı:
- Coin: {symbol}
- Yön: {side}
- Giriş: ${entry:,.4f}
{f'- Sistem gerekçesi: {reason}' if reason else ''}

Bu pozisyon için çok kısa bağlam açıklaması yaz (2 cümle, Türkçe):
"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


# ── HAZIR MESAJ ÜRETİCİLER ───────────────────────────────────────────────────

def send_daily_brief():
    """Sabah brifingine AI yorumu ekle — scheduler.py'dan çağrılır"""
    s = get_sentiment()
    ai_comment = daily_market_analysis(s["value"], s.get("news", []))

    if not ai_comment:
        log.warning("AI yorum üretilemedi, atlanıyor")
        return

    msg = (
        f"🤖 <b>AI PİYASA YORUMU</b>\n"
        f"<code>{'─'*32}</code>\n\n"
        f"<b>🧠 Fear & Greed: {s['value']} — {s['label_tr']}</b>\n\n"
        f"{ai_comment}\n\n"
        f"<code>{'─'*32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)
    log.info("AI günlük brifing gönderildi")


def send_coin_report(symbol: str, price: float, change_24h: float,
                     volume_24h: float, market_cap: float):
    """Coin raporu gönder — haftada 3 kez scheduler'dan çağrılır"""
    analysis = coin_analysis(symbol, price, change_24h, volume_24h, market_cap)
    if not analysis:
        return

    direction = "🟢" if change_24h >= 0 else "🔴"
    sign = "+" if change_24h >= 0 else ""

    msg = (
        f"🔍 <b>COİN RAPORU — #{symbol}</b>\n"
        f"<code>{'─'*32}</code>\n\n"
        f"<b>💰 Fiyat:</b>   <code>${price:,.4f}</code>\n"
        f"<b>📊 24s:</b>     {direction} <code>{sign}{change_24h:.2f}%</code>\n"
        f"<b>📦 Hacim:</b>   <code>${volume_24h/1e6:.1f}M</code>\n\n"
        f"<b>🤖 AI Yorum:</b>\n"
        f"{analysis}\n\n"
        f"<code>{'─'*32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)
    log.info(f"Coin raporu gönderildi: {symbol}")


# ── TEST ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Ollama bağlantı testi...")
    s = get_sentiment()
    result = daily_market_analysis(s["value"], s.get("news", []))
    print(f"\nAI Yorum:\n{result}")
