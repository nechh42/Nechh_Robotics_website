"""
backtest_with_pretrade.py
=========================
Backtest + Pre_trade filtresi ile çalışır.
Canlı sistemle AYNI kurallar:
  TREND_UP   → sadece LONG
  TREND_DOWN → sadece SHORT
  RANGING    → sadece SHORT
  VOLATILE   → işlem yok

Çalıştır: python backtest_with_pretrade.py
"""

import sys, os, requests, logging
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, r'C:\war_machine')
import config
from strategies.indicators import calc_rsi, calc_ema, calc_bollinger, calc_atr
from strategies.regime import detect_regime
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from engine.voting import combine_signals

logging.basicConfig(level=logging.WARNING)

def fetch_klines(symbol, interval="1h", days=30):
    url = "https://api.binance.com/api/v3/klines"
    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)
    all_data = []
    current = start_ms
    while current < end_ms:
        params = {"symbol": symbol, "interval": interval, "startTime": current, "limit": 1000}
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if not data: break
            all_data.extend(data)
            current = data[-1][0] + 1
        except: break
    if not all_data: return None
    df = pd.DataFrame(all_data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades_count","tbb","tbq","ignore"])
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    return df

def apply_pretrade_filter(action, regime):
    """Canlı sistemle aynı kural"""
    if regime == "VOLATILE": return "NONE"
    if regime == "TREND_UP" and action == "SHORT": return "NONE"
    if regime == "TREND_DOWN" and action == "LONG": return "NONE"
    if regime == "RANGING" and action == "LONG": return "NONE"
    return action

def run_backtest(symbol, interval="1h", days=30, sl_pct=0.015, tp_pct=0.03):
    print(f"\n{'='*50}")
    print(f"{symbol} | {interval} | {days} gün | PRE_TRADE AÇIK")
    print(f"{'='*50}")
    
    df = fetch_klines(symbol, interval, days)
    if df is None or len(df) < 50:
        print("Veri yetersiz")
        return

    rsi_s = RSIReversionStrategy()
    mom_s = MomentumStrategy()
    vwap_s = VWAPReversionStrategy()

    balance = 10000.0
    position = None
    trades = []

    for i in range(50, len(df)):
        window = df.iloc[max(0,i-100):i+1].copy().reset_index(drop=True)
        price = window["close"].iloc[-1]
        ts = str(df["timestamp"].iloc[i])

        if position:
            hit = False
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
                comm = price * position["size"] * 0.001
                net = gross - comm
                balance += net
                trades.append({"pnl": net, "reason": reason, "side": position["side"]})
                position = None

        if position is None:
            regime = detect_regime(window)
            signals = []
            for s in [rsi_s, mom_s, vwap_s]:
                try: signals.append(s.evaluate(window, symbol, regime))
                except: pass
            
            combined = combine_signals(signals, regime)
            
            # PRE_TRADE FİLTRESİ
            action = apply_pretrade_filter(combined.action, regime)
            
            if action in ("LONG", "SHORT"):
                size = (balance * 0.05) / price
                balance -= price * size * 0.001
                sl = price * (1-sl_pct) if action=="LONG" else price * (1+sl_pct)
                tp = price * (1+tp_pct) if action=="LONG" else price * (1-tp_pct)
                position = {"side": action, "entry": price, "size": size, "sl": sl, "tp": tp}

    if not trades:
        print("Trade yok")
        return

    pnls = [t["pnl"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    total = len(pnls)
    
    print(f"Trade:     {total}")
    print(f"Win Rate:  {wins/total*100:.1f}%")
    print(f"Toplam PnL: ${sum(pnls):.2f}")
    print(f"Final:     ${balance:.2f}")
    
    longs = [t for t in trades if t["side"]=="LONG"]
    shorts = [t for t in trades if t["side"]=="SHORT"]
    if longs:
        lw = sum(1 for t in longs if t["pnl"]>0)
        print(f"LONG:  {len(longs)} trade | WR: {lw/len(longs)*100:.0f}% | PnL: ${sum(t['pnl'] for t in longs):.2f}")
    if shorts:
        sw = sum(1 for t in shorts if t["pnl"]>0)
        print(f"SHORT: {len(shorts)} trade | WR: {sw/len(shorts)*100:.0f}% | PnL: ${sum(t['pnl'] for t in shorts):.2f}")

SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT","ATOMUSDT","NEARUSDT","LINKUSDT"]

print("\n" + "="*50)
print("BACKTEST + PRE_TRADE FİLTRESİ (30 gün, 1h)")
print("="*50)

total_pnl = 0
for sym in SYMBOLS:
    run_backtest(sym)

