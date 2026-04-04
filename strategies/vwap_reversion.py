"""
vwap_reversion.py - VWAP Mean Reversion Strategy
===================================================
Price reverts to VWAP in ranging markets.

Logic:
  - Price far below VWAP + RSI oversold → LONG
  - Price far above VWAP + RSI overbought → SHORT
  - Only active in RANGING regime (trends break VWAP)

Reference: crypto_fund/strategies/vwap_reversion.py
"""

import logging
import pandas as pd

import config
from engine.signal import Signal
from strategies.base import BaseStrategy
from strategies.indicators import calc_vwap, calc_rsi

logger = logging.getLogger(__name__)


class VWAPReversionStrategy(BaseStrategy):
    name = "VWAP"

    def __init__(self):
        self.deviation = config.VWAP_DEVIATION
        self.rsi_low = 35
        self.rsi_high = 65

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        if df is None or len(df) < 30:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="Insufficient data", strategy=self.name)

        price = df["close"].iloc[-1]

        # VWAP reversion only in ranging markets
        if regime != "RANGING":
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason=f"Trending ({regime})", strategy=self.name, price=price)

        vwap = calc_vwap(df)
        rsi = calc_rsi(df["close"]).iloc[-1]
        curr_vwap = vwap.iloc[-1]

        if pd.isna(rsi) or curr_vwap <= 0:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="Calc failed", strategy=self.name, price=price)

        dev = (price - curr_vwap) / curr_vwap

        action = "NONE"
        confidence = 0.0
        reason = f"VWAP dev={dev*100:.2f}% RSI={rsi:.1f}"

        # Below VWAP + oversold → LONG
        if dev < -self.deviation and rsi < self.rsi_low:
            severity = abs(dev) / self.deviation
            confidence = min(0.85, 0.55 + severity * 0.10)
            action = "LONG"
            reason = f"Below VWAP {dev*100:.2f}%, RSI={rsi:.1f}"

        # Above VWAP + overbought → SHORT
        elif dev > self.deviation and rsi > self.rsi_high:
            severity = dev / self.deviation
            confidence = min(0.85, 0.55 + severity * 0.10)
            action = "SHORT"
            reason = f"Above VWAP {dev*100:.2f}%, RSI={rsi:.1f}"

        # SHORT block (config.ALLOW_SHORT)
        if action == "SHORT" and not config.ALLOW_SHORT:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="SHORT disabled", strategy=self.name, price=price)

        if action != "NONE":
            logger.info(f"[VWAP] {symbol}: {action} conf={confidence:.2f} - {reason}")

        return Signal(symbol=symbol, action=action, confidence=confidence,
                      reason=reason, strategy=self.name, price=price)