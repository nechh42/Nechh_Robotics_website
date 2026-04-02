"""
indicators.py - Technical Indicator Calculations
===================================================
Shared by all strategies. Candle-based, not tick-based.
"""

import numpy as np
import pandas as pd


def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI using exponential moving average (Wilder's method)"""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return series.rolling(period).mean()


def calc_bollinger(closes: pd.Series, period: int = 20, std_mult: float = 2.0):
    """Bollinger Bands -> (upper, middle, lower, bandwidth)"""
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    bandwidth = (upper - lower) / (middle + 1e-10)
    return upper, middle, lower, bandwidth


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range from OHLC DataFrame"""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price"""
    if "volume" not in df.columns or df["volume"].sum() == 0:
        return df["close"]
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    return cum_tp_vol / (cum_vol + 1e-10)


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD -> (macd_line, signal_line, histogram)"""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
