"""
NECHH ROBOTICS — scheduler.py
Zamanlı görevler: health raporu, sabah brifing, haftalık rapor.
Ayrı process olarak çalışır: python -m monitoring.scheduler
"""

import asyncio
import logging
import os
import sys
import sqlite3
import requests
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from monitoring.formatter import fmt
from monitoring.sentiment import get_sentiment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scheduler")

# ── TELEGRAM ──────────────────────────────────────────────────────────────────

TG_TOKEN = config.TELEGRAM_BOT_TOKEN
TG_CHAT_ID = config.TELEGRAM_CHAT_ID


def tg_send(text: str, chat_id: str = None):
    """Telegram mesaj gönder (mevcut bota dokunmaz, direkt API)."""
    if not TG_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN tanımlı değil")
        return
    target = chat_id or TG_CHAT_ID
    if not target:
        log.warning("TELEGRAM_CHAT_ID tanımlı değil")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": target, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        log.info("Mesaj gönderildi")
    except Exception as e:
        log.error(f"Telegram hata: {e}")


# ── VERİ KAYNAĞI: WAR MACHINE DB ─────────────────────────────────────────────

def get_bot_stats() -> dict:
    """War Machine SQLite DB'den gerçek istatistikleri çek."""
    db_path = config.DB_PATH

    defaults = {
        "uptime": "N/A",
        "ticks": 0,
        "balance": config.INITIAL_BALANCE,
        "equity": config.INITIAL_BALANCE,
        "pnl": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "max_dd": 0.0,
        "open_positions": [],
        "mode": "LIVE" if config.REAL_TRADING_ENABLED else "PAPERTRADE",
    }

    if not os.path.exists(db_path):
        log.warning(f"DB bulunamadı: {db_path}")
        return defaults

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Trade istatistikleri
        total = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        wins = c.execute("SELECT COUNT(*) FROM trades WHERE net_pnl > 0").fetchone()[0]
        losses = total - wins
        pnl = c.execute("SELECT COALESCE(SUM(net_pnl), 0) FROM trades").fetchone()[0]
        win_rate = (wins / total * 100) if total > 0 else 0.0

        # Max drawdown hesapla
        rows = c.execute("SELECT net_pnl FROM trades ORDER BY timestamp ASC").fetchall()
        peak = 0.0
        max_dd = 0.0
        cumulative = 0.0
        for (net,) in rows:
            cumulative += net
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = (max_dd / config.INITIAL_BALANCE * 100) if config.INITIAL_BALANCE else 0

        # Açık pozisyonlar
        positions = []
        try:
            pos_rows = c.execute("SELECT symbol, side, entry_price FROM positions").fetchall()
            for sym, side, entry in pos_rows:
                positions.append({"symbol": sym, "side": side, "pnl": 0.0})
        except Exception:
            pass

        # Balance
        balance = config.INITIAL_BALANCE + pnl

        # Uptime (son event'ten veya ilk trade'den)
        first_trade = c.execute("SELECT MIN(timestamp) FROM trades").fetchone()[0]
        if first_trade:
            try:
                start = datetime.fromisoformat(first_trade)
                uptime = str(datetime.now() - start).split('.')[0]
            except Exception:
                uptime = "N/A"
        else:
            uptime = "N/A"

        conn.close()

        return {
            "uptime": uptime,
            "ticks": 0,  # DB'de tick sayısı yok, orchestrator bilgisi
            "balance": balance,
            "equity": balance,
            "pnl": pnl,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "max_dd": max_dd_pct,
            "open_positions": positions,
            "mode": "LIVE" if config.REAL_TRADING_ENABLED else "PAPERTRADE",
        }
    except Exception as e:
        log.error(f"DB okuma hatası: {e}")
        return defaults


def get_best_worst_trade() -> tuple:
    """En iyi ve en kötü trade'i döndür."""
    db_path = config.DB_PATH
    best = {"symbol": "N/A", "pnl": 0.0}
    worst = {"symbol": "N/A", "pnl": 0.0}
    if not os.path.exists(db_path):
        return best, worst
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        row = c.execute("SELECT symbol, net_pnl FROM trades ORDER BY net_pnl DESC LIMIT 1").fetchone()
        if row:
            best = {"symbol": row[0], "pnl": row[1]}
        row = c.execute("SELECT symbol, net_pnl FROM trades ORDER BY net_pnl ASC LIMIT 1").fetchone()
        if row:
            worst = {"symbol": row[0], "pnl": row[1]}
        conn.close()
    except Exception as e:
        log.error(f"Best/worst trade hatası: {e}")
    return best, worst


def get_week_start_balance() -> float:
    """Haftanın başındaki bakiyeyi hesapla."""
    db_path = config.DB_PATH
    if not os.path.exists(db_path):
        return config.INITIAL_BALANCE
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # Bu haftanın Pazartesi 00:00'dan önceki toplam PnL
        now = datetime.now()
        # Haftanın başı
        days_since_monday = now.weekday()
        monday = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        monday = monday - timedelta(days=days_since_monday)
        pnl_before = c.execute(
            "SELECT COALESCE(SUM(net_pnl), 0) FROM trades WHERE timestamp < ?",
            (monday.isoformat(),)
        ).fetchone()[0]
        conn.close()
        return config.INITIAL_BALANCE + pnl_before
    except Exception as e:
        log.error(f"Week start balance hatası: {e}")
        return config.INITIAL_BALANCE


# ── GÖREVLER ──────────────────────────────────────────────────────────────────

async def job_health():
    """Her 4 saatte bir health raporu gönder."""
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
    """Her sabah 08:00 UTC — piyasa brifing (sentiment ağırlıklı)."""
    log.info("Sabah brifing hazırlanıyor...")
    s = get_sentiment()

    delta_day = s["value"] - s["yesterday"]
    delta_week = s["value"] - s["week_ago"]
    sign_d = "+" if delta_day >= 0 else ""
    sign_w = "+" if delta_week >= 0 else ""

    msg = (
        f"🌅 <b>GÜNLÜK PİYASA BRİFİNGİ</b>\n"
        f"<code>{'─' * 32}</code>\n\n"
        f"<b>🧠 Fear & Greed:</b> <code>{s['value']} — {s['label_tr']}</code>\n"
        f"<b>📅 Dün:</b>         <code>{s['yesterday']} ({sign_d}{delta_day:+d})</code>\n"
        f"<b>📆 Geçen hafta:</b> <code>{s['week_ago']} ({sign_w}{delta_week:+d})</code>\n\n"
        f"<code>{'─' * 32}</code>\n"
        f"<b>🔥 Gündem Haberleri:</b>\n"
    )
    for n in s.get("news", [])[:3]:
        title = n.get("title", "")[:70]
        source = n.get("source", "")
        msg += f"• <i>{title}</i> — {source}\n"

    msg += (
        f"\n<code>{'─' * 32}</code>\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    tg_send(msg)


async def job_weekly():
    """Her Pazar 20:00 UTC — haftalık performans raporu."""
    log.info("Haftalık rapor hazırlanıyor...")
    stats = get_bot_stats()
    best, worst = get_best_worst_trade()
    balance_start = get_week_start_balance()

    msg = fmt.weekly_report(
        week_no=datetime.utcnow().isocalendar()[1],
        total_trades=stats["total_trades"],
        wins=stats["wins"],
        losses=stats["losses"],
        win_rate=stats["win_rate"],
        gross_pnl=stats["pnl"],
        best_trade=best,
        worst_trade=worst,
        max_dd=stats["max_dd"],
        balance_start=balance_start,
        balance_end=stats["balance"],
        mode=stats["mode"],
    )
    tg_send(msg)


# ── SCHEDULER BAŞLAT ──────────────────────────────────────────────────────────

async def main():
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(job_health, IntervalTrigger(hours=4), id="health")
    scheduler.add_job(job_morning_brief, CronTrigger(hour=8, minute=0), id="morning")
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
