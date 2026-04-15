"""
message_dispatcher.py
Nechh Robotics — Olay bazlı mesaj yönlendirme motoru
Her olay tipi → doğru formatter → doğru kanal(lar)
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode

# formatter_v2.py'den mesaj üreticileri
from formatter_v2 import (
    format_setup_activated,
    format_setup_closed,
    format_tp_hit,
    format_sl_hit,
    format_daily_summary,
    format_weekly_report,
    format_market_analysis,
    format_marketing_message,
)

# ─── KANAL ID'LERİ ───────────────────────────────────────────────────────────
CHANNELS = {
    "public":    "@NechhRobotics_Public",   # Ücretsiz, tanıtım
    "pro":       "@NechhRobotics_PRO",      # Aylık abonelik
    "vip":       "@NechhRobotics_VIP",      # Üst plan
}

# ─── OLAY TİPLERİ ────────────────────────────────────────────────────────────
class EventType(str, Enum):
    SETUP_ACTIVATED   = "setup_activated"
    SETUP_CLOSED      = "setup_closed"
    TP_HIT            = "tp_hit"
    SL_HIT            = "sl_hit"
    DAILY_SUMMARY     = "daily_summary"
    WEEKLY_REPORT     = "weekly_report"
    MARKET_ANALYSIS   = "market_analysis"
    MARKETING         = "marketing"

# ─── KURAL TABLOSU ───────────────────────────────────────────────────────────
# Her olay tipi için: hangi kanallar alır?
DISPATCH_RULES = {
    EventType.SETUP_ACTIVATED:  ["pro", "vip"],
    EventType.SETUP_CLOSED:     ["pro", "vip"],
    EventType.TP_HIT:           ["pro", "vip"],
    EventType.SL_HIT:           ["pro", "vip"],
    EventType.DAILY_SUMMARY:    ["pro", "vip"],
    EventType.WEEKLY_REPORT:    ["pro", "vip", "public"],   # haftalık public'e de gider (pazarlama)
    EventType.MARKET_ANALYSIS:  ["pro", "vip"],
    EventType.MARKETING:        ["public"],
}

# ─── ANA DISPATCHER ──────────────────────────────────────────────────────────
class MessageDispatcher:
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger("dispatcher")

    async def dispatch(self, event_type: EventType, payload: dict) -> dict:
        """
        Olayı al → mesajı üret → ilgili kanallara gönder.
        Döndürür: {channel: success/fail}
        """
        # 1. Mesajı üret
        message = self._build_message(event_type, payload)
        if not message:
            self.logger.warning(f"Mesaj üretilemedi: {event_type}")
            return {}

        # 2. Hedef kanalları belirle
        target_keys = DISPATCH_RULES.get(event_type, [])
        results = {}

        # 3. Her kanala gönder
        for key in target_keys:
            channel_id = CHANNELS.get(key)
            if not channel_id:
                continue
            try:
                await self.bot.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                results[key] = "✅ gönderildi"
                self.logger.info(f"{event_type} → {channel_id} ✅")
            except Exception as e:
                results[key] = f"❌ hata: {e}"
                self.logger.error(f"{event_type} → {channel_id} ❌ {e}")

            # Telegram flood koruması: kanallar arası 0.5s bekle
            await asyncio.sleep(0.5)

        return results

    def _build_message(self, event_type: EventType, payload: dict) -> Optional[str]:
        """Olay tipine göre doğru formatter'ı çağır."""
        try:
            match event_type:
                case EventType.SETUP_ACTIVATED:
                    return format_setup_activated(payload)
                case EventType.SETUP_CLOSED:
                    return format_setup_closed(payload)
                case EventType.TP_HIT:
                    return format_tp_hit(payload)
                case EventType.SL_HIT:
                    return format_sl_hit(payload)
                case EventType.DAILY_SUMMARY:
                    return format_daily_summary(payload)
                case EventType.WEEKLY_REPORT:
                    return format_weekly_report(payload)
                case EventType.MARKET_ANALYSIS:
                    return format_market_analysis(payload)
                case EventType.MARKETING:
                    return format_marketing_message(payload)
                case _:
                    return None
        except Exception as e:
            self.logger.error(f"Formatter hatası [{event_type}]: {e}")
            return None


# ─── KULLANIM ÖRNEKLERİ ──────────────────────────────────────────────────────
async def main():
    import os
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    dispatcher = MessageDispatcher(BOT_TOKEN)

    # Örnek 1 — Setup açıldı
    await dispatcher.dispatch(EventType.SETUP_ACTIVATED, {
        "symbol":    "BTCUSDT",
        "direction": "LONG",
        "entry":     67450.0,
        "tp":        69200.0,
        "sl":        66800.0,
        "structure": "Liquidity Sweep",
        "timeframe": "4H",
        "session":   "London",
    })

    # Örnek 2 — TP vurdu
    await dispatcher.dispatch(EventType.TP_HIT, {
        "symbol": "ETHUSDT",
        "entry":  3210.0,
        "tp":     3380.0,
        "pnl":    "+5.3%",
        "duration": "6s 42dk",
    })

    # Örnek 3 — Günlük özet
    await dispatcher.dispatch(EventType.DAILY_SUMMARY, {
        "date":       datetime.now().strftime("%d %b %Y"),
        "setups":     3,
        "wins":       2,
        "losses":     1,
        "total_pnl":  "+4.1%",
        "sentiment":  "Fear (38)",
    })


# ─── MEVCUT BOTTAN ÇAĞIRMA (tek satır entegrasyon) ───────────────────────────
# Mevcut botun sinyal ürettiği yere şunu ekle:
#
#   from message_dispatcher import MessageDispatcher, EventType
#   dispatcher = MessageDispatcher(BOT_TOKEN)
#
#   # Pozisyon açılınca:
#   asyncio.create_task(dispatcher.dispatch(EventType.SETUP_ACTIVATED, payload))
#
#   # Pozisyon kapanınca:
#   asyncio.create_task(dispatcher.dispatch(EventType.SETUP_CLOSED, payload))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
