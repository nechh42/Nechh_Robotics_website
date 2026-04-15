"""
NECHH ROBOTICS — scheduler.py
Kurulum: pip install apscheduler requests
Kullanım: python scheduler.py (ayrı process olarak çalışır)
"""

import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Kendi modüllerin
from formatter import fmt
from sentiment import get_sentiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scheduler")

# ── TELEGRAM GÖNDER (mevcut botuna dokunma, direkt API çağrısı) ──────────────
import requests

TG_TOKEN   = "BOTTOKEN_BURAYA"
TG_CHANNEL = "@NechhRobotics_PRO"   # ya da -100xxxx chat_id

def tg_send(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHANNEL, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        log.info("Mesaj gönderildi")
    except Exception as e:
        log.error(f"Telegram hata: {e}")


# ── VERİ KAYNAĞI: mevcut botundan çek ────────────────────────────────────────
# Botun bir JSON endpoint veya dosya bırakıyorsa oradan oku.
# Şimdilik örnek sabit veri — sen kendi botunun verisiyle doldur.

def get_bot_stats() -> dict:
    """
    Mevcut botunun istatistiklerini döndür.
    Seçenek 1: Botun bir stats.json dosyasına yazıyorsa → json.load()
    Seçenek 2: Botun bir local HTTP endpoint'i varsa → requests.get()
    Seçenek 3: Doğrudan DB'den oku
    Şimdilik ÖRNEK veri — kendi entegrasyonunu yaz.
    """
    return {
        "uptime": "3 days, 02:10:00",
        "ticks": 2_100_000,
        "balance": 10_045.20,
        "equity": 10_045.20,
        "pnl": 45.20,
        "total_trades": 24,
        "wins": 7,
        "losses": 17,
        "win_rate": 29.2,
        "max_dd": 0.3,
        "open_positions": [],
        "mode": "PAPERTRADE",
    }


# ── GÖREVLER ──────────────────────────────────────────────────────────────────

async def job_health():
    """Her 4 saatte bir health raporu gönder"""
    log.info("Health raporu hazırlanıyor...")
    stats = get_bot_stats()
    s = get_sentiment()
    msg = fmt.health_report(
        uptime=stats["uptime"],
        ticks=stats["ticks"],
        balance=stats["balance"],
        equity=stats["equity"],
        pnl=stats["pnl"],
        total_trades=stats["total_trades"],
        wins=stats["wins"],
        losses=stats["losses"],
        win_rate=stats["win_rate"],
        max_dd=stats["max_dd"],
        open_positions=stats["open_positions"],
        sentiment=s["value"],
        mode=stats["mode"],
    )
    tg_send(msg)


async def job_morning_brief():
    """Her sabah 08:00 UTC — günlük piyasa özeti (sentiment ağırlıklı)"""
    log.info("Sabah brifing hazırlanıyor...")
    s = get_sentiment()

    delta_day  = s["value"] - s["yesterday"]
    delta_week = s["value"] - s["week_ago"]
    sign_d = "+" if delta_day  >= 0 else ""
    sign_w = "+" if delta_week >= 0 else ""

    msg = (
        f"🌅 <b>GÜNLÜK PİYASA BRİFİNGİ</b>\n"
        f"<code>{'─'*32}</code>\n\n"
        f"<b>🧠 Fear & Greed:</b> <code>{s['value']} — {s['label_tr']}</code>\n"
        f"<b>📅 Dün:</b>         <code>{s['yesterday']} ({sign_d}{delta_day:+d})</code>\n"
        f"<b>📆 Geçen hafta:</b> <code>{s['week_ago']} ({sign_w}{delta_week:+d})</code>\n\n"
        f"<code>{'─'*32}</code>\n"
        f"<b>🔥 Gündem Haberleri:</b>\n"
    )
    for n in s.get("news", [])[:3]:
        title = n.get("title", "")[:70]
        source = n.get("source", "")
        msg += f"• <i>{title}</i> — {source}\n"

    msg += (
        f"\n<code>{'─'*32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)


async def job_weekly():
    """Her Pazar 20:00 UTC — haftalık performans raporu"""
    log.info("Haftalık rapor hazırlanıyor...")
    stats = get_bot_stats()
    # Haftalık verileri botundan al — şimdilik örnek
    msg = fmt.weekly_report(
        week_no=datetime.utcnow().isocalendar()[1],
        total_trades=stats["total_trades"],
        wins=stats["wins"],
        losses=stats["losses"],
        win_rate=stats["win_rate"],
        gross_pnl=stats["pnl"],
        best_trade={"symbol": "ETHUSDT", "pnl": 14.2},   # botundan çek
        worst_trade={"symbol": "SOLUSDT", "pnl": -3.1},  # botundan çek
        max_dd=stats["max_dd"],
        balance_start=10_000.0,   # haftanın başı bakiyesi
        balance_end=stats["balance"],
        mode=stats["mode"],
    )
    tg_send(msg)


# ── SCHEDULER BAŞLAT ──────────────────────────────────────────────────────────

async def main():
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Health: her 4 saatte bir
    scheduler.add_job(job_health, IntervalTrigger(hours=4), id="health")

    # Sabah brifing: her gün 08:00 UTC
    scheduler.add_job(job_morning_brief, CronTrigger(hour=8, minute=0), id="morning")

    # Haftalık: Pazar 20:00 UTC
    scheduler.add_job(job_weekly, CronTrigger(day_of_week="sun", hour=20, minute=0), id="weekly")

    scheduler.start()
    log.info("Scheduler başladı — Ctrl+C ile durdur")

    # İlk çalışmada hemen bir health gönder
    await job_health()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Scheduler durduruldu")


if __name__ == "__main__":
    asyncio.run(main())
