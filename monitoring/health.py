"""
health.py - Periodic Health Check & Telegram Report
======================================================
Two report loops:
  1. Health Report (every 15 min): quick status
  2. Summary Report (every 6 hours): comprehensive overview
"""

import asyncio
import logging
from datetime import datetime, timedelta

import config

# Sentiment modülü — yeni monitoring.sentiment kullan
try:
    from monitoring.sentiment import fear_greed_compat as fear_greed
except ImportError:
    class _DummyFG:
        def get_score(self): return 0
        def get_label(self): return "N/A"
    fear_greed = _DummyFG()

logger = logging.getLogger(__name__)

HEALTH_INTERVAL = int(config.HEALTH_REPORT_INTERVAL_HOURS * 3600)  # Config'ten oku
SUMMARY_INTERVAL = int(config.SUMMARY_REPORT_INTERVAL_HOURS * 3600)  # 6 saat
WEEKLY_REPORT_DAY = 0  # Monday (0=Mon, 6=Sun)


async def health_loop(orchestrator):
    """Background loop: send health report every 30 minutes + weekly summary"""
    from monitoring.telegram import telegram

    await asyncio.sleep(60)  # Wait 1 min after startup

    while True:
        try:
            state = orchestrator.state
            status = state.get_status()
            perf = orchestrator.performance

            # Build positions summary
            pos_lines = []
            for sym, pos in state.positions.items():
                pnl_sign = "+" if pos.unrealized_pnl >= 0 else ""
                pos_lines.append(
                    f"  {sym} {pos.side} @ ${pos.entry_price:.2f} "
                    f"({pnl_sign}${pos.unrealized_pnl:.2f})"
                )
            pos_text = "\n".join(pos_lines) if pos_lines else "  None"

            # Fear & Greed
            fg = fear_greed.get_score()
            fg_label = fear_greed.get_label()

            # Build message
            uptime = datetime.now() - orchestrator._start_time if hasattr(orchestrator, '_start_time') else None
            uptime_str = str(uptime).split('.')[0] if uptime else "N/A"

            msg = (
                f"📊 <b>WAR MACHINE HEALTH</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"Uptime: {uptime_str}\n"
                f"Ticks: {orchestrator._tick_count:,}\n"
                f"Balance: <code>${status['balance']:,.2f}</code>\n"
                f"Equity: <code>${status['equity']:,.2f}</code>\n"
                f"PnL: <b>${status['total_pnl']:+,.2f}</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"Trades: {status['total_trades']} (W:{status['wins']} L:{status['losses']})\n"
                f"Win Rate: {status['win_rate']:.1f}%\n"
                f"Max DD: {perf.max_drawdown_pct:.1f}%\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"Positions ({status['num_positions']}):\n{pos_text}\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"Sentiment: {fg} ({fg_label})\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"<i>✅ Şeffaflık: Tüm işlemler kaydedilmiştir</i>"
            )

            await telegram.send(msg)
            logger.info(f"[HEALTH] Report sent: {status['total_trades']} trades, ${status['total_pnl']:+.2f}")

            # Haftalık rapor kontrolü (Pazartesi günü)
            now = datetime.now()
            if now.weekday() == WEEKLY_REPORT_DAY and now.hour == 9 and now.minute < 30:
                win_rate = status['win_rate'] if status['total_trades'] > 0 else 0.0
                avg_rr = perf.avg_rr if hasattr(perf, 'avg_rr') else 0.0
                await telegram.weekly_performance(
                    status['total_trades'],
                    win_rate,
                    status['total_pnl'],
                    avg_rr,
                    perf.max_drawdown_dollar
                )
                logger.info("[HEALTH] Weekly performance report sent")

        except Exception as e:
            logger.error(f"[HEALTH] Report error: {e}")

        await asyncio.sleep(HEALTH_INTERVAL)


async def summary_loop(orchestrator):
    """Background loop: send comprehensive summary report every 6 hours"""
    from monitoring.telegram import telegram

    await asyncio.sleep(120)  # Wait 2 min after startup

    while True:
        try:
            state = orchestrator.state
            status = state.get_status()
            perf = orchestrator.performance

            # Uptime
            uptime = datetime.now() - orchestrator._start_time if hasattr(orchestrator, '_start_time') else None
            uptime_str = str(uptime).split('.')[0] if uptime else "N/A"

            # Fear & Greed
            fg = fear_greed.get_score()
            fg_label = fear_greed.get_label()

            # Open positions detail
            pos_lines = []
            for sym, pos in state.positions.items():
                pnl_sign = "+" if pos.unrealized_pnl >= 0 else ""
                hold_time = datetime.now() - pos.entry_time if pos.entry_time else None
                hold_str = str(hold_time).split('.')[0] if hold_time else "?"
                pos_lines.append(
                    f"  {'🟢' if pos.unrealized_pnl >= 0 else '🔴'} {sym} {pos.side}\n"
                    f"    Entry: ${pos.entry_price:.4f} | SL: ${pos.stop_loss:.4f} | TP: ${pos.take_profit:.4f}\n"
                    f"    PnL: {pnl_sign}${pos.unrealized_pnl:.2f} | Hold: {hold_str}"
                )
            pos_text = "\n".join(pos_lines) if pos_lines else "  Açık pozisyon yok"

            # Recent closed trades (last 6h window)
            recent_trades = []
            cutoff = datetime.now() - timedelta(hours=6)
            for t in reversed(state.trades):
                if hasattr(t, 'exit_time') and t.exit_time and t.exit_time >= cutoff:
                    emoji = "🟢" if t.net_pnl > 0 else "🔴"
                    recent_trades.append(
                        f"  {emoji} {t.symbol} {t.side} → ${t.net_pnl:+.2f} ({t.exit_reason})"
                    )
                elif len(recent_trades) >= 10:
                    break
            recent_text = "\n".join(recent_trades) if recent_trades else "  Son 6 saatte kapanan işlem yok"

            # Win/loss streak
            streak = 0
            streak_type = ""
            for t in reversed(state.trades):
                if not streak_type:
                    streak_type = "W" if t.net_pnl > 0 else "L"
                    streak = 1
                elif (streak_type == "W" and t.net_pnl > 0) or (streak_type == "L" and t.net_pnl <= 0):
                    streak += 1
                else:
                    break
            streak_text = f"{'🔥' if streak_type == 'W' else '❄️'} {streak} ardışık {'kazanç' if streak_type == 'W' else 'kayıp'}" if streak > 0 else "Henüz işlem yok"

            # PnL emoji
            total_pnl = status['total_pnl']
            pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"

            msg = (
                f"📋 <b>WAR MACHINE — 6 SAATLİK ÖZET</b>\n"
                f"{'━' * 28}\n"
                f"🕐 Uptime: {uptime_str}\n"
                f"📡 Ticks: {orchestrator._tick_count:,}\n"
                f"{'━' * 28}\n"
                f"<b>💰 HESAP DURUMU</b>\n"
                f"  Bakiye: <code>${status['balance']:,.2f}</code>\n"
                f"  Equity: <code>${status['equity']:,.2f}</code>\n"
                f"  {pnl_emoji} Net PnL: <b>${total_pnl:+,.2f}</b>\n"
                f"  Max DD: {perf.max_drawdown_pct:.1f}%\n"
                f"{'━' * 28}\n"
                f"<b>📊 İŞLEM İSTATİSTİKLERİ</b>\n"
                f"  Toplam: {status['total_trades']} (✅{status['wins']} ❌{status['losses']})\n"
                f"  Win Rate: {status['win_rate']:.1f}%\n"
                f"  Sharpe: {perf.sharpe:.2f}\n"
                f"  {streak_text}\n"
                f"{'━' * 28}\n"
                f"<b>📌 AÇIK POZİSYONLAR ({status['num_positions']})</b>\n"
                f"{pos_text}\n"
                f"{'━' * 28}\n"
                f"<b>🔄 SON 6 SAAT İŞLEMLERİ</b>\n"
                f"{recent_text}\n"
                f"{'━' * 28}\n"
                f"🧠 Sentiment: {fg} ({fg_label})\n"
                f"{'━' * 28}\n"
                f"<i>v17.1 PTP=100% | 6h Özet Rapor</i>"
            )

            await telegram.send(msg)
            logger.info(f"[SUMMARY] 6h report sent: {status['total_trades']} trades, ${total_pnl:+.2f}")

        except Exception as e:
            logger.error(f"[SUMMARY] Report error: {e}")

        await asyncio.sleep(SUMMARY_INTERVAL)
