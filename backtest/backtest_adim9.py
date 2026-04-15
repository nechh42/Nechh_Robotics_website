"""
backtest_adim9.py — ADIM 9 İyileştirme Testleri
==================================================
3 iyileştirmeyi mevcut BASELINE ile karşılaştırır:
  1. Coin filtreleme (BTC/ETH çıkar, kalan 6 coin)
  2. Trailing stop (breakeven + trail)
  3. İkisi birden

Kullanım:
    python -m backtest.backtest_adim9
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
# Veri İndirme (cache ile)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_candles(symbol: str, interval: str, days: int) -> pd.DataFrame:
    cache_file = os.path.join(CACHE_DIR, f"{symbol}_{interval}_{days}d.parquet")
    if os.path.exists(cache_file):
        age = datetime.now().timestamp() - os.path.getmtime(cache_file)
        if age < 3600:  # 1 saat cache
            return pd.read_parquet(cache_file)

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

    df.to_parquet(cache_file)
    return df


@dataclass
class Trade:
    symbol: str
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    size: float
    atr: float = 0.0
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    pnl: float = 0.0
    hold_candles: int = 0
    signal_reason: str = ""


def run_backtest(symbol: str, df: pd.DataFrame, strategy: ComboV1Strategy,
                 sl_mult=1.0, tp_mult=1.0, max_hold=1,
                 breakeven_atr=0, trail_activate_atr=0, trail_distance_atr=0.5) -> List[Trade]:
    """
    Backtest with optional breakeven + trailing stop.
    
    breakeven_atr: ATR trigger for moving SL to entry (0=disabled)
    trail_activate_atr: ATR trigger for starting trailing (0=disabled)
    trail_distance_atr: Trailing distance in ATR multiples
    """
    trades = []
    open_trade = None
    hold_count = 0
    lookback = 100
    trail_active = False
    trail_peak = 0.0

    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i + 1].copy().reset_index(drop=True)
        current = df.iloc[i]
        price = current["close"]
        high = current["high"]
        low = current["low"]

        if open_trade is not None:
            hold_count += 1

            # Breakeven: fiyat breakeven_atr×ATR kâra geçtiyse SL → entry
            if breakeven_atr > 0 and open_trade.atr > 0:
                be_price = open_trade.entry_price + open_trade.atr * breakeven_atr
                if high >= be_price and open_trade.stop_loss < open_trade.entry_price:
                    open_trade.stop_loss = open_trade.entry_price

            # Trailing stop activation
            if trail_activate_atr > 0 and not trail_active and open_trade.atr > 0:
                activate_price = open_trade.entry_price + open_trade.atr * trail_activate_atr
                if high >= activate_price:
                    trail_active = True
                    trail_peak = high

            # Trailing stop update
            if trail_active:
                if high > trail_peak:
                    trail_peak = high
                trail_sl = trail_peak - open_trade.atr * trail_distance_atr
                if trail_sl > open_trade.stop_loss:
                    open_trade.stop_loss = trail_sl

            # Check SL
            if low <= open_trade.stop_loss:
                open_trade.exit_price = open_trade.stop_loss
                open_trade.exit_reason = "STOP-LOSS"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                trail_active = False
                trail_peak = 0.0
                continue

            # Check TP
            if high >= open_trade.take_profit:
                open_trade.exit_price = open_trade.take_profit
                open_trade.exit_reason = "TAKE-PROFIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                trail_active = False
                trail_peak = 0.0
                continue

            # Time exit
            if hold_count >= max_hold:
                open_trade.exit_price = price
                open_trade.exit_reason = "TIME-EXIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                trail_active = False
                trail_peak = 0.0
                continue
            continue

        # Entry logic
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
            size=size, atr=atr, signal_reason=signal.reason,
        )
        hold_count = 0
        trail_active = False
        trail_peak = 0.0

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


def calc_stats(trades: List[Trade]) -> dict:
    if not trades:
        return {"count": 0, "pnl": 0, "pf": 0, "wr": 0, "dd": 0}
    
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

    # Coin kırılımı
    coin_stats = {}
    for t in trades:
        if t.symbol not in coin_stats:
            coin_stats[t.symbol] = {"c": 0, "pnl": 0.0, "wins": 0}
        coin_stats[t.symbol]["c"] += 1
        coin_stats[t.symbol]["pnl"] += t.pnl
        if t.pnl > 0:
            coin_stats[t.symbol]["wins"] += 1

    # Exit reason kırılımı
    exit_stats = {}
    for t in trades:
        r = t.exit_reason
        if r not in exit_stats:
            exit_stats[r] = {"c": 0, "pnl": 0.0}
        exit_stats[r]["c"] += 1
        exit_stats[r]["pnl"] += t.pnl

    return {
        "count": len(trades), "pnl": total, "pf": pf, "wr": wr, "dd": dd,
        "gp": gp, "gl": gl, "coins": coin_stats, "exits": exit_stats,
        "avg_win": gp/len(winners) if winners else 0,
        "avg_loss": gl/len(losers) if losers else 0,
    }


def print_result(label: str, stats: dict):
    if stats["count"] == 0:
        print(f"  {label}: HİÇ TRADE YOK")
        return
    
    status = "✅" if stats["pf"] >= 1.0 else "❌"
    print(f"\n  {status} {label}")
    print(f"     Trade: {stats['count']} | WR: {stats['wr']:.1f}% | PnL: ${stats['pnl']:+.2f} | PF: {stats['pf']:.2f} | DD: ${stats['dd']:.2f}")
    print(f"     Ort.Kazanç: ${stats['avg_win']:.2f} | Ort.Kayıp: ${stats['avg_loss']:.2f}")
    
    if stats.get("exits"):
        parts = []
        for r in sorted(stats["exits"], key=lambda x: stats["exits"][x]["pnl"], reverse=True):
            e = stats["exits"][r]
            parts.append(f"{r}:{e['c']}(${e['pnl']:+.1f})")
        print(f"     Çıkış: {' | '.join(parts)}")

    if stats.get("coins"):
        parts = []
        for sym in sorted(stats["coins"], key=lambda x: stats["coins"][x]["pnl"], reverse=True):
            s = stats["coins"][sym]
            parts.append(f"{sym.replace('USDT','')}: {s['c']}t ${s['pnl']:+.1f}")
        print(f"     Coin:  {' | '.join(parts)}")


def main():
    print("=" * 70)
    print("  ADIM 9: İYİLEŞTİRME TESTLERİ")
    print("=" * 70)

    strategy = ComboV1Strategy()

    # Coin grupları
    ALL_COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                 "AVAXUSDT", "DOGEUSDT", "DOTUSDT"]
    # Filtre: BTC/ETH çıkar (paper'da 0 trade), BNB çıkar (paper'da zarar)
    FILTERED_COINS = ["SOLUSDT", "XRPUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT"]
    # Sadece kazananlar (paper data'dan)
    WINNERS_ONLY = ["XRPUSDT", "AVAXUSDT", "DOGEUSDT"]

    for days in [60, 90]:
        print(f"\n{'#'*70}")
        print(f"  VERİ PERİYODU: {days} GÜN")
        print(f"{'#'*70}")

        # Veri indir (cache ile)
        data_all = {}
        for sym in ALL_COINS:
            print(f"  📥 {sym}...", end=" ", flush=True)
            df = fetch_candles(sym, "4h", days)
            if df.empty or len(df) < 120:
                print("ATLA")
                continue
            print(f"{len(df)} mum ✓")
            data_all[sym] = df

        # ━━━━ TEST 1: BASELINE (mevcut ayarlar) ━━━━
        print(f"\n{'─'*70}")
        print(f"  TEST GRUBU: SL=1.0 TP=1.0 HOLD=1")
        print(f"{'─'*70}")
        
        # 1A: Tüm coinler, mevcut ayarlar
        all_trades = []
        for sym, df in data_all.items():
            trades = run_backtest(sym, df, strategy, sl_mult=1.0, tp_mult=1.0, max_hold=1)
            all_trades.extend(trades)
        s1a = calc_stats(all_trades)
        print_result("BASELINE (8 coin, SL=1×ATR, TP=1×ATR)", s1a)

        # 1B: Filtrelenmiş coinler
        filt_trades = []
        for sym in FILTERED_COINS:
            if sym in data_all:
                trades = run_backtest(sym, data_all[sym], strategy, sl_mult=1.0, tp_mult=1.0, max_hold=1)
                filt_trades.extend(trades)
        s1b = calc_stats(filt_trades)
        print_result("COİN FİLTRE (BTC/ETH/BNB çıktı, 5 coin)", s1b)

        # 1C: Sadece kazananlar
        win_trades = []
        for sym in WINNERS_ONLY:
            if sym in data_all:
                trades = run_backtest(sym, data_all[sym], strategy, sl_mult=1.0, tp_mult=1.0, max_hold=1)
                win_trades.extend(trades)
        s1c = calc_stats(win_trades)
        print_result("WINNERS (XRP+AVAX+DOGE, 3 coin)", s1c)

        # ━━━━ TEST 2: TRAİLİNG STOP VARYASYONLARI ━━━━
        print(f"\n{'─'*70}")
        print(f"  TEST GRUBU: TRAİLİNG STOP + BREAKEVEN")
        print(f"{'─'*70}")

        trail_configs = [
            {"label": "BE=0.5ATR + TRAIL(1.0ATR, 0.5ATR dist)", "be": 0.5, "ta": 1.0, "td": 0.5},
            {"label": "BE=0.5ATR + TRAIL(0.7ATR, 0.3ATR dist)", "be": 0.5, "ta": 0.7, "td": 0.3},
            {"label": "BE=0.7ATR + TRAIL(1.0ATR, 0.5ATR dist)", "be": 0.7, "ta": 1.0, "td": 0.5},
            {"label": "SadeceBE=0.5ATR (trail yok)", "be": 0.5, "ta": 0, "td": 0},
            # TP artırarak trail ile birlikte
            {"label": "TP=1.5ATR + BE=0.5 + TRAIL(1.0,0.5)", "be": 0.5, "ta": 1.0, "td": 0.5, "tp": 1.5},
            {"label": "TP=2.0ATR + BE=0.5 + TRAIL(1.0,0.5)", "be": 0.5, "ta": 1.0, "td": 0.5, "tp": 2.0},
        ]

        for tc in trail_configs:
            tp_m = tc.get("tp", 1.0)
            t_trades = []
            for sym in FILTERED_COINS:
                if sym in data_all:
                    trades = run_backtest(
                        sym, data_all[sym], strategy,
                        sl_mult=1.0, tp_mult=tp_m, max_hold=2,  # trail ile max_hold=2
                        breakeven_atr=tc["be"],
                        trail_activate_atr=tc["ta"],
                        trail_distance_atr=tc["td"]
                    )
                    t_trades.extend(trades)
            s = calc_stats(t_trades)
            print_result(tc["label"], s)

        # ━━━━ TEST 3: HOLD SÜRESİ TESTİ ━━━━
        print(f"\n{'─'*70}")
        print(f"  TEST GRUBU: MAX HOLD KARŞILAŞTIRMASI")
        print(f"{'─'*70}")

        for hold in [1, 2, 3]:
            h_trades = []
            for sym in FILTERED_COINS:
                if sym in data_all:
                    trades = run_backtest(sym, data_all[sym], strategy,
                                        sl_mult=1.0, tp_mult=1.0, max_hold=hold)
                    h_trades.extend(trades)
            s = calc_stats(h_trades)
            print_result(f"HOLD={hold} candle (filtrelenmiş coinler)", s)

    print(f"\n{'='*70}")
    print(f"  TEST TAMAMLANDI")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
