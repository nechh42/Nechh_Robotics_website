"""
backtest_short_only.py - SHORT-ONLY Backtest
Sadece SHORT pozisyonlar açılır.
TREND_DOWN ve RANGING'de SHORT — TREND_UP'ta bekle.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime

SYMBOLS = [
    "ZECUSDT",  "PEPEUSDT",  "UNIUSDT",   "ADAUSDT",
    "ETHUSDT",  "LDOUSDT",   "BNBUSDT",   "DOGEUSDT",
    "AAVEUSDT", "LTCUSDT",   "XRPUSDT",   "ATOMUSDT",
    "BTCUSDT",
]

INTERVAL = "1h"
DAYS = 30
INITIAL_BALANCE = 10000.0
COMMISSION = 0.001
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MIN_CONFIDENCE = 0.40
RISK_PCT = 0.02
SL_ATR_MULT = 1.5
TP_ATR_MULT = 2.0

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
    return mid+std*s, mid, mid-std*s, (mid+std*s-(mid-std*s))/(mid+1e-10)

def detect_regime(df):
    if len(df) < 50: return "RANGING"
    closes = df["close"]
    price = closes.iloc[-1]
    pr = df["high"].max() - df["low"].min()
    trend_move = abs(price - closes.iloc[-14]) if len(closes) >= 14 else 0
    adx = min(float(trend_move / pr) * 100, 100.0) if pr > 0 else 0
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

def get_short_signal(df, regime):
    """Sadece SHORT sinyali üret"""
    if regime in ("TREND_UP", "VOLATILE"):
        return False, 0.0

    price = df["close"].iloc[-1]
    
    # Momentum SHORT
    period = 10 if regime == "TREND_DOWN" else 20
    dl = df["low"].iloc[-period-1:-1].min()
    breakout_down = price < dl
    
    ema9 = calc_ema(df["close"], 9).iloc[-1]
    ema21 = calc_ema(df["close"], 21).iloc[-1]
    _, _, _, bw = calc_bb(df["close"])
    bb_exp = bw.iloc[-1] > bw.iloc[-5:-1].mean() * 1.02

    mom_conf = 0.0
    if breakout_down:
        score = 0.40
        if ema9 < ema21: score += 0.15
        if bb_exp: score += 0.10
        if regime == "TREND_DOWN": score += 0.05
        mom_conf = min(0.90, score)

    # RSI SHORT
    rsi = calc_rsi(df["close"]).iloc[-1]
    macd, sig = calc_macd(df["close"])
    macd_bear = macd.iloc[-1] < sig.iloc[-1]
    rsi_conf = 0.0
    if not pd.isna(rsi) and rsi > RSI_OVERBOUGHT:
        depth = (rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT)
        conf = min(0.85, 0.55 + 0.30 * depth)
        if regime == "TREND_UP": conf *= 0.7
        if not macd_bear: conf *= 0.8
        rsi_conf = conf

    best_conf = max(mom_conf, rsi_conf)
    if best_conf >= MIN_CONFIDENCE:
        return True, best_conf
    return False, 0.0

def run_backtest(symbol, df):
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
            if price >= position["sl"]: hit, reason = True, "SL"
            elif price <= position["tp"]: hit, reason = True, "TP"
            if hit:
                gross = (position["entry"] - price) * position["size"]
                comm = price * position["size"] * COMMISSION
                net = gross - comm
                balance += net
                trades.append({"entry": position["entry"], "exit": price,
                               "net": net, "reason": reason, "ts": ts})
                position = None

        if position is None:
            regime = detect_regime(window)
            should_short, conf = get_short_signal(window, regime)

            if should_short:
                atr = calc_atr(window).iloc[-1]
                if pd.isna(atr) or atr == 0: atr = price * 0.02
                sl_dist = max(atr * SL_ATR_MULT, price * 0.015)
                tp_dist = max(atr * TP_ATR_MULT, price * 0.03)  # %3.0 (was %2.0)
                risk_amt = balance * RISK_PCT
                size = risk_amt / sl_dist
                comm = price * size * COMMISSION
                balance -= comm
                sl = price + sl_dist
                tp = price - tp_dist
                position = {"entry": price, "size": size, "sl": sl, "tp": tp}
        equity.append(balance)

    # Açık pozisyonu kapat
    if position:
        price = df["close"].iloc[-1]
        gross = (position["entry"] - price) * position["size"]
        comm = price * position["size"] * COMMISSION
        net = gross - comm
        balance += net
        trades.append({"entry": position["entry"], "exit": price,
                       "net": net, "reason": "END", "ts": "end"})

    if not trades:
        return {"symbol": symbol, "trades": 0, "wr": 0, "pnl": 0,
                "dd": 0, "sharpe": 0, "avg": 0}

    pnls = [t["net"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    peak, max_dd = INITIAL_BALANCE, 0
    for eq in equity:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd: max_dd = dd

    avg = np.mean(pnls)
    std = np.std(pnls)
    sharpe = avg / std if std > 0 else 0
    
    wins_sum = sum(p for p in pnls if p > 0)
    loss_sum = abs(sum(p for p in pnls if p < 0))
    pf = wins_sum / loss_sum if loss_sum > 0 else 999

    return {
        "symbol": symbol,
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "wr": wins / len(trades) * 100,
        "pnl": sum(pnls),
        "dd": max_dd * 100,
        "sharpe": sharpe,
        "avg": avg,
        "pf": pf,
        "final_bal": balance,
    }

# ─── ÇALIŞTIR ──────────────────────────────────────────
print(f"\n{'='*70}")
print(f"SHORT-ONLY BACKTEST — {DAYS} gün, {INTERVAL}, 13 coin")
print(f"{'='*70}")

results = []
total_pnl = 0
total_trades = 0

for sym in SYMBOLS:
    print(f"{sym} çekiliyor...", end=" ", flush=True)
    df = fetch_klines(sym, INTERVAL, DAYS)
    if df is None or len(df) < 60:
        print("VERİ YOK")
        continue
    print(f"{len(df)} mum", end=" → ", flush=True)
    r = run_backtest(sym, df)
    results.append(r)
    icon = "✅" if r["pnl"] > 0 else "❌"
    print(f"${r['pnl']:+.0f} {icon}")

print(f"\n{'='*70}")
print(f"{'Sembol':<12} {'Trade':>5} {'WR%':>5} {'PF':>5} {'PnL':>9} {'DD%':>6} {'Ort/Trade':>9}")
print(f"{'-'*70}")

for r in sorted(results, key=lambda x: x["pnl"], reverse=True):
    if r["trades"] == 0: continue
    icon = "✅" if r["pnl"] > 0 else "❌"
    pf_str = f"{r['pf']:.2f}" if r['pf'] < 99 else "∞"
    print(f"{r['symbol']:<12} {r['trades']:>5} {r['wr']:>4.1f}% {pf_str:>5} "
          f"${r['pnl']:>8.2f} {r['dd']:>5.1f}% ${r['avg']:>8.2f} {icon}")

total_pnl = sum(r["pnl"] for r in results)
total_trades = sum(r["trades"] for r in results)
total_wins = sum(r["wins"] for r in results)
profitable = sum(1 for r in results if r["pnl"] > 0)

all_pnls_win = sum(r["pnl"] for r in results if r["pnl"] > 0)
all_pnls_loss = abs(sum(r["pnl"] for r in results if r["pnl"] < 0))
overall_pf = all_pnls_win / all_pnls_loss if all_pnls_loss > 0 else 999

print(f"{'-'*70}")
print(f"{'TOPLAM':<12} {total_trades:>5} {total_wins/total_trades*100:>4.1f}% {overall_pf:>5.2f} ${total_pnl:>8.2f}")
print(f"Kârlı coin: {profitable}/{len(results)}")
print(f"\n{'='*70}")
print(f"ÖZET:")
print(f"  Toplam Trade:    {total_trades}")
print(f"  Win Rate:        {total_wins/total_trades*100:.1f}%")
print(f"  Profit Factor:   {overall_pf:.2f}")
print(f"  Toplam PnL:      ${total_pnl:,.2f}")
print(f"  Kârlı coin:      {profitable}/{len(results)}")
if overall_pf >= 1.5:
    print(f"\n  ✅ ROADMAP HEDEFİ KARŞILANDI (PF >= 1.5)")
elif overall_pf >= 1.2:
    print(f"\n  ⚠️  İYİ AMA HENÜZ HAZIR DEĞİL (PF hedef: 1.5)")
else:
    print(f"\n  ❌ DAHA ÇALIŞMA GEREKİYOR (PF hedef: 1.5)")
print(f"{'='*70}")