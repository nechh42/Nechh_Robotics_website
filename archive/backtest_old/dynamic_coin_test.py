"""
dynamic_coin_test.py - Dinamik Coin Seçimi A/B Testleri
=========================================================
Plan [12]: Haftalık edge scan → en iyi coin'leri otomatik seç.

Yaklaşım:
  1. Her coin'in 60 günlük performansını haftalık pencerelerle analiz et
  2. "Rolling coin scorer" — son N haftaya göre coin sıralaması
  3. Her hafta TOP-K coin seç → sadece onlarla trade aç
  4. A/B test: sabit coin listesi vs dinamik seçim

Testler:
  - BASELINE: Sabit 15 coin (v15.9)
  - WEEKLY-TOP10: Her hafta son 2 haftanın en iyi 10 coin'ini seç
  - WEEKLY-TOP8: Top 8
  - WEEKLY-TOP12: Top 12
  - ADAPTIVE-DROP: WR<%40 olan coin'leri haftalık drop et
  - MOMENTUM-COINS: Son 2 haftada en çok trade yapan coin'lere odaklan
  - HOTCOLD: Sıcak coinler (son haftada kârlı) bonus, soğuklar penalize

Kullanım:
  python -m backtest.dynamic_coin_test
"""

import sys, os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from strategies.regime import detect_regime
from strategies.indicators import calc_atr, calc_rsi
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.edge_discovery import EdgeDiscoveryStrategy
from engine.voting import combine_signals
from backtest.backtest_v3 import fetch_klines, BTPosition, BTTrade, BacktestV3


# ═════════════════════════════════════════════════════════
# COIN PERFORMANCE ANALYZER
# ═════════════════════════════════════════════════════════

class CoinPerformanceTracker:
    """Her coin'in haftalık performansını takip eder."""

    def __init__(self):
        # coin → [{week, trades, wins, pnl}, ...]
        self.coin_weekly = defaultdict(list)
        self.coin_trades = defaultdict(list)  # coin → [pnl, pnl, ...]

    def record_trade(self, symbol: str, pnl: float, week_num: int):
        self.coin_trades[symbol].append(pnl)
        # Haftalık aggregation
        weekly = self.coin_weekly[symbol]
        if not weekly or weekly[-1]["week"] != week_num:
            weekly.append({"week": week_num, "trades": 0, "wins": 0, "pnl": 0.0})
        weekly[-1]["trades"] += 1
        if pnl > 0:
            weekly[-1]["wins"] += 1
        weekly[-1]["pnl"] += pnl

    def get_top_coins(self, lookback_weeks: int = 2, top_k: int = 10,
                      current_week: int = 0) -> List[str]:
        """Son N haftanın performansına göre en iyi K coin'i seç."""
        scores = {}
        for symbol, weekly_data in self.coin_weekly.items():
            recent = [w for w in weekly_data
                      if w["week"] > current_week - lookback_weeks and w["week"] <= current_week]
            if not recent:
                continue
            total_trades = sum(w["trades"] for w in recent)
            total_wins = sum(w["wins"] for w in recent)
            total_pnl = sum(w["pnl"] for w in recent)
            wr = total_wins / total_trades if total_trades > 0 else 0

            # Score = PnL ağırlıklı (trade sayısı bonus)
            scores[symbol] = total_pnl + (wr - 0.5) * 50 + min(total_trades, 10) * 2

        sorted_coins = sorted(scores.items(), key=lambda x: -x[1])
        return [c[0] for c in sorted_coins[:top_k]]

    def get_active_coins(self, min_wr: float = 0.40, lookback_weeks: int = 2,
                         current_week: int = 0) -> Set[str]:
        """WR >= min_wr olan coin'leri döndür (adaptive drop)."""
        active = set()
        for symbol, weekly_data in self.coin_weekly.items():
            recent = [w for w in weekly_data
                      if w["week"] > current_week - lookback_weeks and w["week"] <= current_week]
            if not recent:
                active.add(symbol)  # Veri yoksa aktif tut
                continue
            total_trades = sum(w["trades"] for w in recent)
            total_wins = sum(w["wins"] for w in recent)
            if total_trades < 3:
                active.add(symbol)
                continue
            wr = total_wins / total_trades
            if wr >= min_wr:
                active.add(symbol)
        return active


# ═════════════════════════════════════════════════════════
# DYNAMIC BACKTEST
# ═════════════════════════════════════════════════════════

class DynamicCoinBacktest(BacktestV3):
    """
    Haftalık dinamik coin seçimi yapan backtest.
    coin_selector: fonksiyon(tracker, week_num) → set of active symbols
    """

    def __init__(self, coin_selector=None, initial_balance=10000.0):
        super().__init__(initial_balance=initial_balance)
        self.coin_selector = coin_selector
        self.tracker = CoinPerformanceTracker()
        self.active_coins = set()
        self._current_week = -1
        self._trades_recorded = 0

    def run(self, symbols=None, days=60, interval="4h"):
        """Override: haftalık coin selection ile walk-forward backtest."""
        symbols = symbols or config.SYMBOLS
        all_symbols = list(symbols)  # Tüm coin'leri fetch et

        # Fetch data
        data_map = {}
        for sym in all_symbols:
            df = fetch_klines(sym, interval, days + 10)
            if df is not None and len(df) >= 50:
                data_map[sym] = df

        if not data_map:
            return self._empty_result(days)

        all_times = set()
        for df in data_map.values():
            all_times.update(df["open_time"].tolist())
        sorted_times = sorted(all_times)

        # İlk 2 hafta: tüm coin'ler aktif (warm-up)
        self.active_coins = set(sym for sym in all_symbols
                                if sym not in getattr(config, 'COIN_BLACKLIST', []))

        # Walk forward
        for t_idx, timestamp in enumerate(sorted_times):
            dt = datetime.fromtimestamp(timestamp / 1000)

            # Hafta değişimi kontrolü
            week_num = dt.isocalendar()[1]
            if week_num != self._current_week:
                self._current_week = week_num
                if self.coin_selector and t_idx > 84:  # 2 hafta warm-up (84 = 14gün×6)
                    self.active_coins = self.coin_selector(self.tracker, week_num)

            # Gün sıfırlama
            if self._current_day != dt.date():
                self._daily_trades = 0
                self._daily_loss = 0.0
                self._current_day = dt.date()

            for sym in list(data_map.keys()):
                df = data_map[sym]
                mask = df["open_time"] <= timestamp
                df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)
                if len(df_window) < 50:
                    continue

                price = df_window["close"].iloc[-1]
                high = df_window["high"].iloc[-1]
                low = df_window["low"].iloc[-1]
                ts_str = str(df_window["timestamp"].iloc[-1])

                # MFE/MAE
                if sym in self.positions:
                    self._update_mfe_mae(sym, high, low)

                # Exits
                if sym in self.positions:
                    self._check_exits(sym, price, high, low, ts_str, df_window)

                # Funding
                if sym in self.positions:
                    self._funding_counter += 1
                    if self._funding_counter >= 2:
                        self._apply_funding(sym, price)
                        self._funding_counter = 0

                # Entry — SADECE aktif coin'lerde
                if sym not in self.positions and sym in self.active_coins:
                    self._evaluate_entry(sym, df_window, price, ts_str)

            # Bu timestamp'teki tüm semboller işlendi — kapanan trade'leri kaydet
            trades_recorded = getattr(self, '_trades_recorded', 0)
            if len(self.trades) > trades_recorded:
                for t in self.trades[trades_recorded:]:
                    self.tracker.record_trade(t.symbol, t.net_pnl, week_num)
                self._trades_recorded = len(self.trades)

            equity = self._calc_equity(data_map, timestamp)
            self.equity_curve.append(equity)

        # Close remaining
        for sym in list(self.positions.keys()):
            if sym in data_map:
                df = data_map[sym]
                last_price = df["close"].iloc[-1]
                last_time = str(df["timestamp"].iloc[-1])
                last_regime = detect_regime(df.tail(100).reset_index(drop=True))
                self._close_position(sym, last_price, last_time, "END_OF_DATA", last_regime)

        from backtest.backtest_v3 import BTResult
        result = BTResult(period=f"{days}d", symbols_tested=all_symbols)
        result = self._calculate_results(result)
        return result

    def _empty_result(self, days):
        from backtest.backtest_v3 import BTResult
        return BTResult(period=f"{days}d")


# ═════════════════════════════════════════════════════════
# COIN SELECTORS
# ═════════════════════════════════════════════════════════

def selector_top10(tracker, week_num):
    """Son 2 haftanın en iyi 10 coin'i."""
    top = tracker.get_top_coins(lookback_weeks=2, top_k=10, current_week=week_num)
    return set(top) if top else _default_coins()

def selector_top8(tracker, week_num):
    top = tracker.get_top_coins(lookback_weeks=2, top_k=8, current_week=week_num)
    return set(top) if top else _default_coins()

def selector_top12(tracker, week_num):
    top = tracker.get_top_coins(lookback_weeks=2, top_k=12, current_week=week_num)
    return set(top) if top else _default_coins()

def selector_adaptive_drop(tracker, week_num):
    """WR<%40 olan coin'leri haftalık drop et."""
    active = tracker.get_active_coins(min_wr=0.40, lookback_weeks=2, current_week=week_num)
    return active if active else _default_coins()

def selector_adaptive_drop_45(tracker, week_num):
    """WR<%45 olan coin'leri haftalık drop et."""
    active = tracker.get_active_coins(min_wr=0.45, lookback_weeks=2, current_week=week_num)
    return active if active else _default_coins()

def selector_top10_3w(tracker, week_num):
    """Son 3 haftanın en iyi 10 coin'i (daha stabil)."""
    top = tracker.get_top_coins(lookback_weeks=3, top_k=10, current_week=week_num)
    return set(top) if top else _default_coins()

def selector_hot_cold(tracker, week_num):
    """Son 1 haftada sıcak olan coin'ler + her zaman BTC/ETH."""
    top = tracker.get_top_coins(lookback_weeks=1, top_k=8, current_week=week_num)
    always_on = {"BTCUSDT", "ETHUSDT", "AVAXUSDT", "DOGEUSDT", "AAVEUSDT"}
    return set(top).union(always_on) if top else _default_coins()

def _default_coins():
    """Fallback: blacklist dışındaki tüm coin'ler."""
    return set(s for s in config.SYMBOLS if s not in config.COIN_BLACKLIST)


# ═════════════════════════════════════════════════════════
# TEST TANIMLARİ
# ═════════════════════════════════════════════════════════

TESTS = {
    "BASELINE-STATIC": None,         # Sabit coin listesi (v15.9)
    "WEEKLY-TOP10": selector_top10,
    "WEEKLY-TOP8": selector_top8,
    "WEEKLY-TOP12": selector_top12,
    "DROP-WR<40": selector_adaptive_drop,
    "DROP-WR<45": selector_adaptive_drop_45,
    "TOP10-3W": selector_top10_3w,
    "HOT-COLD": selector_hot_cold,
}


def calc_stats(result) -> Dict:
    """Backtest result'tan istatistik çıkar."""
    trades = result.trades
    if not trades:
        return {"trades": 0, "wr": 0, "pnl": 0, "pf": 0, "dd": 0}

    pnls = [t.net_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    wr = len(wins) / len(pnls) * 100
    pnl = sum(pnls)
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    pf = gross_win / gross_loss if gross_loss > 0 else 999

    eq = result.equity_curve
    peak = eq[0] if eq else 10000
    max_dd = 0
    for e in eq:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd
    dd_pct = max_dd / 10000 * 100

    return {
        "trades": len(trades),
        "wr": wr,
        "pnl": pnl,
        "pf": pf,
        "dd": dd_pct,
        "avg_win": np.mean(wins) if wins else 0,
        "avg_loss": np.mean(losses) if losses else 0,
    }


# ═════════════════════════════════════════════════════════
# COIN PERFORMANCE DEEP ANALYSIS
# ═════════════════════════════════════════════════════════

def analyze_coin_dynamics(data_map, sorted_times, symbols):
    """
    Coin bazlı haftalık performans analizi.
    Hangi coinler ne zaman iyi/kötü performans gösteriyor?
    """
    print(f"\n{'='*70}")
    print(f"COİN DİNAMİK PERFORMANS ANALİZİ")
    print(f"{'='*70}")

    # Baseline backtest — her coin'in performansını ayrı ayrı görmek için
    bt = BacktestV3()
    result = bt.run(symbols=symbols, days=60)

    # Coin bazlı trade breakdown
    coin_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0,
                                       "time_exits": 0, "partial_tp": 0,
                                       "smart_exits": 0, "stop_losses": 0})

    for t in result.trades:
        cs = coin_stats[t.symbol]
        cs["trades"] += 1
        if t.net_pnl > 0:
            cs["wins"] += 1
        cs["pnl"] += t.net_pnl
        if "TIME-EXIT" in t.reason:
            cs["time_exits"] += 1
        elif "PARTIAL-TP" in t.reason:
            cs["partial_tp"] += 1
        elif "SMART-EXIT" in t.reason:
            cs["smart_exits"] += 1
        elif "STOP-LOSS" in t.reason:
            cs["stop_losses"] += 1

    # Sırala ve göster
    sorted_coins = sorted(coin_stats.items(), key=lambda x: -x[1]["pnl"])

    print(f"\n  {'Coin':12s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'TP1':>3s} | {'Smart':>5s} | {'Time':>4s} | {'SL':>3s}")
    print(f"  {'─'*12}─┼─{'─'*5}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*3}─┼─{'─'*5}─┼─{'─'*4}─┼─{'─'*3}")

    for sym, cs in sorted_coins:
        wr = cs["wins"] / cs["trades"] * 100 if cs["trades"] > 0 else 0
        print(f"  {sym:12s} | {cs['trades']:>5d} | {wr:>5.1f}% | ${cs['pnl']:>+9.2f} | "
              f"{cs['partial_tp']:>3d} | {cs['smart_exits']:>5d} | {cs['time_exits']:>4d} | {cs['stop_losses']:>3d}")

    return coin_stats


# ═════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════

if __name__ == "__main__":
    days = 60
    symbols = config.SYMBOLS

    print(f"\n{'='*70}")
    print(f"DİNAMİK COİN SEÇİMİ A/B TESTLERİ — {len(TESTS)} test")
    print(f"{'='*70}")
    print(f"Days: {days} | Symbols: {len(symbols)} | Active (after BL): "
          f"{len([s for s in symbols if s not in config.COIN_BLACKLIST])}")

    # Run all tests
    results = {}
    for i, (name, selector) in enumerate(TESTS.items()):
        print(f"\n[{i+1}/{len(TESTS)}] {name}...", flush=True)
        bt = DynamicCoinBacktest(coin_selector=selector)
        result = bt.run(symbols=symbols, days=days)
        stats = calc_stats(result)
        results[name] = stats

        if stats["trades"] > 0:
            print(f"  → {stats['trades']} trade | WR={stats['wr']:.1f}% | "
                  f"PnL=${stats['pnl']:+.2f} | PF={stats['pf']:.2f} | MaxDD={stats['dd']:.1f}%")
        else:
            print(f"  → 0 trade")

    # Sonuç tablosu
    baseline = results.get("BASELINE-STATIC", {"trades": 0, "wr": 0, "pnl": 0, "pf": 0, "dd": 0})

    sorted_results = sorted(results.items(), key=lambda x: -x[1]["pnl"])

    print(f"\n{'='*70}")
    print(f"SONUÇ TABLOSU (PnL sırası)")
    print(f"{'='*70}")
    print(f"  {'Test':20s} | {'Trades':>6s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'DD':>5s} | vs BL")
    print(f"  {'─'*20}─┼─{'─'*6}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*8}")

    for name, stats in sorted_results:
        pnl_diff = stats["pnl"] - baseline["pnl"]
        marker = " ★" if stats["pnl"] > baseline["pnl"] and name != "BASELINE-STATIC" else ""
        bl_mark = " (BL)" if name == "BASELINE-STATIC" else ""
        print(f"  {name:20s} | {stats['trades']:>6d} | {stats['wr']:>5.1f}% | ${stats['pnl']:>+9.2f} | "
              f"{stats['pf']:>5.2f} | {stats['dd']:>4.1f}% | ${pnl_diff:>+.0f}{marker}{bl_mark}")

    # Kazananlar
    winners = [(n, s) for n, s in sorted_results
               if s["pnl"] > baseline["pnl"] and n != "BASELINE-STATIC"]

    if winners:
        print(f"\n{'='*70}")
        print(f"KAZANANLAR")
        print(f"{'='*70}")
        for name, stats in winners[:3]:
            pnl_diff = stats["pnl"] - baseline["pnl"]
            wr_diff = stats["wr"] - baseline["wr"]
            print(f"\n  ★ {name}")
            print(f"    PnL: ${stats['pnl']:+.2f} (${pnl_diff:+.2f} vs BL)")
            print(f"    WR:  {stats['wr']:.1f}% ({wr_diff:+.1f}%)")
            print(f"    PF:  {stats['pf']:.2f} | Trades: {stats['trades']}")
    else:
        print(f"\n⚠️  Hiçbir dinamik seçim baseline'ı geçemedi — sabit liste optimal!")

    # === COİN BAZLI DERİN ANALİZ ===
    print(f"\n\n{'='*70}")
    print(f"COİN BAZLI PERFORMANS (BASELINE)")
    print(f"{'='*70}")

    bt_deep = BacktestV3()
    result_deep = bt_deep.run(symbols=symbols, days=days)

    coin_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0})
    for t in result_deep.trades:
        cs = coin_stats[t.symbol]
        cs["trades"] += 1
        if t.net_pnl > 0:
            cs["wins"] += 1
        cs["pnl"] += t.net_pnl

    sorted_coins = sorted(coin_stats.items(), key=lambda x: -x[1]["pnl"])

    print(f"\n  {'Coin':12s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | Değerlendirme")
    print(f"  {'─'*12}─┼─{'─'*5}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*20}")

    for sym, cs in sorted_coins:
        wr = cs["wins"] / cs["trades"] * 100 if cs["trades"] > 0 else 0
        if cs["pnl"] > 50:
            verdict = "★ GÜÇLÜ"
        elif cs["pnl"] > 0:
            verdict = "✓ KÂRLI"
        elif cs["pnl"] > -20:
            verdict = "~ NÖT"
        else:
            verdict = "✗ ZARARDA"
        print(f"  {sym:12s} | {cs['trades']:>5d} | {wr:>5.1f}% | ${cs['pnl']:>+9.2f} | {verdict}")
