"""
telegram.py - Telegram Notifications
========================================
Send trade alerts and system notifications.
Based on: crypto_fund/core_v2/telegram_notifier.py
"""

import aiohttp
import logging

import config
from monitoring.formatter import fmt

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
        pnl_pct = ((exit_price - entry) / entry * 100) if entry > 0 else 0
        msg = fmt.trade_close(
            symbol=symbol, side=side, entry=entry, exit_price=exit_price,
            pnl=pnl, pnl_pct=pnl_pct, duration="—",
        )
        await self.send(msg)

    async def system_alert(self, title: str, message: str):
        msg = fmt.system_alert(title=title, message=message)
        await self.send(msg)

    async def startup_alert(self):
        mode = "LIVE" if config.REAL_TRADING_ENABLED else "PAPER"
        msg = fmt.startup(
            mode=mode, balance=config.INITIAL_BALANCE,
            symbols=len(config.SYMBOLS), strategy="COMBO V1",
        )
        await self.send(msg)

    async def weekly_performance(self, trades: int, win_rate: float, total_pnl: float, 
                                 avg_rr: float = 0.0, max_dd: float = 0.0):
        """Haftalık performans raporu - şeffaflık ilkesi"""
        wins = int(trades * win_rate / 100) if trades else 0
        losses = trades - wins
        msg = fmt.weekly_report(
            total_trades=trades, wins=wins, losses=losses,
            win_rate=win_rate, pnl=total_pnl, max_dd=max_dd,
            best_trade="—", worst_trade="—",
        )
        await self.send(msg)

    async def liquidation_spike_alert(self, symbol: str, risk_level: str, liquidation_price: float, 
                                      current_price: float, distance_pct: float, liquidation_count: int = 0,
                                      volume_spike: float = 0.0, volatility_spike: float = 0.0):
        """
        Likidation İğnesi (Liquidation Spike) Uyarısı
        Risk seviye: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
        Binance order book'tan algılanan masif liquidation olayları
        """
        risk_emoji = {
            'LOW': '🟡',      # Düşük risk
            'MEDIUM': '🟠',   # Orta risk - pozisyon kontrol etmelisiniz
            'HIGH': '🔴',     # Yüksek risk - stop loss önerilir
            'CRITICAL': '🚨'  # Kritik - acil çıkış tavsiyesi
        }
        
        emoji = risk_emoji.get(risk_level, '⚠️')
        
        msg = fmt.liquidation_spike(
            symbol=symbol, risk_level=risk_level,
            liq_price=liquidation_price, current_price=current_price,
            distance_pct=distance_pct,
        )
        await self.send(msg)

    async def top_3_coins_signal(self, coin: str, pattern: str, win_rate: float, 
                                 signal_reason: str, confidence: float):
        """
        Top 3 Coin Edge Pattern Sinyali
        EDGE DISCOVERY v3 tarafından tespit edilen yüksek kalite sinyaller
        """
        msg = fmt.top_coins_signal(
            coin=coin, pattern=pattern, win_rate=win_rate,
            signal_reason=signal_reason, confidence=confidence,
        )
        await self.send(msg)


telegram = TelegramNotifier()
