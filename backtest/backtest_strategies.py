"""
backtest_strategies.py — Tüm Stratejileri Tek Tek Test Et
============================================================
Her stratejiyi aynı 60 gün veride ayrı ayrı çalıştırır.
Ayrıca eski v15.5 konfigürasyonunu da test eder.

Kullanım:
    python -m backtest.backtest_strategies
    python -m backtest.backtest_strategies --days 90
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List, Optional, Callable

import pandas as pd
import numpy as np
import requests

import config
from strategies.indicators import (
    calc_ema, calc_rsi, calc_atr, calc_macd,
    calc_bollinger, calc_vwap,
)
from strategies.regime import detect_regime

logging.basicConfig(level=logging.WARNING, format="%(message)s")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Veri İndirme (cache'li)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CANDLE_CACHE = {}

def fetch_candles(symbol: str, interval: str, days: int) -> pd.DataFrame:
    key = f"{symbol}_{interval}_{days}"
    if key in _CANDLE_CACHE:
        return _CANDLE_CACHE[key].copy()

    url = "https://api.binance.com/api/v3/klines"
    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=days + 10)).timestamp() * 1000)

    all_candles = []
    while start_ms < end_ms:
        params = {"symbol": symbol, "interval": interval,
                  "startTime": start_ms, "limit": 1000}
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_candles.extend(data)
        start_ms = data[-1][0] + 1

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df[["time", "open", "high", "low", "close", "volume"]].copy().reset_index(drop=True)

    _CANDLE_CACHE[key] = df.copy()
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Trade Kaydı
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class Trade:
    symbol: str
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    take_profit_1: float  # partial TP
    size: float
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    pnl: float = 0.0
    hold_candles: int = 0
    entry_regime: str = ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRATEJİLER — her biri (df, symbol, regime) → Signal dict veya None
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def strategy_scalp_v0(df, symbol, regime):
    """EMA Cross + RSI band + Volume (mevcut ScalpV0)"""
    if len(df) < 30:
        return None
    close = df["close"]
    volume = df["volume"]
    price = close.iloc[-1]

    ema9 = calc_ema(close, 9).iloc[-1]
    ema21 = calc_ema(close, 21).iloc[-1]
    rsi = calc_rsi(close, 14).iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    vol_now = volume.iloc[-1]
    vol_avg = volume.rolling(20).mean().iloc[-1]

    if pd.isna(ema9) or pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        return None
    if ema9 <= ema21:
        return None
    if rsi < 35 or rsi > 65:
        return None
    if vol_avg > 0 and vol_now < vol_avg:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strategy_momentum(df, symbol, regime):
    """Donchian Channel Breakout + Volume + EMA alignment"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        return None

    period = 10 if regime in ("TREND_UP", "TREND_DOWN") else 20
    if len(df) < period + 2:
        return None

    donchian_high = df["high"].iloc[-period-1:-1].max()
    if price <= donchian_high:
        return None

    # EMA alignment
    ema9 = calc_ema(close, 9).iloc[-1]
    ema21 = calc_ema(close, 21).iloc[-1]
    if pd.isna(ema9) or pd.isna(ema21):
        return None
    if ema9 <= ema21:
        return None

    # Volume check
    vol_now = df["volume"].iloc[-1]
    vol_avg = df["volume"].iloc[-21:-1].mean()
    if vol_avg > 0 and vol_now < vol_avg * 1.2:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strategy_vwap_reversion(df, symbol, regime):
    """VWAP Mean Reversion — fiyat VWAP altında + RSI düşük → LONG"""
    if len(df) < 30:
        return None
    if regime != "RANGING":
        return None

    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    vwap = calc_vwap(df).iloc[-1]
    rsi = calc_rsi(close, 14).iloc[-1]

    if pd.isna(rsi) or pd.isna(atr) or atr <= 0 or vwap <= 0:
        return None

    dev = (price - vwap) / vwap
    if dev >= -0.01:  # VWAP'ın %1+ altında olmalı
        return None
    if rsi >= 35:  # RSI düşük olmalı
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strategy_rsi_oversold(df, symbol, regime):
    """RSI < 30 Oversold Bounce — rejim bağımsız"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    rsi = calc_rsi(close, 14).iloc[-1]

    if pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        return None
    if rsi >= 30:
        return None

    # MACD teyidi (opsiyonel bonus)
    macd, signal, _ = calc_macd(close)
    macd_bull = not pd.isna(macd.iloc[-1]) and macd.iloc[-1] > signal.iloc[-1]
    conf = 0.70 if macd_bull else 0.60

    return {"action": "LONG", "price": price, "atr": atr, "conf": conf}


def strategy_bollinger_bounce(df, symbol, regime):
    """Fiyat alt Bollinger Band'a dokundu + RSI < 40 → LONG"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]

    upper, middle, lower, bw = calc_bollinger(close, 20, 2.0)
    rsi = calc_rsi(close, 14).iloc[-1]

    if pd.isna(rsi) or pd.isna(atr) or atr <= 0:
        return None
    if pd.isna(lower.iloc[-1]):
        return None
    if price > lower.iloc[-1]:
        return None
    if rsi >= 40:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strategy_mean_reversion(df, symbol, regime):
    """Son 3 mumda %3+ düşüş + RSI < 35 → dip alım"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        return None

    # Son 3 mumda düşüş
    price_3ago = close.iloc[-4] if len(close) >= 4 else close.iloc[0]
    drop_pct = (price - price_3ago) / price_3ago
    if drop_pct >= -0.03:  # %3'ten fazla düşüş olmalı
        return None

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 35:
        return None

    # Hacim kontrolü — panik satışta hacim yüksek olmalı
    vol_now = df["volume"].iloc[-1]
    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    if vol_avg > 0 and vol_now < vol_avg:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.70}


def strategy_ema_pullback(df, symbol, regime):
    """EMA21'e pullback: Trend devam — fiyat EMA21'e düştü ve geri döndü"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        return None

    ema9 = calc_ema(close, 9)
    ema21 = calc_ema(close, 21)
    ema50 = calc_ema(close, 50)

    e9 = ema9.iloc[-1]
    e21 = ema21.iloc[-1]
    e50 = ema50.iloc[-1]

    if pd.isna(e9) or pd.isna(e21) or pd.isna(e50):
        return None

    # Trend yukarı olmalı
    if not (e9 > e21 > e50):
        return None

    # Fiyat EMA21'e yakın olmalı (pullback)
    dist = (price - e21) / e21
    if dist < -0.005 or dist > 0.01:  # EMA21'e yakın (-%0.5 ile +%1 arası)
        return None

    # Önceki mum daha düşüktü (geri dönüş)
    prev_price = close.iloc[-2]
    if prev_price >= price:  # son mum yukarı kapanmalı
        return None

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi < 40 or rsi > 60:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.70}


def strategy_breakout_volume(df, symbol, regime):
    """Yüksek hacimli breakout: 20-bar high kırılması + 2x hacim"""
    if len(df) < 30:
        return None
    close = df["close"]
    price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]

    if pd.isna(atr) or atr <= 0:
        return None

    high_20 = df["high"].iloc[-21:-1].max()
    if price <= high_20:
        return None

    # Çok güçlü hacim (2x)
    vol_now = df["volume"].iloc[-1]
    vol_avg = df["volume"].iloc[-21:-1].mean()
    if vol_avg <= 0 or vol_now < vol_avg * 2.0:
        return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.75}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Backtest Motoru
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_backtest(
    symbol: str,
    df: pd.DataFrame,
    strategy_fn: Callable,
    sl_mult: float = 1.0,
    tp_mult: float = 1.0,
    max_hold: int = 1,
    partial_tp_enabled: bool = False,
    partial_tp_pct: float = 0.70,
    partial_tp_ratio: float = 0.50,
    smart_exit: bool = False,
    breakeven_atr: float = 0.0,
    regime_filter: bool = False,
) -> List[Trade]:
    """Tek coin / tek strateji backtest."""
    trades: List[Trade] = []
    open_trade: Optional[Trade] = None
    hold_count = 0
    partial_done = False
    remaining_size = 0.0
    entry_regime = ""
    lookback = 100

    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i + 1].copy().reset_index(drop=True)
        current = df.iloc[i]
        price = current["close"]
        high = current["high"]
        low = current["low"]

        # Açık pozisyon
        if open_trade is not None:
            hold_count += 1

            # Breakeven: fiyat +breakeven_atr×ATR geçtiyse SL → entry
            if breakeven_atr > 0 and open_trade.stop_loss < open_trade.entry_price:
                be_dist = open_trade.take_profit - open_trade.entry_price  # approximate ATR
                if be_dist > 0:
                    be_trigger = open_trade.entry_price + be_dist * breakeven_atr / tp_mult
                    if high >= be_trigger:
                        open_trade.stop_loss = max(open_trade.stop_loss, open_trade.entry_price)

            # Partial TP
            if partial_tp_enabled and not partial_done and open_trade.take_profit_1 > 0:
                if high >= open_trade.take_profit_1:
                    # Partial close
                    close_size = remaining_size * partial_tp_pct
                    partial_pnl = (open_trade.take_profit_1 - open_trade.entry_price) * close_size
                    partial_pnl -= open_trade.take_profit_1 * close_size * 0.001  # commission
                    open_trade.pnl += partial_pnl
                    remaining_size -= close_size
                    partial_done = True

            # SL
            if low <= open_trade.stop_loss:
                exit_pnl = (open_trade.stop_loss - open_trade.entry_price) * remaining_size
                exit_pnl -= open_trade.stop_loss * remaining_size * 0.001
                open_trade.pnl += exit_pnl
                open_trade.pnl -= open_trade.entry_price * open_trade.size * 0.001  # entry commission
                open_trade.exit_price = open_trade.stop_loss
                open_trade.exit_reason = "STOP-LOSS"
                open_trade.hold_candles = hold_count
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                partial_done = False
                continue

            # TP (full)
            if high >= open_trade.take_profit:
                exit_pnl = (open_trade.take_profit - open_trade.entry_price) * remaining_size
                exit_pnl -= open_trade.take_profit * remaining_size * 0.001
                open_trade.pnl += exit_pnl
                open_trade.pnl -= open_trade.entry_price * open_trade.size * 0.001
                open_trade.exit_price = open_trade.take_profit
                open_trade.exit_reason = "PARTIAL-TP1" if partial_done else "TAKE-PROFIT"
                open_trade.hold_candles = hold_count
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                partial_done = False
                continue

            # Smart Exit (regime changed while in profit)
            if smart_exit:
                curr_regime = detect_regime(window)
                if curr_regime != entry_regime:
                    curr_pnl = (price - open_trade.entry_price) * remaining_size
                    if curr_pnl > 0:
                        exit_pnl = (price - open_trade.entry_price) * remaining_size
                        exit_pnl -= price * remaining_size * 0.001
                        open_trade.pnl += exit_pnl
                        open_trade.pnl -= open_trade.entry_price * open_trade.size * 0.001
                        open_trade.exit_price = price
                        open_trade.exit_reason = "SMART-EXIT"
                        open_trade.hold_candles = hold_count
                        trades.append(open_trade)
                        open_trade = None
                        hold_count = 0
                        partial_done = False
                        continue

            # MAX_HOLD
            if hold_count >= max_hold:
                exit_pnl = (price - open_trade.entry_price) * remaining_size
                exit_pnl -= price * remaining_size * 0.001
                open_trade.pnl += exit_pnl
                open_trade.pnl -= open_trade.entry_price * open_trade.size * 0.001
                open_trade.exit_price = price
                open_trade.exit_reason = "TIME-EXIT"
                open_trade.hold_candles = hold_count
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                partial_done = False
                continue

            continue

        # Yeni sinyal ara
        regime = detect_regime(window)

        # Regime filter (v15 tarzı: TREND_DOWN ve VOLATILE bloke)
        if regime_filter and regime in ("TREND_DOWN", "VOLATILE"):
            continue

        sig = strategy_fn(window, symbol, regime)
        if sig is None or sig["action"] != "LONG":
            continue

        price_entry = sig["price"]
        atr = sig["atr"]

        # Dynamic R:R
        sl_dist = atr * sl_mult
        tp_dist = atr * tp_mult

        min_sl = price_entry * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        sl_price = price_entry - sl_dist
        tp_price = price_entry + tp_dist
        tp1_price = price_entry + tp_dist * partial_tp_ratio if partial_tp_enabled else 0.0

        equity = 10000.0
        risk_amount = equity * 0.005
        size_by_risk = risk_amount / sl_dist
        size_by_notional = (equity * 0.10) / price_entry
        size = min(size_by_risk, size_by_notional)

        open_trade = Trade(
            symbol=symbol,
            entry_price=price_entry,
            entry_time=current["time"],
            stop_loss=sl_price,
            take_profit=tp_price,
            take_profit_1=tp1_price,
            size=size,
            entry_regime=regime,
        )
        remaining_size = size
        entry_regime = regime
        hold_count = 0
        partial_done = False

    # Açık kalan pozisyon
    if open_trade is not None:
        last = df.iloc[-1]
        exit_pnl = (last["close"] - open_trade.entry_price) * remaining_size
        exit_pnl -= last["close"] * remaining_size * 0.001
        open_trade.pnl += exit_pnl
        open_trade.pnl -= open_trade.entry_price * open_trade.size * 0.001
        open_trade.exit_price = last["close"]
        open_trade.exit_reason = "END"
        open_trade.hold_candles = hold_count
        trades.append(open_trade)

    return trades


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sonuç Hesabı
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_stats(trades: List[Trade]) -> dict:
    if not trades:
        return {"count": 0, "wr": 0, "pnl": 0, "pf": 0, "dd": 0, "avg_w": 0, "avg_l": 0}

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]
    total_pnl = sum(t.pnl for t in trades)
    gp = sum(t.pnl for t in winners) if winners else 0
    gl = abs(sum(t.pnl for t in losers)) if losers else 0.001
    pf = gp / gl if gl > 0 else float("inf")
    wr = len(winners) / len(trades) * 100

    cum = peak = dd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_time):
        cum += t.pnl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)

    # Çıkış nedenleri
    exit_stats = {}
    for t in trades:
        r = t.exit_reason
        if r not in exit_stats:
            exit_stats[r] = {"count": 0, "pnl": 0.0}
        exit_stats[r]["count"] += 1
        exit_stats[r]["pnl"] += t.pnl

    return {
        "count": len(trades),
        "wr": wr,
        "pnl": total_pnl,
        "pf": pf,
        "dd": dd,
        "avg_w": gp / len(winners) if winners else 0,
        "avg_l": gl / len(losers) if losers else 0,
        "exits": exit_stats,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Senaryoları
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST_SCENARIOS = [
    {
        "name": "1. ScalpV0 (baseline)",
        "fn": strategy_scalp_v0,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "2. Momentum (Donchian)",
        "fn": strategy_momentum,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "3. VWAP Reversion",
        "fn": strategy_vwap_reversion,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": False,
    },
    {
        "name": "4. RSI Oversold (<30)",
        "fn": strategy_rsi_oversold,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "5. Bollinger Bounce",
        "fn": strategy_bollinger_bounce,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "6. Mean Reversion (dip)",
        "fn": strategy_mean_reversion,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "7. EMA Pullback",
        "fn": strategy_ema_pullback,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    {
        "name": "8. Breakout+Volume (2x)",
        "fn": strategy_breakout_volume,
        "sl": 1.0, "tp": 1.0, "hold": 1,
        "partial": False, "smart": False, "be": 0, "regime_f": True,
    },
    # ─── v15 tarzı parametrelerle ───
    {
        "name": "9. ScalpV0 + PartialTP70%",
        "fn": strategy_scalp_v0,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": False, "be": 0.7, "regime_f": True,
    },
    {
        "name": "10. Momentum + v15 config",
        "fn": strategy_momentum,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
    {
        "name": "11. RSI + v15 config",
        "fn": strategy_rsi_oversold,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
    {
        "name": "12. Bollinger + v15 config",
        "fn": strategy_bollinger_bounce,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
    {
        "name": "13. MeanRev + v15 config",
        "fn": strategy_mean_reversion,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
    {
        "name": "14. EMA Pullback + v15",
        "fn": strategy_ema_pullback,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
    {
        "name": "15. Breakout + v15",
        "fn": strategy_breakout_volume,
        "sl": 1.0, "tp": 1.2, "hold": 3,
        "partial": True, "ptp_pct": 0.70, "ptp_ratio": 0.50,
        "smart": True, "be": 0.7, "regime_f": True,
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ana
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()
    days = args.days

    symbols = config.SYMBOLS

    print(f"\n{'='*76}")
    print(f"  TÜM STRATEJİ BACKTEST — {days} GÜN, {len(symbols)} COİN")
    print(f"  {len(TEST_SCENARIOS)} test senaryosu çalıştırılacak")
    print(f"{'='*76}")

    # Veri indir (cache'li — sadece 1 kere indirilir)
    print(f"\n  📥 Veri indiriliyor...")
    data = {}
    for sym in symbols:
        print(f"     {sym}...", end=" ", flush=True)
        df = fetch_candles(sym, "4h", days)
        if df.empty or len(df) < 120:
            print(f"ATLA ({len(df)} mum)")
            continue
        print(f"{len(df)} mum ✓")
        data[sym] = df

    print(f"\n  {len(data)} coin hazır.\n")

    # Her senaryo
    results = []
    for scenario in TEST_SCENARIOS:
        name = scenario["name"]
        fn = scenario["fn"]
        print(f"  ⏳ {name}...", end=" ", flush=True)

        all_trades = []
        for sym, df in data.items():
            trades = run_backtest(
                symbol=sym,
                df=df,
                strategy_fn=fn,
                sl_mult=scenario["sl"],
                tp_mult=scenario["tp"],
                max_hold=scenario["hold"],
                partial_tp_enabled=scenario.get("partial", False),
                partial_tp_pct=scenario.get("ptp_pct", 0.70),
                partial_tp_ratio=scenario.get("ptp_ratio", 0.50),
                smart_exit=scenario.get("smart", False),
                breakeven_atr=scenario.get("be", 0),
                regime_filter=scenario.get("regime_f", False),
            )
            all_trades.extend(trades)

        stats = calc_stats(all_trades)
        results.append({"name": name, "stats": stats, "scenario": scenario})

        status = "✅" if stats["pf"] >= 1.0 and stats["wr"] >= 45 else "❌"
        print(f"{stats['count']:4d} trade | WR={stats['wr']:5.1f}% | PnL=${stats['pnl']:>+8.2f} | PF={stats['pf']:.2f} {status}")

    # ─── SONUÇ TABLOSU ───
    print(f"\n{'='*76}")
    print(f"  SONUÇ TABLOSU — Sıralama: Profit Factor")
    print(f"{'='*76}")
    print(f"  {'#':>2} | {'Strateji':<30} | {'Trade':>5} | {'WR':>6} | {'PnL':>10} | {'PF':>5} | {'DD':>8} |")
    print(f"  {'-'*2}-+-{'-'*30}-+-{'-'*5}-+-{'-'*6}-+-{'-'*10}-+-{'-'*5}-+-{'-'*8}-+")

    for r in sorted(results, key=lambda x: x["stats"]["pf"], reverse=True):
        s = r["stats"]
        mark = "✅" if s["pf"] >= 1.0 and s["wr"] >= 45 else "  "
        print(
            f"  {mark} | {r['name']:<30} | {s['count']:>5} | {s['wr']:>5.1f}% | "
            f"${s['pnl']:>+9.2f} | {s['pf']:>5.2f} | ${s['dd']:>7.2f} |"
        )

    # En iyi sonuç detayı
    best = max(results, key=lambda x: x["stats"]["pf"])
    bs = best["stats"]
    print(f"\n  🏆 EN İYİ: {best['name']}")
    print(f"     PF={bs['pf']:.2f} | WR={bs['wr']:.1f}% | PnL=${bs['pnl']:+.2f} | Trade={bs['count']}")
    if "exits" in bs:
        print(f"     Çıkış nedenleri:")
        for reason, data_e in sorted(bs["exits"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            print(f"       {reason:15s}: {data_e['count']:4d} trade | ${data_e['pnl']:+8.2f}")

    # Karar
    print(f"\n{'='*76}")
    passed = [r for r in results if r["stats"]["pf"] >= 1.0 and r["stats"]["wr"] >= 45]
    if passed:
        print(f"  ✅ {len(passed)} STRATEJİ GEÇTİ!")
        for p in passed:
            ps = p["stats"]
            print(f"     → {p['name']}: PF={ps['pf']:.2f}, WR={ps['wr']:.1f}%, PnL=${ps['pnl']:+.2f}")
        print(f"  → Paper trading'e geçilebilir!")
    else:
        borderline = [r for r in results if r["stats"]["pf"] >= 0.90]
        if borderline:
            print(f"  ⚠️  Geçen yok ama {len(borderline)} strateji sınırda (PF≥0.90):")
            for b in borderline:
                bst = b["stats"]
                print(f"     → {b['name']}: PF={bst['pf']:.2f}, WR={bst['wr']:.1f}%")
        else:
            print(f"  ❌ HİÇBİR STRATEJİ GEÇEMEDİ (PF≥1.0 & WR≥45%)")
    print(f"{'='*76}")

    # Dosyaya kaydet
    result_file = os.path.join(os.path.dirname(__file__), "backtest_strategies_results.txt")
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(f"Tüm Strateji Backtest — {days} gün — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Coinler: {', '.join(symbols)}\n\n")
        f.write(f"{'#':>2} | {'Strateji':<30} | {'Trade':>5} | {'WR':>6} | {'PnL':>10} | {'PF':>5} | {'DD':>8}\n")
        f.write("-" * 80 + "\n")
        for r in sorted(results, key=lambda x: x["stats"]["pf"], reverse=True):
            s = r["stats"]
            f.write(
                f"   | {r['name']:<30} | {s['count']:>5} | {s['wr']:>5.1f}% | "
                f"${s['pnl']:>+9.2f} | {s['pf']:>5.2f} | ${s['dd']:>7.2f}\n"
            )
        f.write("\n")
        for r in results:
            s = r["stats"]
            if "exits" in s and s["exits"]:
                f.write(f"\n{r['name']} çıkış nedenleri:\n")
                for reason, d in sorted(s["exits"].items(), key=lambda x: x[1]["pnl"], reverse=True):
                    f.write(f"  {reason:15s}: {d['count']:4d} trade | ${d['pnl']:+8.2f}\n")

    print(f"\n  📄 Detaylar: {result_file}")


if __name__ == "__main__":
    main()
