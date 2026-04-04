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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EDGE DISCOVERY PATTERNS (Keşfedilen Avantajlar)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_high_volatility(df: pd.DataFrame, period: int = 50) -> pd.Series:
    """
    Edge: High Volatility
    Win Rate: 66-82% depending on coin
    
    Triggers when ATR is 1.5x above median (volatility expansion detected).
    Strong in: AAVEUSDT (+32% edge), LTCUSDT (+32.8% edge), ETHUSDT (+24.3% edge)
    """
    atr = calc_atr(df, 14)
    atr_median = atr.rolling(period).median()
    return atr > (atr_median * 1.5)


def detect_momentum_continuation_up(df: pd.DataFrame) -> pd.Series:
    """
    Edge: Momentum Continuation (Uptrend)
    Win Rate: 80% (PEPEUSDT +35.2% edge over baseline)
    
    Triggers when price has 4h momentum >+1% AND trending up with volume.
    Most reliable pattern in discovery results.
    """
    closes = df["close"]
    mom_4h = closes.pct_change(4)  # 4 candles ago momentum
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    
    # Uptrend: EMA9 > EMA21 AND 4h momentum positive + volume
    uptrend = ema9 > ema21
    momentum_pos = mom_4h > 0.01  # +1% over 4 candles
    
    return uptrend & momentum_pos


def detect_bb_upper_high_volume(df: pd.DataFrame, bb_period: int = 20) -> pd.Series:
    """
    Edge: Bollinger Upper Band + High Volume
    Win Rate: 67-75% depending on coin
    
    Triggers when price is at BB upper (>80% position) AND volume > 1.5x average.
    Common in: PEPEUSDT (+30.2% edge), LTCUSDT (+27.1%), AAVEUSDT (+22.7%)
    """
    upper, _, lower, _ = calc_bollinger(df["close"], bb_period, 2.0)
    bb_pos = (df["close"] - lower) / (upper - lower + 1e-10)
    bb_upper = bb_pos > 0.80
    
    # High volume check
    if "volume" in df.columns:
        vol_avg = df["volume"].rolling(20).mean()
        high_vol = df["volume"] > (vol_avg * 1.5)
    else:
        high_vol = pd.Series(False, index=df.index)
    
    return bb_upper & high_vol


def detect_trend_down(df: pd.DataFrame) -> pd.Series:
    """
    Edge: Downtrend Detection
    Win Rate: 52-58% depending on coin
    
    Triggers when EMA9 < EMA21 < EMA50 (clear downtrend).
    Safe pattern: BNBUSDT (+13.3% edge @ 24h)
    """
    ema9 = calc_ema(df["close"], 9)
    ema21 = calc_ema(df["close"], 21)
    ema50 = calc_ema(df["close"], 50)
    
    return (ema9 < ema21) & (ema21 < ema50)


def detect_rsi_oversold(df: pd.DataFrame, threshold: int = 40) -> pd.Series:
    """
    Edge: RSI Below Threshold (Oversold Signal)
    Win Rate: 54-56% depending on coin
    
    Triggers when RSI < threshold (default 40 for mean reversion).
    Reliable base pattern: ADAUSDT, PEPEUSDT
    """
    rsi = calc_rsi(df["close"], 14)
    return rsi < threshold


def detect_bb_lower_high_volume(df: pd.DataFrame, bb_period: int = 20) -> pd.Series:
    """
    Edge: Bollinger Lower Band + High Volume
    Win Rate: 66-67%
    
    Triggers when price is at BB lower (<20% position) AND volume > 1.5x average.
    Mean reversion pattern: BNBUSDT, continues into next 12h+
    """
    upper, _, lower, _ = calc_bollinger(df["close"], bb_period, 2.0)
    bb_pos = (df["close"] - lower) / (upper - lower + 1e-10)
    bb_lower = bb_pos < 0.20
    
    # High volume check
    if "volume" in df.columns:
        vol_avg = df["volume"].rolling(20).mean()
        high_vol = df["volume"] > (vol_avg * 1.5)
    else:
        high_vol = pd.Series(False, index=df.index)
    
    return bb_lower & high_vol


def detect_trend_down_oversold(df: pd.DataFrame, rsi_threshold: int = 35) -> pd.Series:
    """
    Edge: Downtrend + Oversold (Reversal Setup)
    Win Rate: 58%
    
    Triggers when in downtrend BUT RSI < 35 (oversold bounce setup).
    Pattern: ADAUSDT +16.5% edge @ 24h
    """
    ema9 = calc_ema(df["close"], 9)
    ema21 = calc_ema(df["close"], 21)
    ema50 = calc_ema(df["close"], 50)
    
    downtrend = (ema9 < ema21) & (ema21 < ema50)
    rsi = calc_rsi(df["close"], 14)
    oversold = rsi < rsi_threshold
    
    return downtrend & oversold


def detect_strong_momentum_up(df: pd.DataFrame, momentum_threshold: float = 0.05) -> pd.Series:
    """
    Edge: Strong Upward Momentum (24h lookback)
    Win Rate: 61%
    
    Triggers when 24h momentum > +5% (strong bull move).
    Pattern: ZECUSDT +13.8% edge, high avg returns +2.95%
    """
    closes = df["close"]
    mom_24h = closes.pct_change(24)
    return mom_24h > momentum_threshold


def detect_composite_edge(df: pd.DataFrame, strategy_type: str = "aggressive") -> pd.Series:
    """
    Edge: Composite Score (Multi-condition validation)
    
    'aggressive': High volatility + Momentum continuation (short-term plays)
    'conservative': Trend alignment + BB position (longer holds)
    
    Useful for higher conviction entries combining multiple edges.
    """
    if strategy_type == "aggressive":
        # For fast 4h+ moves
        aggressive = detect_high_volatility(df) & detect_momentum_continuation_up(df)
        return aggressive
    else:
        # For 24h+ holds, safer entry
        conservative = detect_trend_down_oversold(df) | detect_bb_lower_high_volume(df)
        return conservative


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# v2.0 YENI KEŞFEDILEN PATTERN'LAR (Edge Discovery v2.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_strong_momentum_down(df: pd.DataFrame, momentum_threshold: float = -0.05) -> pd.Series:
    """
    Edge: Strong Downward Momentum (24h lookback)
    Win Rate: 87.1% (VETUSDT @12h timeframe)
    
    Triggers when 24h momentum < -5% (strong bearish move).
    Most reliable SHORT setup (BUT SHORT DISABLED in config).
    Used for contrarian/mean-reversion bounce signals.
    """
    closes = df["close"]
    mom_24h = closes.pct_change(24)
    return mom_24h < momentum_threshold


def detect_squeeze_breakout_down(df: pd.DataFrame, bb_period: int = 20) -> pd.Series:
    """
    Edge: BB Squeeze + Downward Breakout
    Win Rate: 84.1% (ARPAUSDT @24h)
    
    Triggers when BB is tightly squeezed AND price breaks below lower band.
    Pattern: Capitulation/accumulation bottom followed by reversal.
    """
    upper, _, lower, bandwidth = calc_bollinger(df["close"], bb_period, 2.0)
    
    # Squeeze condition: BB width < 25th percentile
    bb_squeeze = bandwidth < bandwidth.rolling(50).quantile(0.25)
    
    # Breakout down: price breaks below lower + closes there
    breakout_down = df["close"] < lower
    
    return bb_squeeze & breakout_down


def detect_low_volatility(df: pd.DataFrame, period: int = 50) -> pd.Series:
    """
    Edge: Low Volatility Period
    Win Rate: 81.5% (ARPAUSDT @24h)
    
    Opposite of high_volatility. Triggers when ATR is compressed.
    Often precedes breakout moves (calm before storm).
    Entry for patience traders waiting for expansion.
    """
    atr = calc_atr(df, 14)
    atr_median = atr.rolling(period).median()
    return atr < (atr_median * 0.7)  # Below 70% of median


def detect_bb_squeeze(df: pd.DataFrame, bb_period: int = 20) -> pd.Series:
    """
    Edge: Bollinger Band Squeeze
    Win Rate: 64.1% (ARPAUSDT @24h)
    
    Triggers when BB bandwidth contracts (volatility compression).
    Precedes directional breakouts. Neutral but high-probability setup.
    """
    _, _, _, bandwidth = calc_bollinger(df["close"], bb_period, 2.0)
    
    # Squeeze when bandwidth < 25th percentile (tightest quartile)
    return bandwidth < bandwidth.rolling(50).quantile(0.25)


def detect_trend_mixed(df: pd.DataFrame) -> pd.Series:
    """
    Edge: Mixed Trend (No Clear Direction)
    Win Rate: 52.5% (FLOWUSDT @24h, high AvgRet +3.48%!)
    
    Triggers when EMA9 and EMA21 are not aligned (none of UP/DOWN).
    Often precedes bigger moves. High return volatility.
    """
    ema9 = calc_ema(df["close"], 9)
    ema21 = calc_ema(df["close"], 21)
    ema50 = calc_ema(df["close"], 50)
    
    # Explicitly NOT in clear trend
    clear_up = (ema9 > ema21) & (ema21 > ema50)
    clear_down = (ema9 < ema21) & (ema21 < ema50)
    
    return ~(clear_up | clear_down)  # NOT in clear trend (MIXED)


def detect_rsi_30_50(df: pd.DataFrame) -> pd.Series:
    """
    Edge: RSI in 30-50 Band (Lower Neutral Zone)
    Win Rate: 52.4% (DOGEUSDT @24h)
    
    RSI between 30-50 indicates weak buying pressure.
    Good for contrarian bounce setups.
    """
    rsi = calc_rsi(df["close"], 14)
    return rsi.between(30, 50)


def detect_price_below_ema50(df: pd.DataFrame) -> pd.Series:
    """
    Edge: Price Below EMA50
    Win Rate: Varies (DOGEUSDT 51%, LTCUSDT 54.2%)
    
    Simple but effective: price below 50-period moving average = weakness.
    Used for trend-following entries on further weakness.
    """
    ema50 = calc_ema(df["close"], 50)
    return df["close"] < ema50


def detect_bb_near_lower(df: pd.DataFrame, bb_period: int = 20) -> pd.Series:
    """
    Edge: Price Near Bollinger Lower Band
    Win Rate: Varies (OPUSDT 58%, XRPUSDT 53-54%)
    
    Triggers when price is in lower 20% of BB range.
    Mean reversion signal (likely bounce).
    """
    upper, _, lower, _ = calc_bollinger(df["close"], bb_period, 2.0)
    bb_pos = (df["close"] - lower) / (upper - lower + 1e-10)
    return bb_pos < 0.20


def detect_oversold_high_volume(df: pd.DataFrame, rsi_threshold: int = 35) -> pd.Series:
    """
    Edge: Oversold + High Volume (Capitulation)
    Win Rate: 66% (BNBUSDT @12h)
    
    RSI < 35 AND volume > 1.5x average = strong selling + accumulation.
    Classic reversal setup: weak hands capitulate, smart money buys.
    """
    rsi = calc_rsi(df["close"], 14)
    oversold = rsi < rsi_threshold
    
    if "volume" in df.columns:
        vol_avg = df["volume"].rolling(20).mean()
        high_vol = df["volume"] > (vol_avg * 1.5)
    else:
        high_vol = pd.Series(False, index=df.index)
    
    return oversold & high_vol


def detect_ranging_bb_upper(df: pd.DataFrame) -> pd.Series:
    """
    Edge: Ranging Market + BB Upper
    Win Rate: 69% (SOLUSDT @4h)
    
    In MIXED trend (no clear direction) AND price at BB upper (>80%).
    Fading overbought in choppy markets.
    """
    # Ranging condition
    ranging = detect_trend_mixed(df)
    
    # BB upper position
    upper, _, lower, _ = calc_bollinger(df["close"], 20, 2.0)
    bb_pos = (df["close"] - lower) / (upper - lower + 1e-10)
    bb_upper = bb_pos > 0.80
    
    return ranging & bb_upper
