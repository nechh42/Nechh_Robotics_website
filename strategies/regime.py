"""
regime.py - Market Regime Detection
======================================
Determines: TREND_UP, TREND_DOWN, RANGING, or VOLATILE.
Uses ADX for trend strength + volatility ratio for chaos detection.
Based on: crypto_fund/src/analytics/market_regime.py (improved)
"""

import logging
import pandas as pd
import numpy as np
import config
from strategies.indicators import calc_ema, calc_atr

logger = logging.getLogger(__name__)

def _calc_adx_approx(df: pd.DataFrame, period: int = 14) -> float:
    """Simplified ADX - measures trend strength (0-100)"""
    if len(df) < period * 2:
        return 0.0
    price_range = df["high"].max() - df["low"].min()
    if price_range == 0:
        return 0.0
    trend_move = abs(df["close"].iloc[-1] - df["close"].iloc[-period])
    return min(float(trend_move / price_range) * 100, 100.0)

def _calc_volatility_ratio(df: pd.DataFrame) -> float:
    """Current volatility vs average (>1.5 = high vol)"""
    if len(df) < 20:
        return 1.0
    returns = df["close"].pct_change().dropna()
    if len(returns) < 10:
        return 1.0
    current_vol = returns.tail(5).std()
    avg_vol = returns.std()
    if avg_vol == 0:
        return 1.0
    return float(current_vol / avg_vol)

def detect_regime(df: pd.DataFrame) -> str:
    """
    Detect market regime using multiple indicators.

    Logic (priority order):
      1. VOLATILE: volatility ratio > 1.5 AND ATR > 2% of price
      2. TREND_UP: ADX > 25 AND positive price change
      3. TREND_DOWN: ADX > 25 AND negative price change
      4. RANGING: everything else

    Returns: 'TREND_UP', 'TREND_DOWN', 'RANGING', or 'VOLATILE'
    """
    # TEST: Force regime if configured
    if config.TEST_MODE_FORCE_REGIME:
        logger.warning(f"[TEST] FORCING REGIME: {config.TEST_MODE_FORCE_REGIME}")
        return config.TEST_MODE_FORCE_REGIME
    
    if df is None or len(df) < 50:
        return "RANGING"

    closes = df["close"]
    price = closes.iloc[-1]

    # Calculate indicators
    adx = _calc_adx_approx(df)
    vol_ratio = _calc_volatility_ratio(df)
    atr = calc_atr(df).iloc[-1] if len(df) > 14 else 0.0
    price_change_20 = ((price - closes.iloc[-20]) / closes.iloc[-20] * 100) if len(closes) >= 20 else 0.0

    # DEBUG: Log all calculations
    logger.info(f"[REGIME-DEBUG] ADX={adx:.1f}, vol_ratio={vol_ratio:.2f}, atr_pct={atr/price*100:.2f}%, price_chg_20={price_change_20:.2f}%")

    # 1. High volatility check first (chaos mode)
    if vol_ratio > 1.5 and atr > price * 0.02:
        logger.info(f"Regime: VOLATILE (vol_ratio={vol_ratio:.2f}, atr_pct={atr/price*100:.2f}%)")
        return "VOLATILE"

    # 2. Strong trend check (ADX > 25)
    if adx > 25:
        if price_change_20 > 2:
            logger.info(f"Regime: TREND_UP (ADX={adx:.1f}, chg={price_change_20:.2f}%)")
            return "TREND_UP"
        elif price_change_20 < -2:
            logger.info(f"Regime: TREND_DOWN (ADX={adx:.1f}, chg={price_change_20:.2f}%)")
            return "TREND_DOWN"
        else:
            logger.info(f"Regime: ADX>{25} but weak price chg ({price_change_20:.2f}%) → RANGING")

    # 3. Weak trend / EMA alignment
    ema20 = calc_ema(closes, 20).iloc[-1]
    ema50 = calc_ema(closes, 50).iloc[-1]

    if pd.isna(ema20) or pd.isna(ema50):
        return "RANGING"

    if price > ema20 > ema50 and price_change_20 > 0:
        logger.info(f"Regime: TREND_UP (EMA: {price:.0f}>{ema20:.0f}>{ema50:.0f})")
        return "TREND_UP"
    elif price < ema20 < ema50 and price_change_20 < 0:
        logger.info(f"Regime: TREND_DOWN (EMA: {price:.0f}<{ema20:.0f}<{ema50:.0f})")
        return "TREND_DOWN"

    logger.info(f"Regime: RANGING (default)")
    return "RANGING"
