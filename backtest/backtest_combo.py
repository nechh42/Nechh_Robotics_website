"""
backtest_combo.py — Combo V1 Strateji Backtest (birleşik 4 kazanan)
=====================================================================
VWAP Reversion + EMA Pullback + Bollinger Bounce + Mean Reversion

60 gün (IS) + 90 gün (OOS dahil) testleri çalıştırır.

Kullanım:
    python -m backtest.backtest_combo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import requests

import config
from strategies.combo_v1 import ComboV1Strategy
from strategies.regime import detect_regime

logging.basicConfig(level=logging.WARNING, format="%(message)s")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Veri İndirme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_candles(symbol: str, interval: str, days: int) -> pd.DataFrame:
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
    return df


@dataclass
class Trade:
    symbol: str
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    size: float
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    pnl: float = 0.0
    hold_candles: int = 0
    signal_reason: str = ""


def run_backtest(symbol: str, df: pd.DataFrame, strategy: ComboV1Strategy,
                 sl_mult=1.0, tp_mult=1.0, max_hold=1) -> List[Trade]:
    trades = []
    open_trade = None
    hold_count = 0
    lookback = 100

    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i + 1].copy().reset_index(drop=True)
        current = df.iloc[i]
        price = current["close"]
        high = current["high"]
        low = current["low"]

        if open_trade is not None:
            hold_count += 1

            if low <= open_trade.stop_loss:
                open_trade.exit_price = open_trade.stop_loss
                open_trade.exit_reason = "STOP-LOSS"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue

            if high >= open_trade.take_profit:
                open_trade.exit_price = open_trade.take_profit
                open_trade.exit_reason = "TAKE-PROFIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue

            if hold_count >= max_hold:
                open_trade.exit_price = price
                open_trade.exit_reason = "TIME-EXIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue
            continue

        regime = detect_regime(window)
        if regime in ("TREND_DOWN", "VOLATILE"):
            continue

        signal = strategy.evaluate(window, symbol, regime)
        if signal.action != "LONG":
            continue
        if signal.confidence < 0.55:
            continue

        atr = signal.atr
        sl_dist = atr * sl_mult
        tp_dist = atr * tp_mult
        min_sl = signal.price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        equity = 10000.0
        risk_amount = equity * 0.005
        size = min(risk_amount / sl_dist, (equity * 0.10) / signal.price)

        open_trade = Trade(
            symbol=symbol, entry_price=signal.price,
            entry_time=current["time"],
            stop_loss=signal.price - sl_dist,
            take_profit=signal.price + tp_dist,
            size=size, signal_reason=signal.reason,
        )
        hold_count = 0

    if open_trade:
        last = df.iloc[-1]
        open_trade.exit_price = last["close"]
        open_trade.exit_reason = "END"
        open_trade.hold_candles = hold_count
        open_trade.pnl = _pnl(open_trade)
        trades.append(open_trade)

    return trades


def _pnl(t: Trade) -> float:
    gross = (t.exit_price - t.entry_price) * t.size
    comm = t.entry_price * t.size * 0.001 * 2
    return gross - comm


def print_report(trades: List[Trade], label: str, days: int):
    if not trades:
        print(f"\n  ❌ {label}: HİÇ TRADE YOK")
        return {}

    total = sum(t.pnl for t in trades)
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]
    wr = len(winners) / len(trades) * 100
    gp = sum(t.pnl for t in winners) if winners else 0
    gl = abs(sum(t.pnl for t in losers)) if losers else 0.001
    pf = gp / gl

    cum = peak = dd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_time):
        cum += t.pnl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)

    exit_stats = {}
    for t in trades:
        r = t.exit_reason
        if r not in exit_stats:
            exit_stats[r] = {"c": 0, "pnl": 0.0}
        exit_stats[r]["c"] += 1
        exit_stats[r]["pnl"] += t.pnl

    # Hangi alt-strateji ne kadar?
    sub_stats = {}
    for t in trades:
        key = t.signal_reason.split(":")[0] if t.signal_reason else "?"
        if key not in sub_stats:
            sub_stats[key] = {"c": 0, "pnl": 0.0, "wins": 0}
        sub_stats[key]["c"] += 1
        sub_stats[key]["pnl"] += t.pnl
        if t.pnl > 0:
            sub_stats[key]["wins"] += 1

    coin_stats = {}
    for t in trades:
        if t.symbol not in coin_stats:
            coin_stats[t.symbol] = {"c": 0, "pnl": 0.0, "wins": 0}
        coin_stats[t.symbol]["c"] += 1
        coin_stats[t.symbol]["pnl"] += t.pnl
        if t.pnl > 0:
            coin_stats[t.symbol]["wins"] += 1

    print(f"\n{'='*65}")
    print(f"  {label} — {days} GÜN")
    print(f"{'='*65}")
    print(f"  Trade: {len(trades)} | Kazanan: {len(winners)} ({wr:.1f}%) | Kaybeden: {len(losers)}")
    print(f"  PnL: ${total:+.2f} | PF: {pf:.2f} | MaxDD: ${dd:.2f}")
    print(f"  Ort.Kazanç: ${gp/len(winners):.2f}" if winners else "  Ort.Kazanç: $0")
    print(f"  Ort.Kayıp: ${gl/len(losers):.2f}" if losers else "  Ort.Kayıp: $0")

    print(f"\n  Çıkış nedenleri:")
    for r in sorted(exit_stats, key=lambda x: exit_stats[x]["pnl"], reverse=True):
        e = exit_stats[r]
        print(f"    {r:15s}: {e['c']:3d} trade | ${e['pnl']:+8.2f}")

    print(f"\n  Alt strateji kırılımı:")
    for k in sorted(sub_stats, key=lambda x: sub_stats[x]["pnl"], reverse=True):
        s = sub_stats[k]
        swr = s["wins"]/s["c"]*100 if s["c"] > 0 else 0
        print(f"    {k:12s}: {s['c']:3d} trade | WR={swr:5.1f}% | ${s['pnl']:+8.2f}")

    print(f"\n  Coin bazlı:")
    for sym in sorted(coin_stats, key=lambda x: coin_stats[x]["pnl"], reverse=True):
        s = coin_stats[sym]
        swr = s["wins"]/s["c"]*100 if s["c"] > 0 else 0
        print(f"    {sym:12s}: {s['c']:3d} trade | WR={swr:5.1f}% | ${s['pnl']:+8.2f}")

    print(f"{'='*65}")

    status = "✅ GEÇTİ" if pf >= 1.0 and wr >= 45 else "❌ KALDI"
    print(f"\n  📊 KARAR: {status} — PF={pf:.2f}, WR={wr:.1f}%")

    return {"count": len(trades), "wr": wr, "pnl": total, "pf": pf, "dd": dd}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    symbols = config.SYMBOLS
    strategy = ComboV1Strategy()

    # Test parametreleri — tüm varyasyonlar
    configs = [
        {"label": "COMBO SL=1.0 TP=1.0 HOLD=1", "sl": 1.0, "tp": 1.0, "hold": 1},
        {"label": "COMBO SL=1.0 TP=1.0 HOLD=2", "sl": 1.0, "tp": 1.0, "hold": 2},
        {"label": "COMBO SL=1.0 TP=1.2 HOLD=2", "sl": 1.0, "tp": 1.2, "hold": 2},
        {"label": "COMBO SL=1.0 TP=1.5 HOLD=3", "sl": 1.0, "tp": 1.5, "hold": 3},
        {"label": "COMBO SL=0.8 TP=1.0 HOLD=2", "sl": 0.8, "tp": 1.0, "hold": 2},
    ]

    # Her periyot için
    for days in [args.days, 90, 120]:
        print(f"\n{'#'*65}")
        print(f"  VERİ PERİYODU: {days} GÜN")
        print(f"{'#'*65}")

        print(f"\n  📥 Veri indiriliyor ({days} gün)...")
        data = {}
        for sym in symbols:
            print(f"     {sym}...", end=" ", flush=True)
            df = fetch_candles(sym, "4h", days)
            if df.empty or len(df) < 120:
                print(f"ATLA")
                continue
            print(f"{len(df)} mum ✓")
            data[sym] = df

        for cfg in configs:
            all_trades = []
            for sym, df in data.items():
                trades = run_backtest(sym, df, strategy,
                                      sl_mult=cfg["sl"], tp_mult=cfg["tp"],
                                      max_hold=cfg["hold"])
                all_trades.extend(trades)

            print_report(all_trades, cfg["label"], days)

    # Sonuçları dosyaya kaydet
    print(f"\n  📄 Test tamamlandı!")


if __name__ == "__main__":
    main()
