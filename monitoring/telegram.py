"""
telegram.py - Telegram Notifications
========================================
Send trade alerts and system notifications.
Based on: crypto_fund/core_v2/telegram_notifier.py
"""

import aiohttp
import logging

import config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Async Telegram notification service"""

    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = config.TELEGRAM_ENABLED

        if not self.enabled:
            logger.warning("[TELEGRAM] Disabled - missing token or chat_id")

    async def send(self, text: str):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        logger.warning(f"[TELEGRAM] Send failed: {resp.status}")
        except Exception as e:
            logger.error(f"[TELEGRAM] Error: {e}")

    async def trade_alert(self, symbol: str, side: str, entry: float, exit_price: float, pnl: float, 
                         stop_loss: float = 0.0, take_profit: float = 0.0, risk_pct: float = 0.0):
        emoji = "🟢" if pnl > 0 else "🔴"
        sign = "+" if pnl >= 0 else ""
        pnl_pct = ((exit_price - entry) / entry * 100) if entry > 0 else 0
        
        msg = f"{emoji} <b>#{symbol.replace('USDT', '')}</b> {side}\n\n"
        msg += f"<b>Entry:</b> <code>${entry:,.4f}</code>\n"
        msg += f"<b>Exit:</b> <code>${exit_price:,.4f}</code>\n"
        
        if stop_loss > 0:
            msg += f"<b>Stop:</b> <code>${stop_loss:,.4f}</code>\n"
        if take_profit > 0:
            msg += f"<b>Target:</b> <code>${take_profit:,.4f}</code>\n"
            
        msg += f"\n<b>PnL:</b> {sign}<b>${pnl:.2f}</b> ({sign}{pnl_pct:.2f}%)\n"
        
        if risk_pct > 0:
            msg += f"<b>Risk:</b> {risk_pct:.2f}%\n"
            
        msg += f"\n✅ <i>Şeffaflık: Tüm işlemler kaydedilmiştir</i>"
        
        await self.send(msg)

    async def system_alert(self, title: str, message: str):
        await self.send(f"⚠️ <b>{title}</b>\n{message}")

    async def startup_alert(self):
        await self.send(
            "🟢 <b>WAR MACHINE STARTED</b>\n"
            f"Symbols: {len(config.SYMBOLS)}\n"
            f"Balance: ${config.INITIAL_BALANCE:,.2f}\n"
            f"Mode: {'LIVE' if config.REAL_TRADING_ENABLED else 'PAPER'}"
        )

    async def weekly_performance(self, trades: int, win_rate: float, total_pnl: float, 
                                 avg_rr: float = 0.0, max_dd: float = 0.0):
        """Haftalık performans raporu - şeffaflık ilkesi"""
        msg = "📊 <b>HAFTALIK PERFORMANS RAPORU</b>\n\n"
        msg += f"<b>İşlem Sayısı:</b> {trades}\n"
        msg += f"<b>Win Rate:</b> {win_rate:.1f}%\n"
        msg += f"<b>Net PnL:</b> <b>${total_pnl:,.2f}</b>\n"
        
        if avg_rr > 0:
            msg += f"<b>Ort. RR Ratio:</b> 1:{avg_rr:.2f}\n"
        if max_dd > 0:
            msg += f"<b>Max Drawdown:</b> ${max_dd:,.2f}\n"
            
        msg += f"\n<i>🔒 Kayıt altında tutulmuş veriler - Şeffaflık garantisiyle</i>"
        
        await self.send(msg)


telegram = TelegramNotifier()
