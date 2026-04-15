"""
NECHH ROBOTICS — ai_analyst.py
Ollama/DeepSeek ile AI piyasa analizi.
Kurulum: pip install ollama && ollama pull deepseek-r1:7b
"""

import os
import sys
import logging
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from monitoring.sentiment import get_sentiment
from monitoring.formatter import fmt

log = logging.getLogger("ai_analyst")

# Yapılandırma
OLLAMA_MODEL = getattr(config, "OLLAMA_MODEL", "deepseek-r1:7b")
TG_TOKEN = config.TELEGRAM_BOT_TOKEN
TG_CHAT_ID = config.TELEGRAM_CHAT_ID


def tg_send(text: str, chat_id: str = None):
    if not TG_TOKEN:
        return
    target = chat_id or TG_CHAT_ID
    if not target:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": target, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.error(f"Telegram hata: {e}")


def ask_ollama(prompt: str, system: str = "") -> str:
    """Ollama'ya soru sor, cevabı string olarak döndür."""
    try:
        import ollama as _ollama
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = _ollama.chat(model=OLLAMA_MODEL, messages=messages)
        return response["message"]["content"].strip()
    except ImportError:
        log.warning("ollama kütüphanesi kurulu değil: pip install ollama")
        return ""
    except Exception as e:
        log.error(f"Ollama hata: {e}")
        return ""


SYSTEM_PROMPT = """Sen Nechh Robotics'in yapay zeka piyasa analistsin.
Kripto para piyasalarını analiz ediyorsun.
Türkçe yaz. Kısa ve net ol. Maksimum 5 cümle.
Asla kesin tahmin verme. Yatırım tavsiyesi değil de.
HTML tag kullanma. Sadece düz metin."""


def daily_market_analysis(fear_greed: int, news_headlines: list) -> str:
    """Günlük piyasa yorumu üret."""
    headlines_text = "\n".join([f"- {n.get('title', '')}" for n in news_headlines[:5]])
    prompt = f"""Bugünün kripto piyasa durumunu analiz et:

Fear & Greed Index: {fear_greed}/100
Son haberler:
{headlines_text}

Kısa piyasa yorumu yaz (3-4 cümle, Türkçe):"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


def coin_analysis(symbol: str, price: float, change_24h: float,
                  volume_24h: float, market_cap: float) -> str:
    """Belirli bir coin için kısa analiz üret."""
    prompt = f"""{symbol} coin analizi:
- Fiyat: ${price:,.4f}
- 24s değişim: {change_24h:+.2f}%
- 24s hacim: ${volume_24h:,.0f}
- Piyasa değeri: ${market_cap:,.0f}

Bu veriye göre kısa teknik yorum yap (3 cümle, Türkçe):"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


def trade_context(symbol: str, side: str, entry: float,
                  reason: str = "") -> str:
    """Trade sinyalinin bağlamını açıkla."""
    prompt = f"""Algoritmik sistem şu pozisyonu açtı:
- Coin: {symbol}
- Yön: {side}
- Giriş: ${entry:,.4f}
{f'- Sistem gerekçesi: {reason}' if reason else ''}

Bu pozisyon için çok kısa bağlam açıklaması yaz (2 cümle, Türkçe):"""
    return ask_ollama(prompt, SYSTEM_PROMPT)


def send_daily_brief():
    """Sabah brifingine AI yorumu ekle — scheduler'dan çağrılır."""
    s = get_sentiment()
    ai_comment = daily_market_analysis(s["value"], s.get("news", []))

    if not ai_comment:
        log.warning("AI yorum üretilemedi, atlanıyor")
        return

    msg = (
        f"🤖 <b>AI PİYASA YORUMU</b>\n"
        f"<code>{'─' * 32}</code>\n\n"
        f"<b>🧠 Fear & Greed: {s['value']} — {s['label_tr']}</b>\n\n"
        f"{ai_comment}\n\n"
        f"<code>{'─' * 32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)
    log.info("AI günlük brifing gönderildi")


def send_coin_report(symbol: str, price: float, change_24h: float,
                     volume_24h: float, market_cap: float):
    """Coin raporu gönder."""
    analysis = coin_analysis(symbol, price, change_24h, volume_24h, market_cap)
    if not analysis:
        return

    direction = "🟢" if change_24h >= 0 else "🔴"
    sign = "+" if change_24h >= 0 else ""

    msg = (
        f"🔍 <b>COİN RAPORU — #{symbol}</b>\n"
        f"<code>{'─' * 32}</code>\n\n"
        f"<b>💰 Fiyat:</b>   <code>${price:,.4f}</code>\n"
        f"<b>📊 24s:</b>     {direction} <code>{sign}{change_24h:.2f}%</code>\n"
        f"<b>📦 Hacim:</b>   <code>${volume_24h / 1e6:.1f}M</code>\n\n"
        f"<b>🤖 AI Yorum:</b>\n"
        f"{analysis}\n\n"
        f"<code>{'─' * 32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)
    log.info(f"Coin raporu gönderildi: {symbol}")


if __name__ == "__main__":
    print("Ollama bağlantı testi...")
    s = get_sentiment()
    result = daily_market_analysis(s["value"], s.get("news", []))
    print(f"\nAI Yorum:\n{result}")
