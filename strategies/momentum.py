"""
momentum.py - Momentum Breakout Strategy (v8.3 - Donchian + BB hybrid)
========================================================================
Donchian channel breakout (primary) + Bollinger Band expansion (secondary).

Logic:
  - PRIMARY: Donchian breakout (price > 20-candle high or < 20-candle low)
  - SECONDARY: BB expansion confirms breakout strength
  - Volume > 1.2x average confirms real breakout
  - EMA trend alignment for direction
  - Higher confidence in trending regimes
"""

import logging
import pandas as pd

import config
from engine.signal import Signal
from strategies.base import BaseStrategy
from strategies.indicators import calc_bollinger, calc_ema

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    name = "MOMENTUM"

    def __init__(self):
        self.bb_period = config.BB_PERIOD
        self.bb_std = config.BB_STD
        self.donchian_period = 20  # Donchian channel lookback

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        if df is None or len(df) < max(self.bb_period, self.donchian_period) + 10:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="Insufficient data", strategy=self.name)

        price = df["close"].iloc[-1]

        # ─── DONCHIAN CHANNEL (Primary signal) ─────────────
        # Regime'e göre periyot: trend'de kısa (daha sık sinyal), ranging'de uzun
        if regime in ("TREND_UP", "TREND_DOWN"):
            period = 10   # Trend'de 10 mum — daha sık breakout
        else:
            period = self.donchian_period  # RANGING/VOLATILE: 20 mum, daha seçici

        donchian_high = df["high"].iloc[-period-1:-1].max()
        donchian_low = df["low"].iloc[-period-1:-1].min()
        breakout_up = price > donchian_high
        breakout_down = price < donchian_low

        if not breakout_up and not breakout_down:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="No Donchian breakout", strategy=self.name, price=price)

        # ─── BB EXPANSION (Secondary confirmation) ─────────
        upper, middle, lower, bandwidth = calc_bollinger(
            df["close"], self.bb_period, self.bb_std
        )
        bb_expanding = False
        curr_bw = bandwidth.iloc[-1]
        prev_bw = bandwidth.iloc[-5:-1].mean()
        if not pd.isna(curr_bw) and not pd.isna(prev_bw) and prev_bw > 0:
            bb_expanding = curr_bw > prev_bw * 1.02  # 2% expansion (loose)

        # ─── VOLUME CONFIRMATION ───────────────────────────
        vol_confirmed = False
        if "volume" in df.columns and df["volume"].sum() > 0:
            vol_avg = df["volume"].iloc[-21:-1].mean()
            vol_curr = df["volume"].iloc[-1]
            if vol_avg > 0:
                vol_confirmed = (vol_curr / vol_avg) > 1.2

        # ─── EMA TREND ────────────────────────────────────
        ema9 = calc_ema(df["close"], 9).iloc[-1]
        ema21 = calc_ema(df["close"], 21).iloc[-1]
        ema_bullish = ema9 > ema21
        ema_bearish = ema9 < ema21

        action = "NONE"
        confidence = 0.0
        reason = ""

        # ─── LONG BREAKOUT ────────────────────────────────
        if breakout_up:
            # Score based on confirmations
            score = 0.40  # Base: Donchian breakout alone
            parts = ["Donchian up"]
            if ema_bullish:
                score += 0.15
                parts.append("EMA9>21")
            if vol_confirmed:
                score += 0.15
                parts.append("vol")
            if bb_expanding:
                score += 0.10
                parts.append("BB exp")
            if regime == "TREND_UP":
                score += 0.05
            confidence = min(0.90, score)
            reason = " + ".join(parts)
            action = "LONG"

        # ─── SHORT BREAKOUT ───────────────────────────────
        elif breakout_down:
            score = 0.40  # Base: Donchian breakout alone
            parts = ["Donchian down"]
            if ema_bearish:
                score += 0.15
                parts.append("EMA9<21")
            if vol_confirmed:
                score += 0.15
                parts.append("vol")
            if bb_expanding:
                score += 0.10
                parts.append("BB exp")
            if regime == "TREND_DOWN":
                score += 0.05
            confidence = min(0.90, score)
            reason = " + ".join(parts)
            action = "SHORT"

        if action != "NONE":
            logger.info(f"[MOMENTUM] {symbol}: {action} conf={confidence:.2f} - {reason}")

        return Signal(symbol=symbol, action=action, confidence=confidence,
                      reason=reason, strategy=self.name, price=price)