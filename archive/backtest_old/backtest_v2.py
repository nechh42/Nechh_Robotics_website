"""
backtest_v2.py - War Machine Backtest (Bağımsız, çalışan versiyon)
====================================================================
Pre_trade filtreli vs filtresiz karşılaştırma.
Binance'ten veri çeker, tüm stratejileri çalıştırır.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import sys

# ─── CONFIG ────────────────────────────────────────────
SYMBOLS = [
    "BTCUSDT",   # En düşük spread, en yüksek likidite
    "ETHUSDT",   # Spread: ~0.01-0.02%
    "SOLUSDT",   # Spread: ~0.01-0.03%
    "BNBUSDT",   # Spread: ~0.01-0.02%
    "XRPUSDT",   # Spread: ~0.01-0.03%
    "DOGEUSDT",  # Spread: ~0.01-0.04%
    "ADAUSDT",   # Spread: ~0.02-0.05%
    "AVAXUSDT",  # Spread: ~0.02-0.05%
    "DOTUSDT",   # Spread: ~0.02-0.05%
    "LINKUSDT",  # Spread: ~0.02-0.05%
    "SUIUSDT",   # Spread: ~0.02-0.05%
    "MATICUSDT", # Spread: ~0.02-0.05%
    "LTCUSDT",   # Spread: ~0.02-0.05%
    "NEARUSDT",  # Spread: ~0.02-0.06%
    "APTUSDT",   # Spread: ~0.02-0.06%
    "ARBUSDT",   # Spread: ~0.02-0.06%
    "OPUSDT",    # Spread: ~0.02-0.06%
    "UNIUSDT",   # Spread: ~0.02-0.06%
    "ATOMUSDT",  # Spread: ~0.03-0.07%
    "ETCUSDT",   # Spread: ~0.03-0.07%
    "WIFUSDT",   # Spread: ~0.03-0.07%
    "PEPEUSDT",  # Spread: ~0.03-0.08% (meme coin ama hacim yüksek)
    "INJUSDT",   # Spread: ~0.03-0.08%
    "FILUSDT",   # Spread: ~0.03-0.08%
    "HBARUSDT",  # Spread: ~0.03-0.08%
    "VETUSDT",   # Spread: ~0.03-0.08%
    "STXUSDT",   # Spread: ~0.03-0.08%
    "IMXUSDT",   # Spread: ~0.03-0.08%
    "RNDRUSDT",  # Spread: ~0.03-0.08%
    "SEIUSDT",   # Spread: ~0.03-0.08%
    "AAVEUSDT",  # Spread: ~0.03-0.08%
    "MKRUSDT",   # Spread: ~0.03-0.08%
    "GRTUSDT",   # Spread: ~0.04-0.09%
    "ALGOUSDT",  # Spread: ~0.04-0.09%
    "ICPUSDT",   # Spread: ~0.04-0.09%
    "QNTUSDT",   # Spread: ~0.04-0.09%
    "FLOWUSDT",  # Spread: ~0.04-0.09%
    "SANDUSDT",  # Spread: ~0.04-0.09%
    "GALAUSDT",  # Spread: ~0.04-0.09%
    "MANAUSDT",  # Spread: ~0.04-0.09%
    "AXSUSDT",   # Spread: ~0.04-0.09%
    "APEUSDT",   # Spread: ~0.04-0.09%
    "LDOUSDT",   # Spread: ~0.04-0.09%
    "FTMUSDT",   # Spread: ~0.04-0.09%
    "CRVUSDT",   # Spread: ~0.04-0.09%
    "KAVAUSDT",  # Spread: ~0.04-0.10%
    "ZECUSDT",   # Spread: ~0.04-0.10%
    "XLMUSDT",   # Spread: ~0.04-0.10%
    "EOSUSDT",   # Spread: ~0.04-0.10%
    "THETAUSDT", # Spread: ~0.04-0.10%
]

INTERVAL = "1h"
DAYS = 30
INITIAL_BALANCE = 10000.0
COMMISSION = 0.001
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BB_PERIOD = 20
DONCHIAN_PERIOD = 10
MIN_CONFIDENCE = 0.40
RISK_PCT = 0.02       # %2 risk per trade
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.0
MAX_POSITIONS = 4

# ─── VERİ ÇEKME ────────────────────────────────────────
def fetch_klines(symbol, interval="1h", days=30):
    url = "https://api.binance.com/api/v3/klines"
    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)
    all_data = []
    current = start_ms
    while current < end_ms:
        try:
            r = requests.get(url, params={"symbol": symbol, "interval": interval,
                             "startTime": current, "limit": 1000}, timeout=15)
            data = r.json()
            if not data: break
            all_data.extend(data)
            current = data[-1][0] + 1
        except: break
    if not all_data: return None
    df = pd.DataFrame(all_data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qv","tc","tbb","tbq","ignore"])
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.reset_index(drop=True)

# ─── İNDİKATÖRLER ──────────────────────────────────────
def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    ag = gain.ewm(alpha=1/period, min_periods=period).mean()
    al = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = ag / (al + 1e-10)
    return 100 - (100 / (1 + rs))

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr(df, period=14):
    h, l, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_macd(closes):
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calc_bb(closes, period=20, std=2.0):
    mid = closes.rolling(period).mean()
    s = closes.rolling(period).std()
    return mid + std*s, mid, mid - std*s, (mid+std*s - (mid-std*s))/(mid+1e-10)

def calc_vwap(df):
    if df["volume"].sum() == 0: return df["close"]
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / (df["volume"].cumsum() + 1e-10)

# ─── REJİM TESPİTİ ─────────────────────────────────────
def detect_regime(df):
    if len(df) < 50: return "RANGING"
    closes = df["close"]
    price = closes.iloc[-1]
    # ADX approx
    pr = df["high"].max() - df["low"].min()
    trend_move = abs(price - closes.iloc[-14]) if len(closes) >= 14 else 0
    adx = min(float(trend_move / pr) * 100, 100.0) if pr > 0 else 0
    # Volatility
    rets = closes.pct_change().dropna()
    vol_ratio = rets.tail(5).std() / (rets.std() + 1e-10) if len(rets) >= 10 else 1.0
    atr_val = calc_atr(df).iloc[-1] if len(df) > 14 else 0
    if vol_ratio > 1.5 and atr_val > price * 0.02: return "VOLATILE"
    pc20 = ((price - closes.iloc[-20]) / closes.iloc[-20] * 100) if len(closes) >= 20 else 0
    if adx > 25:
        if pc20 > 2: return "TREND_UP"
        elif pc20 < -2: return "TREND_DOWN"
    ema20 = calc_ema(closes, 20).iloc[-1]
    ema50 = calc_ema(closes, 50).iloc[-1]
    if pd.isna(ema20) or pd.isna(ema50): return "RANGING"
    if price > ema20 > ema50 and pc20 > 0: return "TREND_UP"
    elif price < ema20 < ema50 and pc20 < 0: return "TREND_DOWN"
    return "RANGING"

# ─── STRATEJİLER ───────────────────────────────────────
def rsi_signal(df, regime):
    rsi = calc_rsi(df["close"]).iloc[-1]
    macd, sig = calc_macd(df["close"])
    macd_bull = macd.iloc[-1] > sig.iloc[-1]
    macd_bear = macd.iloc[-1] < sig.iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna(rsi): return "NONE", 0.0

    if rsi < RSI_OVERSOLD:
        depth = (RSI_OVERSOLD - rsi) / RSI_OVERSOLD
        conf = min(0.85, 0.55 + 0.30 * depth)
        if regime == "TREND_DOWN": conf *= 0.7
        if not macd_bull: conf *= 0.8
        return "LONG", conf
    elif rsi > RSI_OVERBOUGHT:
        depth = (rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT)
        conf = min(0.85, 0.55 + 0.30 * depth)
        if regime == "TREND_UP": conf *= 0.7
        if not macd_bear: conf *= 0.8
        return "SHORT", conf
    return "NONE", 0.0

def momentum_signal(df, regime):
    price = df["close"].iloc[-1]
    period = 10 if regime in ("TREND_UP", "TREND_DOWN") else 20
    dh = df["high"].iloc[-period-1:-1].max()
    dl = df["low"].iloc[-period-1:-1].min()
    breakout_up = price > dh
    breakout_down = price < dl
    if not breakout_up and not breakout_down: return "NONE", 0.0

    ema9 = calc_ema(df["close"], 9).iloc[-1]
    ema21 = calc_ema(df["close"], 21).iloc[-1]
    _, _, _, bw = calc_bb(df["close"])
    bb_exp = bw.iloc[-1] > bw.iloc[-5:-1].mean() * 1.02

    if breakout_up:
        score = 0.40
        if ema9 > ema21: score += 0.15
        if bb_exp: score += 0.10
        if regime == "TREND_UP": score += 0.05
        return "LONG", min(0.90, score)
    else:
        score = 0.40
        if ema9 < ema21: score += 0.15
        if bb_exp: score += 0.10
        if regime == "TREND_DOWN": score += 0.05
        return "SHORT", min(0.90, score)

def vwap_signal(df, regime):
    if regime != "RANGING": return "NONE", 0.0
    price = df["close"].iloc[-1]
    vwap = calc_vwap(df).iloc[-1]
    rsi = calc_rsi(df["close"]).iloc[-1]
    if pd.isna(rsi) or vwap <= 0: return "NONE", 0.0
    dev = (price - vwap) / vwap
    if dev < -0.01 and rsi < 35:
        return "LONG", min(0.85, 0.55 + abs(dev)/0.01 * 0.10)
    elif dev > 0.01 and rsi > 65:
        return "SHORT", min(0.85, 0.55 + dev/0.01 * 0.10)
    return "NONE", 0.0

def get_combined_signal(df, regime):
    r_act, r_conf = rsi_signal(df, regime)
    m_act, m_conf = momentum_signal(df, regime)
    v_act, v_conf = vwap_signal(df, regime)

    signals = [(r_act, r_conf, "RSI"), (m_act, m_conf, "MOM"), (v_act, v_conf, "VWAP")]
    active = [(a, c, n) for a, c, n in signals if a != "NONE" and c >= MIN_CONFIDENCE]
    if not active: return "NONE", 0.0, ""

    long_sigs = [(a,c,n) for a,c,n in active if a == "LONG"]
    short_sigs = [(a,c,n) for a,c,n in active if a == "SHORT"]

    # Çakışma kontrolü
    strong_long = [s for s in long_sigs if s[1] >= 0.55]
    strong_short = [s for s in short_sigs if s[1] >= 0.55]
    if strong_long and strong_short: return "NONE", 0.0, "CONFLICT"

    if long_sigs and (not short_sigs or max(c for _,c,_ in long_sigs) > max(c for _,c,_ in short_sigs)):
        best_conf = max(c for _,c,_ in long_sigs)
        bonus = 1.15 if len(long_sigs) >= 2 else 1.0
        return "LONG", min(0.95, best_conf * bonus), "+".join(n for _,_,n in long_sigs)
    elif short_sigs:
        best_conf = max(c for _,c,_ in short_sigs)
        bonus = 1.15 if len(short_sigs) >= 2 else 1.0
        return "SHORT", min(0.95, best_conf * bonus), "+".join(n for _,_,n in short_sigs)
    return "NONE", 0.0, ""

# ─── PRE_TRADE FİLTRESİ ────────────────────────────────
def pre_trade_check(action, regime, confidence):
    if regime == "VOLATILE": return False, "VOLATILE"
    if regime == "TREND_UP" and action == "SHORT": return False, "TREND_UP→LONG only"
    if regime == "TREND_DOWN" and action == "LONG": return False, "TREND_DOWN→SHORT only"
    if regime == "RANGING" and action == "LONG" and confidence < 0.60: return False, "RANGING LONG conf<0.60"
    return True, "OK"

# ─── ANA BACKTEST FONKSİYONU ───────────────────────────
def run_backtest(symbol, df, use_pretrade=True):
    balance = INITIAL_BALANCE
    position = None
    trades = []
    equity = [INITIAL_BALANCE]

    for i in range(50, len(df)):
        window = df.iloc[max(0,i-100):i+1].copy().reset_index(drop=True)
        price = window["close"].iloc[-1]
        ts = str(df["timestamp"].iloc[i])

        # SL/TP kontrolü
        if position:
            hit, reason = False, ""
            if position["side"] == "LONG":
                if price <= position["sl"]: hit, reason = True, "SL"
                elif price >= position["tp"]: hit, reason = True, "TP"
            else:
                if price >= position["sl"]: hit, reason = True, "SL"
                elif price <= position["tp"]: hit, reason = True, "TP"
            if hit:
                if position["side"] == "LONG":
                    gross = (price - position["entry"]) * position["size"]
                else:
                    gross = (position["entry"] - price) * position["size"]
                comm = price * position["size"] * COMMISSION
                net = gross - comm
                balance += net
                trades.append({"side": position["side"], "entry": position["entry"],
                               "exit": price, "net": net, "reason": reason, "ts": ts})
                position = None

        # Yeni sinyal
        if position is None:
            regime = detect_regime(window)
            action, conf, strats = get_combined_signal(window, regime)

            if action != "NONE":
                approved = True
                if use_pretrade:
                    approved, _ = pre_trade_check(action, regime, conf)

                if approved:
                    atr = calc_atr(window).iloc[-1]
                    if pd.isna(atr) or atr == 0: atr = price * 0.02
                    sl_dist = max(atr * SL_ATR_MULT, price * 0.015)
                    tp_dist = max(atr * TP_ATR_MULT, price * 0.02)
                    risk_amt = balance * RISK_PCT
                    size = risk_amt / sl_dist
                    comm = price * size * COMMISSION
                    balance -= comm

                    if action == "LONG":
                        sl, tp = price - sl_dist, price + tp_dist
                    else:
                        sl, tp = price + sl_dist, price - tp_dist

                    position = {"side": action, "entry": price, "size": size,
                               "sl": sl, "tp": tp, "ts": ts}
        equity.append(balance)

    # Açık pozisyonu kapat
    if position:
        price = df["close"].iloc[-1]
        gross = (price - position["entry"]) * position["size"] if position["side"] == "LONG" \
                else (position["entry"] - price) * position["size"]
        comm = price * position["size"] * COMMISSION
        net = gross - comm
        balance += net
        trades.append({"side": position["side"], "entry": position["entry"],
                       "exit": price, "net": net, "reason": "END", "ts": "end"})

    # Hesapla
    if not trades:
        return {"symbol": symbol, "trades": 0, "wr": 0, "pnl": 0, "dd": 0, "sharpe": 0}

    pnls = [t["net"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) * 100

    peak, max_dd = INITIAL_BALANCE, 0
    for eq in equity:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd: max_dd = dd

    avg = np.mean(pnls)
    std = np.std(pnls)
    sharpe = avg / std if std > 0 else 0

    return {
        "symbol": symbol,
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "wr": wr,
        "pnl": sum(pnls),
        "dd": max_dd * 100,
        "sharpe": sharpe,
        "avg": avg,
        "best": max(pnls),
        "worst": min(pnls),
        "final_bal": balance,
    }

# ─── ÇALIŞTIR ──────────────────────────────────────────
print(f"\n{'='*70}")
print(f"WAR MACHINE BACKTEST — {DAYS} gün, {INTERVAL}")
print(f"{'='*70}")

results_with = []
results_without = []

for sym in SYMBOLS:
    print(f"\n{sym} verisi çekiliyor...", end=" ", flush=True)
    df = fetch_klines(sym, INTERVAL, DAYS)
    if df is None or len(df) < 60:
        print("VERİ YOK, atlandı")
        continue
    print(f"{len(df)} mum")

    r_with = run_backtest(sym, df, use_pretrade=True)
    r_without = run_backtest(sym, df, use_pretrade=False)
    results_with.append(r_with)
    results_without.append(r_without)

# ─── RAPOR ─────────────────────────────────────────────
def print_table(results, title):
    print(f"\n{'='*75}")
    print(f"  {title}")
    print(f"{'='*75}")
    print(f"{'Sembol':<12} {'Trade':>5} {'Kazanç':>6} {'WR%':>5} {'PnL':>9} {'MaxDD%':>6} {'Sharpe':>6} {'Ort/Trade':>9}")
    print(f"{'-'*75}")
    total_pnl = 0
    total_trades = 0
    for r in results:
        if r["trades"] == 0:
            print(f"{r['symbol']:<12} {'—':>5}")
            continue
        icon = "✅" if r["pnl"] > 0 else "❌"
        print(f"{r['symbol']:<12} {r['trades']:>5} {r.get('wins',0):>6} {r['wr']:>4.1f}% "
              f"${r['pnl']:>8.2f} {r['dd']:>5.1f}% {r['sharpe']:>6.2f} ${r['avg']:>8.2f} {icon}")
        total_pnl += r["pnl"]
        total_trades += r["trades"]
    print(f"{'-'*75}")
    print(f"{'TOPLAM':<12} {total_trades:>5} {'':>6} {'':>5} ${total_pnl:>8.2f}")
    print(f"Kârlı coin: {sum(1 for r in results if r['pnl'] > 0)}/{len(results)}")

print_table(results_without, "PRE_TRADE FİLTRESİZ (ham strateji)")
print_table(results_with, "PRE_TRADE FİLTRELİ (canlı sistem gibi)")

# Fark analizi
print(f"\n{'='*75}")
print(f"  KARŞILAŞTIRMA — Filtre ne kadar etki ediyor?")
print(f"{'='*75}")
print(f"{'Sembol':<12} {'Filtresiz PnL':>13} {'Filtreli PnL':>13} {'Fark':>10} {'Trade Farkı':>11}")
print(f"{'-'*75}")
for rw, rf in zip(results_without, results_with):
    diff = rf["pnl"] - rw["pnl"]
    tdiff = rf["trades"] - rw["trades"]
    icon = "↑" if diff > 0 else "↓"
    print(f"{rw['symbol']:<12} ${rw['pnl']:>12.2f} ${rf['pnl']:>12.2f} ${diff:>9.2f} {icon}  {tdiff:>+5} trade")

total_wo = sum(r["pnl"] for r in results_without)
total_w = sum(r["pnl"] for r in results_with)
print(f"{'-'*75}")
print(f"{'TOPLAM':<12} ${total_wo:>12.2f} ${total_w:>12.2f} ${total_w-total_wo:>9.2f}")
print(f"\n{'='*75}")