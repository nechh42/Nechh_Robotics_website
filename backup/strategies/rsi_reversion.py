"""
rsi_reversion.py - RSI Mean Reversion Strategy
=================================================
Candle-based RSI. No tick noise.

Logic:
  - RSI < 30 (oversold) in RANGING or TREND_UP → LONG
  - RSI > 70 (overbought) in RANGING or TREND_DOWN → SHORT
  - Confidence scales with RSI extremity

Reference: crypto_fund/strategies/mean_reversion.py
"""

import logging
import pandas as pd

import config
from engine.signal import Signal
from strategies.base import BaseStrategy
from strategies.indicators import calc_rsi, calc_macd

logger = logging.getLogger(__name__)


class RSIReversionStrategy(BaseStrategy):
    name = "RSI"

    def __init__(self):
        self.period = config.RSI_PERIOD
        self.oversold = config.RSI_OVERSOLD
        self.overbought = config.RSI_OVERBOUGHT

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        if df is None or len(df) < self.period + 5:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="Insufficient data", strategy=self.name)

        rsi_series = calc_rsi(df["close"], self.period)
        rsi = rsi_series.iloc[-1]
        price = df["close"].iloc[-1]

        if pd.isna(rsi):
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="RSI NaN", strategy=self.name, price=price)

        # MACD confirmation
        macd_line, signal_line, histogram = calc_macd(df["close"])
        macd_bull = macd_line.iloc[-1] > signal_line.iloc[-1]  # MACD above signal
        macd_bear = macd_line.iloc[-1] < signal_line.iloc[-1]  # MACD below signal

        action = "NONE"
        confidence = 0.0
        reason = f"RSI={rsi:.1f}"

        # LONG: oversold (works in all regimes, reduced conf in TREND_DOWN)
        if rsi < self.oversold:
            # Flat base + scale: 0.55 at threshold, up to 0.85 at extreme
            depth = (self.oversold - rsi) / self.oversold
            base_conf = min(0.85, 0.55 + 0.30 * depth)
            if regime == "TREND_DOWN":
                base_conf *= 0.7  # Counter-trend penalty
            if macd_bull:
                confidence = base_conf
                reason = f"RSI oversold {rsi:.1f} + MACD bull ({regime})"
            else:
                confidence = base_conf * 0.8  # Soft no-MACD penalty
                reason = f"RSI oversold {rsi:.1f} (no MACD confirm) ({regime})"
            action = "LONG"

        # SHORT: overbought (works in all regimes, reduced conf in TREND_UP)
        elif rsi > self.overbought:
            depth = (rsi - self.overbought) / (100 - self.overbought)
            base_conf = min(0.85, 0.55 + 0.30 * depth)
            if regime == "TREND_UP":
                base_conf *= 0.7  # Counter-trend penalty
            if macd_bear:
                confidence = base_conf
                reason = f"RSI overbought {rsi:.1f} + MACD bear ({regime})"
            else:
                confidence = base_conf * 0.8  # Soft no-MACD penalty
                reason = f"RSI overbought {rsi:.1f} (no MACD confirm) ({regime})"
            action = "SHORT"

        if action != "NONE":
            logger.info(f"[RSI] {symbol}: {action} conf={confidence:.2f} - {reason}")

        return Signal(symbol=symbol, action=action, confidence=confidence,
                      reason=reason, strategy=self.name, price=price)