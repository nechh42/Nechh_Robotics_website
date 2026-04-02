"""
health.py - Periodic Health Check & Telegram Report
======================================================
Every 30 minutes, sends a status report to Telegram:
  - Uptime, tick count
  - Open positions + unrealized PnL
  - Closed trades + win rate
  - Current regime per symbol
  - Fear & Greed score
  - System health (memory, errors)
"""

import asyncio
import logging
from datetime import datetime, timedelta

import config
from data.sentiment import fear_greed

logger = logging.getLogger(__name__)

HEALTH_INTERVAL = int(config.HEALTH_REPORT_INTERVAL_HOURS * 3600)  # Config'ten oku
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
                    perf.max_drawdown
                )
                logger.info("[HEALTH] Weekly performance report sent")

        except Exception as e:
            logger.error(f"[HEALTH] Report error: {e}")

        await asyncio.sleep(HEALTH_INTERVAL)
