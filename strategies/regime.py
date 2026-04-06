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

def _calc_wilder_adx(df: pd.DataFrame, period: int = 14) -> tuple:
    """
    Gerçek Wilder's ADX hesaplaması + DI+/DI- yön göstergeleri.

    Returns: (adx, plus_di, minus_di)
      - adx > 25: güçlü trend
      - adx < 20: trend yok (ranging)
      - plus_di > minus_di: yükseliş yönü
      - minus_di > plus_di: düşüş yönü
    """
    if len(df) < period * 3:
        return 0.0, 50.0, 50.0

    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)

    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)

    up_mask = (up_move > down_move) & (up_move > 0)
    down_mask = (down_move > up_move) & (down_move > 0)
    plus_dm[up_mask] = up_move[up_mask]
    minus_dm[down_mask] = down_move[down_mask]

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder Smoothing (alpha = 1/period)
    alpha = 1.0 / period
    atr_smooth = tr.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    smooth_plus = plus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    smooth_minus = minus_dm.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    # Directional Indicators
    plus_di = 100.0 * smooth_plus / atr_smooth.replace(0, np.nan)
    minus_di = 100.0 * smooth_minus / atr_smooth.replace(0, np.nan)

    # DX ve ADX
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
    adx = dx.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
    pdi_val = float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 50.0
    mdi_val = float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 50.0

    return adx_val, pdi_val, mdi_val

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
    # TEST: Force regime if configured (only when TEST_MODE is True)
    if config.TEST_MODE and config.TEST_MODE_FORCE_REGIME:
        logger.warning(f"[TEST] FORCING REGIME: {config.TEST_MODE_FORCE_REGIME}")
        return config.TEST_MODE_FORCE_REGIME
    
    if df is None or len(df) < 50:
        return "RANGING"

    # NOT: Sentiment artık regime'ı DEĞİŞTİRMEZ.
    # Sentiment = pozisyon boyutu çarpanı olarak pre_trade.py'de uygulanır.

    closes = df["close"]
    price = closes.iloc[-1]

    # Gerçek Wilder ADX + DI hesapla
    adx, plus_di, minus_di = _calc_wilder_adx(df)
    vol_ratio = _calc_volatility_ratio(df)
    atr = calc_atr(df).iloc[-1] if len(df) > 14 else 0.0

    logger.info(f"[REGIME] ADX={adx:.1f}, +DI={plus_di:.1f}, -DI={minus_di:.1f}, vol_r={vol_ratio:.2f}, atr%={atr/price*100:.2f}%")

    # 1. VOLATILE: aşırı teknik volatilite
    if vol_ratio > 1.5 and atr > price * 0.02:
        logger.info(f"Regime: VOLATILE (vol_ratio={vol_ratio:.2f}, atr%={atr/price*100:.2f}%)")
        return "VOLATILE"

    # 2. Güçlü trend (ADX > 25) — DI yönü belirler
    if adx > 25:
        if plus_di > minus_di:
            logger.info(f"Regime: TREND_UP (ADX={adx:.1f}, +DI={plus_di:.1f} > -DI={minus_di:.1f})")
            return "TREND_UP"
        else:
            logger.info(f"Regime: TREND_DOWN (ADX={adx:.1f}, -DI={minus_di:.1f} > +DI={plus_di:.1f})")
            return "TREND_DOWN"

    # 3. Orta trend (ADX 20-25) — EMA doğrulaması gerekir
    if adx > 20:
        ema20 = calc_ema(closes, 20).iloc[-1]
        ema50 = calc_ema(closes, 50).iloc[-1]
        if not pd.isna(ema20) and not pd.isna(ema50):
            if price > ema20 > ema50 and plus_di > minus_di:
                logger.info(f"Regime: TREND_UP (ADX={adx:.1f}+EMA, +DI={plus_di:.1f})")
                return "TREND_UP"
            elif price < ema20 < ema50 and minus_di > plus_di:
                logger.info(f"Regime: TREND_DOWN (ADX={adx:.1f}+EMA, -DI={minus_di:.1f})")
                return "TREND_DOWN"

    # 4. Trend yok
    logger.info(f"Regime: RANGING (ADX={adx:.1f})")
    return "RANGING"
