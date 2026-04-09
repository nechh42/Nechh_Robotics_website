"""
rsi_reversion.py - RSI Mean Reversion Strategy (v2.0 - TREND FILTERED)
======================================================================
Candle-based RSI + Trend filter from 4h.

Logic:
  - LONG ONLY: RSI < 30 (oversold) in TREND_UP regime
  - Confidence scales with RSI extremity
  - 1h timeframe for mean reversion entry precision

Reference: crypto_fund/strategies/mean_reversion.py (enhanced)
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

    def __init__(self, candles_1h_manager=None):
        self.period = config.RSI_PERIOD
        self.oversold = config.RSI_OVERSOLD
        self.overbought = config.RSI_OVERBOUGHT
        self.candles_1h_manager = candles_1h_manager  # 1h candle manager injected

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        """
        Evaluate RSI on 1h timeframe, only when 4h is TREND_UP.
        
        Args:
            df: 4h DataFrame (for trend/regime detection)
            symbol: Trading symbol
            regime: From 4h analysis (TREND_UP, TREND_DOWN, RANGING)
        
        Returns:
            Signal with LONG only in TREND_UP when RSI<30
        """
        # RULE: LONG sadece TREND_UP'ta
        if regime != "TREND_UP":
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason=f"Regime {regime} - LONG only in TREND_UP", 
                          strategy=self.name)

        # Get 1h data if available
        df_1h = None
        if self.candles_1h_manager and hasattr(self.candles_1h_manager, 'get_dataframe'):
            df_1h = self.candles_1h_manager.get_dataframe(symbol, 50)

        if df_1h is None or len(df_1h) < self.period + 5:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="Insufficient 1h data", strategy=self.name)

        rsi_series = calc_rsi(df_1h["close"], self.period)
        rsi = rsi_series.iloc[-1]
        price = df_1h["close"].iloc[-1]

        if pd.isna(rsi):
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="RSI NaN", strategy=self.name, price=price)

        # MACD confirmation
        macd_line, signal_line, histogram = calc_macd(df_1h["close"])
        macd_bull = macd_line.iloc[-1] > signal_line.iloc[-1]

        action = "NONE"
        confidence = 0.0
        reason = f"RSI={rsi:.1f}"

        # LONG ONLY: oversold (RSI < 30)
        if rsi < self.oversold:
            # Depth-based confidence: 0.55 at threshold, up to 0.85 at extreme
            depth = (self.oversold - rsi) / self.oversold
            base_conf = min(0.85, 0.55 + 0.30 * depth)
            
            if macd_bull:
                confidence = base_conf
                reason = f"1h RSI oversold {rsi:.1f} + MACD bull (TREND_UP)"
            else:
                confidence = base_conf * 0.8  # Soft penalty if no MACD
                reason = f"1h RSI oversold {rsi:.1f} (TREND_UP, no MACD)"
            
            action = "LONG"

        # SHORT block (config.ALLOW_SHORT)
        if action == "SHORT" and not config.ALLOW_SHORT:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="SHORT disabled", strategy=self.name, price=price)

        if action != "NONE":
            logger.info(f"[RSI] {symbol}: {action} conf={confidence:.2f} - {reason}")

        return Signal(symbol=symbol, action=action, confidence=confidence,
                      reason=reason, strategy=self.name, price=price)