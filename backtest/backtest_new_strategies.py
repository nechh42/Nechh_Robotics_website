"""
backtest_new_strategies.py — 10 Yeni Strateji Testi
=====================================================
Daha önce denenmemiş stratejileri test eder.
Mean-reversion çalıştığına göre, o kategoriye ağırlık verildi.

Kullanım:
    python -m backtest.backtest_new_strategies
"""

import sys, os
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
    calc_bollinger, calc_vwap, calc_sma,
)
from strategies.regime import detect_regime

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Veri (cache'li)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CACHE = {}

def fetch_candles(symbol, interval, days):
    key = f"{symbol}_{interval}_{days}"
    if key in _CACHE:
        return _CACHE[key].copy()
    url = "https://api.binance.com/api/v3/klines"
    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = int((now - timedelta(days=days + 10)).timestamp() * 1000)
    rows = []
    while start_ms < end_ms:
        r = requests.get(url, params={"symbol": symbol, "interval": interval,
                                       "startTime": start_ms, "limit": 1000}, timeout=30)
        r.raise_for_status()
        d = r.json()
        if not d: break
        rows.extend(d)
        start_ms = d[-1][0] + 1
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume",
                                      "close_time","qv","trades","tbb","tbq","ig"])
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df[["time","open","high","low","close","volume"]].reset_index(drop=True)
    _CACHE[key] = df.copy()
    return df


@dataclass
class Trade:
    symbol: str; entry_price: float; entry_time: datetime
    stop_loss: float; take_profit: float; size: float
    exit_price: float = 0.0; exit_time: Optional[datetime] = None
    exit_reason: str = ""; pnl: float = 0.0; hold_candles: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Yardımcı İndikatörler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_stoch_rsi(close, period=14, k_period=3, d_period=3):
    """Stochastic RSI → %K, %D"""
    rsi = calc_rsi(close, period)
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    k = stoch_rsi.rolling(k_period).mean() * 100
    d = k.rolling(d_period).mean()
    return k, d

def calc_cci(df, period=20):
    """Commodity Channel Index"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma) / (0.015 * mad + 1e-10)

def calc_williams_r(df, period=14):
    """Williams %R"""
    high_max = df["high"].rolling(period).max()
    low_min = df["low"].rolling(period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min + 1e-10)

def calc_obv(df):
    """On-Balance Volume (vectorized)"""
    close = df["close"].values
    vol = df["volume"].values
    direction = np.sign(np.diff(close, prepend=close[0]))
    return pd.Series(np.cumsum(direction * vol), index=df.index)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10 YENİ STRATEJİ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def strat_stoch_rsi_bounce(df, symbol, regime):
    """StochRSI < 20 ve %K > %D (yukarı çapraz) → LONG"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    k, d = calc_stoch_rsi(close)
    k_now, d_now = k.iloc[-1], d.iloc[-1]
    k_prev, d_prev = k.iloc[-2], d.iloc[-2]
    if pd.isna(k_now) or pd.isna(d_now): return None

    # StochRSI oversold + bullish crossover
    if k_now < 20 and k_now > d_now and k_prev <= d_prev:
        return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}
    # Çok derin oversold (< 10) — crossover bekleme
    if k_now < 10 and d_now < 15:
        return {"action": "LONG", "price": price, "atr": atr, "conf": 0.60}
    return None


def strat_keltner_bounce(df, symbol, regime):
    """Keltner Channel alt bandına dokunma → LONG (ATR-based Bollinger)"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    ema20 = calc_ema(close, 20).iloc[-1]
    if pd.isna(ema20): return None

    # Keltner bands: EMA ± 2×ATR
    upper = ema20 + 2 * atr
    lower = ema20 - 2 * atr

    if price > lower: return None

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 45: return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strat_cci_oversold(df, symbol, regime):
    """CCI < -100 → oversold bounce"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    cci = calc_cci(df, 20)
    cci_now = cci.iloc[-1]
    if pd.isna(cci_now): return None

    if cci_now >= -100: return None

    # Daha derin = daha güçlü sinyal
    conf = min(0.80, 0.58 + abs(cci_now + 100) / 500)
    return {"action": "LONG", "price": price, "atr": atr, "conf": conf}


def strat_rsi_divergence(df, symbol, regime):
    """Bullish RSI Divergence: fiyat düşük yapıyor ama RSI yükseliyor"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    rsi = calc_rsi(close, 14)
    if pd.isna(rsi.iloc[-1]): return None

    # Son 10 mumda: fiyat düşük ama RSI yükseliş
    window = 10
    if len(close) < window + 5: return None

    price_recent_low = close.iloc[-window:].min()
    price_prev_low = close.iloc[-window*2:-window].min()
    rsi_at_recent = rsi.iloc[-window:].min()
    rsi_at_prev = rsi.iloc[-window*2:-window].min()

    if pd.isna(rsi_at_recent) or pd.isna(rsi_at_prev): return None

    # Fiyat daha düşük dip + RSI daha yüksek dip = bullish divergence
    if price_recent_low < price_prev_low and rsi_at_recent > rsi_at_prev:
        if rsi.iloc[-1] < 40:  # Hâlâ düşük RSI bölgesinde
            return {"action": "LONG", "price": price, "atr": atr, "conf": 0.70}
    return None


def strat_williams_r_bounce(df, symbol, regime):
    """Williams %R < -80 (oversold) bounce"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    wr = calc_williams_r(df, 14)
    wr_now = wr.iloc[-1]
    if pd.isna(wr_now): return None

    if wr_now >= -80: return None

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 40: return None

    conf = min(0.78, 0.60 + abs(wr_now + 80) / 100)
    return {"action": "LONG", "price": price, "atr": atr, "conf": conf}


def strat_macd_histogram_rev(df, symbol, regime):
    """MACD histogram negatiften pozitife geçiş + RSI < 50"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    macd, sig, hist = calc_macd(close)
    if pd.isna(hist.iloc[-1]) or pd.isna(hist.iloc[-2]): return None

    # Histogram negatiften pozitife
    if hist.iloc[-2] < 0 and hist.iloc[-1] > 0:
        rsi = calc_rsi(close, 14).iloc[-1]
        if pd.isna(rsi): return None
        if rsi < 55:
            conf = 0.63 if rsi < 45 else 0.58
            return {"action": "LONG", "price": price, "atr": atr, "conf": conf}
    return None


def strat_double_bottom(df, symbol, regime):
    """Double Bottom (W pattern): İki yakın dip + ikinci dip daha yüksek RSI"""
    if len(df) < 40: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    # Son 20 mumda en düşük noktayı bul
    window1 = close.iloc[-20:-10]
    window2 = close.iloc[-10:]
    if len(window1) < 5 or len(window2) < 5: return None

    low1 = window1.min()
    low2 = window2.min()

    # İki dip yakın seviyede (%2 tolerans)
    if abs(low1 - low2) / low1 > 0.02: return None
    # Fiyat şu an diplerden yukarıda
    if price < low2 * 1.01: return None

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi < 35 or rsi > 55: return None

    # İkinci dip yükselen RSI ile (bullish)
    rsi_series = calc_rsi(close, 14)
    rsi_at_low1 = rsi_series.iloc[-20:-10].min()
    rsi_at_low2 = rsi_series.iloc[-10:].min()
    if pd.isna(rsi_at_low1) or pd.isna(rsi_at_low2): return None

    if rsi_at_low2 > rsi_at_low1:  # Bullish divergence at double bottom
        return {"action": "LONG", "price": price, "atr": atr, "conf": 0.72}
    return None


def strat_engulfing(df, symbol, regime):
    """Bullish Engulfing: Önceki kırmızı mum tamamen yeşil mumla sarılıyor"""
    if len(df) < 30: return None
    price = df["close"].iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    # Mevcut mum
    o1, c1 = df["open"].iloc[-1], df["close"].iloc[-1]
    # Önceki mum
    o0, c0 = df["open"].iloc[-2], df["close"].iloc[-2]

    # Önceki: kırmızı, mevcut: yeşil
    if not (c0 < o0 and c1 > o1): return None

    # Engulfing: yeşil mum kırmızıyı tamamen kaplar
    if not (o1 <= c0 and c1 >= o0): return None

    # Trend filtresi: düşüşten sonra olmalı
    rsi = calc_rsi(df["close"], 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 50: return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.65}


def strat_obv_divergence(df, symbol, regime):
    """OBV Divergence: Fiyat düşerken OBV yükseliyor (biriktirim)"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    obv = calc_obv(df)
    if len(obv) < 20: return None

    # Son 10 mum: fiyat düşüş, OBV yükseliş
    price_slope = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10]
    obv_slope = obv.iloc[-1] - obv.iloc[-10]

    if price_slope >= -0.02: return None  # Fiyat düşmeli (%2+)
    if obv_slope <= 0: return None  # OBV yükselmeli

    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 45: return None

    return {"action": "LONG", "price": price, "atr": atr, "conf": 0.68}


def strat_pivot_bounce(df, symbol, regime):
    """Pivot Support Bounce: Klasik pivot noktası desteğinden dönüş"""
    if len(df) < 30: return None
    close = df["close"]; price = close.iloc[-1]
    atr = calc_atr(df, 14).iloc[-1]
    if pd.isna(atr) or atr <= 0: return None

    # Son 6 mumun (1 gün = 6×4h) pivot hesabı
    day_high = df["high"].iloc[-7:-1].max()
    day_low = df["low"].iloc[-7:-1].min()
    day_close = df["close"].iloc[-2]

    pivot = (day_high + day_low + day_close) / 3
    s1 = 2 * pivot - day_high     # support 1
    s2 = pivot - (day_high - day_low)  # support 2

    # Fiyat S1 veya S2'ye yakın (%0.5 tolerans)
    near_s1 = abs(price - s1) / price < 0.005
    near_s2 = abs(price - s2) / price < 0.005

    if not (near_s1 or near_s2): return None

    # RSI teyidi
    rsi = calc_rsi(close, 14).iloc[-1]
    if pd.isna(rsi) or rsi >= 45: return None

    conf = 0.68 if near_s2 else 0.62  # S2 daha güçlü destek
    return {"action": "LONG", "price": price, "atr": atr, "conf": conf}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Backtest Motoru (basit)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_bt(symbol, df, fn, sl=1.0, tp=1.0, hold=1):
    trades = []; ot = None; hc = 0
    for i in range(100, len(df)):
        w = df.iloc[i-100:i+1].copy().reset_index(drop=True)
        cur = df.iloc[i]; p = cur["close"]; h = cur["high"]; l = cur["low"]

        if ot:
            hc += 1
            if l <= ot.stop_loss:
                ot.exit_price=ot.stop_loss; ot.exit_reason="SL"; ot.hold_candles=hc
                ot.pnl=(ot.exit_price-ot.entry_price)*ot.size - ot.entry_price*ot.size*0.002
                trades.append(ot); ot=None; hc=0; continue
            if h >= ot.take_profit:
                ot.exit_price=ot.take_profit; ot.exit_reason="TP"; ot.hold_candles=hc
                ot.pnl=(ot.exit_price-ot.entry_price)*ot.size - ot.entry_price*ot.size*0.002
                trades.append(ot); ot=None; hc=0; continue
            if hc >= hold:
                ot.exit_price=p; ot.exit_reason="TIME"; ot.hold_candles=hc
                ot.pnl=(ot.exit_price-ot.entry_price)*ot.size - ot.entry_price*ot.size*0.002
                trades.append(ot); ot=None; hc=0; continue
            continue

        regime = detect_regime(w)
        if regime in ("TREND_DOWN","VOLATILE"): continue
        sig = fn(w, symbol, regime)
        if not sig or sig["action"] != "LONG": continue
        if sig["conf"] < 0.55: continue

        a = sig["atr"]; sd = a*sl; td = a*tp
        ms = sig["price"]*0.005
        if sd < ms:
            sc = ms/sd; sd=ms; td*=sc
        eq = 10000.0
        sz = min(eq*0.005/sd, eq*0.10/sig["price"])
        ot = Trade(symbol=symbol, entry_price=sig["price"], entry_time=cur["time"],
                   stop_loss=sig["price"]-sd, take_profit=sig["price"]+td, size=sz)
        hc = 0

    if ot:
        last=df.iloc[-1]
        ot.exit_price=last["close"]; ot.exit_reason="END"; ot.hold_candles=hc
        ot.pnl=(ot.exit_price-ot.entry_price)*ot.size - ot.entry_price*ot.size*0.002
        trades.append(ot)
    return trades


def stats(trades):
    if not trades: return {"n":0,"wr":0,"pnl":0,"pf":0,"dd":0}
    w = [t for t in trades if t.pnl > 0]
    l = [t for t in trades if t.pnl <= 0]
    gp = sum(t.pnl for t in w) if w else 0
    gl = abs(sum(t.pnl for t in l)) if l else 0.001
    cum=pk=dd=0.0
    for t in sorted(trades, key=lambda x:x.entry_time):
        cum+=t.pnl; pk=max(pk,cum); dd=max(dd,pk-cum)
    return {"n":len(trades),"wr":len(w)/len(trades)*100,"pnl":sum(t.pnl for t in trades),
            "pf":gp/gl,"dd":dd}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Listesi
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRATEGIES = [
    ("Stochastic RSI Bounce", strat_stoch_rsi_bounce),
    ("Keltner Channel Bounce", strat_keltner_bounce),
    ("CCI Oversold (<-100)", strat_cci_oversold),
    ("RSI Divergence", strat_rsi_divergence),
    ("Williams %R Bounce", strat_williams_r_bounce),
    ("MACD Histogram Rev", strat_macd_histogram_rev),
    ("Double Bottom (W)", strat_double_bottom),
    ("Bullish Engulfing", strat_engulfing),
    ("OBV Divergence", strat_obv_divergence),
    ("Pivot Support Bounce", strat_pivot_bounce),
]

CONFIGS = [
    {"sl":1.0, "tp":1.0, "hold":1, "tag":"SL1 TP1 H1"},
    {"sl":1.0, "tp":1.0, "hold":2, "tag":"SL1 TP1 H2"},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    symbols = config.SYMBOLS
    print(f"\n{'='*78}")
    print(f"  10 YENİ STRATEJİ TESTİ — {args.days} GÜN, {len(symbols)} coin")
    print(f"{'='*78}")

    print(f"\n  📥 Veri indiriliyor...")
    data = {}
    for sym in symbols:
        print(f"     {sym}...", end=" ", flush=True)
        df = fetch_candles(sym, "4h", args.days)
        if df.empty or len(df) < 120:
            print("ATLA"); continue
        print(f"{len(df)} mum ✓")
        data[sym] = df

    all_results = []

    for cfg in CONFIGS:
        print(f"\n{'─'*78}")
        print(f"  Config: {cfg['tag']}")
        print(f"{'─'*78}")

        for name, fn in STRATEGIES:
            trades = []
            for sym, df in data.items():
                trades.extend(run_bt(sym, df, fn, cfg["sl"], cfg["tp"], cfg["hold"]))
            s = stats(trades)
            ok = "✅" if s["pf"] >= 1.0 and s["wr"] >= 45 else "  "
            print(f"  {ok} {name:<25s} | {s['n']:4d} trade | WR={s['wr']:5.1f}% | "
                  f"PnL=${s['pnl']:>+8.2f} | PF={s['pf']:>5.2f} | DD=${s['dd']:>7.2f}")
            all_results.append({"name": name, "cfg": cfg["tag"], **s})

    # ─── Özet ───
    print(f"\n{'='*78}")
    print(f"  ÖZET — En İyi Sonuçlar (PF sıralı)")
    print(f"{'='*78}")

    passed = [r for r in all_results if r["pf"] >= 1.0 and r["wr"] >= 45]
    borderline = [r for r in all_results if 0.9 <= r["pf"] < 1.0 or (r["pf"] >= 1.0 and r["wr"] < 45)]

    if passed:
        print(f"\n  ✅ GEÇENLER:")
        for r in sorted(passed, key=lambda x: x["pf"], reverse=True):
            print(f"     {r['name']:<25s} [{r['cfg']}] | {r['n']:3d}t WR={r['wr']:.1f}% "
                  f"PnL=${r['pnl']:+.2f} PF={r['pf']:.2f}")

    if borderline:
        print(f"\n  ⚠️  SINIRDA:")
        for r in sorted(borderline, key=lambda x: x["pf"], reverse=True):
            print(f"     {r['name']:<25s} [{r['cfg']}] | {r['n']:3d}t WR={r['wr']:.1f}% "
                  f"PnL=${r['pnl']:+.2f} PF={r['pf']:.2f}")

    failed = [r for r in all_results if r["pf"] < 0.9]
    if failed:
        print(f"\n  ❌ BAŞARISIZ ({len(failed)} test)")

    print(f"\n{'='*78}")


if __name__ == "__main__":
    main()
