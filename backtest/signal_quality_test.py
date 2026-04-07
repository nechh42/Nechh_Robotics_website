"""
signal_quality_test.py - Sinyal Kalitesi A/B Testleri
========================================================
ML feature importance'tan türetilen kural tabanlı filtreler.
Top features: volume_ratio, ADX, upper_shadow, ret_10, bb_position

Her test baseline v15.8'e karşı karşılaştırılır.
Kazananlar config.py'a eklenir.

Kullanım:
  python -m backtest.signal_quality_test
"""

import sys, os, copy
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from strategies.regime import detect_regime, _calc_wilder_adx, _calc_volatility_ratio
from strategies.indicators import (
    calc_rsi, calc_atr, calc_ema, calc_bollinger, calc_vwap
)
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.edge_discovery import EdgeDiscoveryStrategy
from engine.voting import combine_signals
from backtest.backtest_v3 import fetch_klines, BTPosition, BTTrade, BacktestV3


class FilteredBacktest(BacktestV3):
    """
    BacktestV3 + configurable pre-trade filters.
    Her filtre entry anında uygulanır.
    """

    def __init__(self, filter_config: Dict = None, **kwargs):
        super().__init__(**kwargs)
        self.fc = filter_config or {}
        self.filtered_count = 0
        self.filter_reasons = {}

    def _evaluate_entry(self, symbol, df, price, timestamp):
        """Override: Filtreleri uygula SONRA entry yap."""
        if len(self.positions) >= config.MAX_POSITIONS:
            return
        if self._daily_trades >= config.MAX_DAILY_TRADES:
            return
        if self._daily_loss >= config.MAX_DAILY_LOSS:
            return

        regime = detect_regime(df)

        if getattr(config, 'TREND_UP_BLOCK', False) and regime == "TREND_UP":
            return
        if symbol in getattr(config, 'COIN_BLACKLIST', []):
            return
        if getattr(config, 'DIP_BUY_FILTER', False) and regime == "RANGING":
            if len(df) >= 2 and df["close"].iloc[-2] >= df["open"].iloc[-2]:
                return

        # Evaluate strategies
        signals = []
        for strat in self.strategies:
            try:
                sig = strat.evaluate(df, symbol, regime)
                if sig.action != "NONE":
                    atr_s = calc_atr(df)
                    sig.atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02
                    sig.price = price
                    signals.append(sig)
            except Exception:
                pass

        if not signals:
            return

        combined = combine_signals(signals, regime)
        if combined.action == "NONE":
            return

        action = combined.action
        if regime == "VOLATILE":
            return
        if action == "LONG" and regime == "TREND_DOWN":
            return
        if action == "SHORT" and not config.ALLOW_SHORT:
            if not (getattr(config, 'ALLOW_SHORT_CONDITIONAL', False) and regime == "TREND_DOWN"):
                return

        # ═══════════════════════════════════════════════════
        # ★ SIGNAL QUALITY FILTERS (burada uygulanır)
        # ═══════════════════════════════════════════════════

        closes = df["close"]
        volumes = df["volume"]
        highs = df["high"]
        lows = df["low"]

        # --- VOLUME RATIO FILTER ---
        min_vol = self.fc.get("min_volume_ratio", 0)
        if min_vol > 0:
            vol_avg = volumes.tail(20).mean()
            vol_cur = volumes.iloc[-1]
            vol_ratio = vol_cur / vol_avg if vol_avg > 0 else 1.0
            if vol_ratio < min_vol:
                self.filtered_count += 1
                self.filter_reasons["volume_low"] = self.filter_reasons.get("volume_low", 0) + 1
                return

        max_vol = self.fc.get("max_volume_ratio", 0)
        if max_vol > 0:
            vol_avg = volumes.tail(20).mean()
            vol_cur = volumes.iloc[-1]
            vol_ratio = vol_cur / vol_avg if vol_avg > 0 else 1.0
            if vol_ratio > max_vol:
                self.filtered_count += 1
                self.filter_reasons["volume_high"] = self.filter_reasons.get("volume_high", 0) + 1
                return

        # --- ADX FILTER ---
        min_adx = self.fc.get("min_adx", 0)
        max_adx = self.fc.get("max_adx", 100)
        if min_adx > 0 or max_adx < 100:
            adx_val, _, _ = _calc_wilder_adx(df)
            if adx_val < min_adx or adx_val > max_adx:
                self.filtered_count += 1
                self.filter_reasons["adx_range"] = self.filter_reasons.get("adx_range", 0) + 1
                return

        # --- UPPER SHADOW FILTER ---
        max_upper_shadow = self.fc.get("max_upper_shadow", 1.0)
        if max_upper_shadow < 1.0:
            candle_range = highs.iloc[-1] - lows.iloc[-1]
            if candle_range > 0:
                if closes.iloc[-1] >= df["open"].iloc[-1]:
                    upper_shadow = highs.iloc[-1] - closes.iloc[-1]
                else:
                    upper_shadow = highs.iloc[-1] - df["open"].iloc[-1]
                shadow_pct = upper_shadow / candle_range
                if shadow_pct > max_upper_shadow:
                    self.filtered_count += 1
                    self.filter_reasons["upper_shadow"] = self.filter_reasons.get("upper_shadow", 0) + 1
                    return

        # --- RETURN MOMENTUM FILTER ---
        min_ret = self.fc.get("min_ret_10", -999)
        max_ret = self.fc.get("max_ret_10", 999)
        if min_ret > -999 or max_ret < 999:
            if len(closes) > 10:
                ret_10 = (closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11] * 100
                if ret_10 < min_ret or ret_10 > max_ret:
                    self.filtered_count += 1
                    self.filter_reasons["ret_10_range"] = self.filter_reasons.get("ret_10_range", 0) + 1
                    return

        # --- BB POSITION FILTER ---
        min_bb = self.fc.get("min_bb_position", -1)
        max_bb = self.fc.get("max_bb_position", 2)
        if min_bb > -1 or max_bb < 2:
            upper, middle, lower, _ = calc_bollinger(closes)
            bb_range = upper.iloc[-1] - lower.iloc[-1]
            if bb_range > 0:
                bb_pos = (price - lower.iloc[-1]) / bb_range
                if bb_pos < min_bb or bb_pos > max_bb:
                    self.filtered_count += 1
                    self.filter_reasons["bb_position"] = self.filter_reasons.get("bb_position", 0) + 1
                    return

        # --- MULTI-STRATEGY AGREEMENT ---
        min_agree = self.fc.get("min_strategies_agree", 1)
        if min_agree > 1:
            long_count = sum(1 for s in signals if s.action == "LONG")
            if long_count < min_agree:
                self.filtered_count += 1
                self.filter_reasons["agreement"] = self.filter_reasons.get("agreement", 0) + 1
                return

        # --- RSI RANGE FILTER ---
        min_rsi = self.fc.get("min_rsi", 0)
        max_rsi = self.fc.get("max_rsi", 100)
        if min_rsi > 0 or max_rsi < 100:
            rsi = calc_rsi(closes)
            rsi_val = rsi.iloc[-1] if not rsi.empty else 50
            if rsi_val < min_rsi or rsi_val > max_rsi:
                self.filtered_count += 1
                self.filter_reasons["rsi_range"] = self.filter_reasons.get("rsi_range", 0) + 1
                return

        # --- EMA TREND FILTER ---
        if self.fc.get("require_ema_bullish", False):
            ema9 = calc_ema(closes, 9).iloc[-1]
            ema21 = calc_ema(closes, 21).iloc[-1]
            if ema9 < ema21:  # Short-term below long-term = bearish
                self.filtered_count += 1
                self.filter_reasons["ema_bearish"] = self.filter_reasons.get("ema_bearish", 0) + 1
                return

        # --- VOLUME TREND FILTER ---
        min_vol_trend = self.fc.get("min_volume_trend", 0)
        if min_vol_trend > 0:
            vol_5 = volumes.tail(5).mean()
            vol_20 = volumes.tail(20).mean()
            vol_trend = vol_5 / vol_20 if vol_20 > 0 else 1.0
            if vol_trend < min_vol_trend:
                self.filtered_count += 1
                self.filter_reasons["vol_trend"] = self.filter_reasons.get("vol_trend", 0) + 1
                return

        # ═══════════════════════════════════════════════════
        # FILTERS PASSED → proceed with normal entry
        # ═══════════════════════════════════════════════════

        atr_s = calc_atr(df)
        atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02

        rr = config.DYNAMIC_RR.get(regime, {"sl": 1.5, "tp": 3.0})
        sl_dist = atr * rr["sl"]
        tp_dist = atr * rr["tp"]

        min_sl = price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        if action == "LONG":
            sl = price - sl_dist
            tp = price + tp_dist
            tp1 = price + tp_dist * config.PARTIAL_TP_RATIO
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            tp1 = price - tp_dist * config.PARTIAL_TP_RATIO

        risk_amount = self.balance * config.RISK_BASE_PCT
        size_by_risk = risk_amount / sl_dist
        size_by_notional = (self.balance * 0.10) / price
        size = min(size_by_risk, size_by_notional)
        if regime == "RANGING":
            size *= 0.50
        if size < 0.0001:
            return

        entry_comm = price * size * config.COMMISSION_RATE
        self.balance -= entry_comm

        self.positions[symbol] = BTPosition(
            symbol=symbol, side=action, entry_price=price,
            size=size, stop_loss=sl, take_profit=tp,
            take_profit_1=tp1, entry_time=timestamp,
            strategy=combined.strategy, entry_regime=regime,
            original_entry_regime=regime,
            entry_atr=atr, max_favorable=price, max_adverse=price,
        )
        self._daily_trades += 1


def run_test(name: str, filter_config: Dict, data_map: Dict,
             sorted_times: List, symbols: List) -> Dict:
    """Tek bir filtre testi çalıştır."""
    bt = FilteredBacktest(filter_config=filter_config)
    bt.balance = 10000.0

    for timestamp in sorted_times:
        dt = datetime.fromtimestamp(timestamp / 1000)
        if bt._current_day != dt.date():
            bt._daily_trades = 0
            bt._daily_loss = 0.0
            bt._current_day = dt.date()

        for sym in symbols:
            if sym not in data_map:
                continue
            df = data_map[sym]
            mask = df["open_time"] <= timestamp
            df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)
            if len(df_window) < 50:
                continue

            price = df_window["close"].iloc[-1]
            high = df_window["high"].iloc[-1]
            low = df_window["low"].iloc[-1]
            ts_str = str(df_window["timestamp"].iloc[-1])

            if sym in bt.positions:
                bt._update_mfe_mae(sym, high, low)
            if sym in bt.positions:
                bt._check_exits(sym, price, high, low, ts_str, df_window)
            if sym in bt.positions:
                bt._funding_counter += 1
                if bt._funding_counter >= 2:
                    bt._apply_funding(sym, price)
                    bt._funding_counter = 0
            if sym not in bt.positions:
                bt._evaluate_entry(sym, df_window, price, ts_str)

        equity = bt._calc_equity(data_map, timestamp)
        bt.equity_curve.append(equity)

    # Close remaining
    for sym in list(bt.positions.keys()):
        if sym in data_map:
            df = data_map[sym]
            last_price = df["close"].iloc[-1]
            last_time = str(df["timestamp"].iloc[-1])
            last_regime = detect_regime(df.tail(100).reset_index(drop=True))
            bt._close_position(sym, last_price, last_time, "END_OF_DATA", last_regime)

    trades = bt.trades
    if not trades:
        return {"name": name, "trades": 0, "wr": 0, "pnl": 0, "pf": 0, "dd": 0, "filtered": bt.filtered_count}

    pnls = [t.net_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    wr = len(wins) / len(pnls) * 100
    pnl = sum(pnls)
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    pf = gross_win / gross_loss if gross_loss > 0 else 999

    # Max drawdown
    eq = bt.equity_curve
    peak = eq[0]
    max_dd = 0
    for e in eq:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dd:
            max_dd = dd
    dd_pct = max_dd / 10000 * 100

    return {
        "name": name,
        "trades": len(trades),
        "wr": wr,
        "pnl": pnl,
        "pf": pf,
        "dd": dd_pct,
        "filtered": bt.filtered_count,
        "filter_reasons": bt.filter_reasons,
        "avg_win": np.mean(wins) if wins else 0,
        "avg_loss": np.mean(losses) if losses else 0,
    }


# ═════════════════════════════════════════════════════════
# TEST TANIMLARİ
# ═════════════════════════════════════════════════════════

TESTS = {
    # === BASELINE ===
    "BASELINE": {},

    # === VOLUME FILTERS ===
    "VOL>0.7": {"min_volume_ratio": 0.7},
    "VOL>0.8": {"min_volume_ratio": 0.8},
    "VOL>1.0": {"min_volume_ratio": 1.0},
    "VOL<3.0": {"max_volume_ratio": 3.0},

    # === ADX FILTERS ===
    "ADX>15": {"min_adx": 15},
    "ADX>20": {"min_adx": 20},
    "ADX<40": {"max_adx": 40},
    "ADX:15-40": {"min_adx": 15, "max_adx": 40},

    # === UPPER SHADOW ===
    "SHADOW<0.5": {"max_upper_shadow": 0.50},
    "SHADOW<0.4": {"max_upper_shadow": 0.40},
    "SHADOW<0.3": {"max_upper_shadow": 0.30},

    # === RETURN MOMENTUM ===
    "RET10>-5": {"min_ret_10": -5.0},
    "RET10>-3": {"min_ret_10": -3.0},
    "RET10:-5/+10": {"min_ret_10": -5.0, "max_ret_10": 10.0},

    # === BB POSITION ===
    "BB<0.7": {"max_bb_position": 0.70},
    "BB:0.1-0.8": {"min_bb_position": 0.10, "max_bb_position": 0.80},
    "BB<0.6": {"max_bb_position": 0.60},

    # === MULTI-STRATEGY AGREEMENT ===
    "AGREE≥2": {"min_strategies_agree": 2},

    # === RSI RANGE ===
    "RSI:25-65": {"min_rsi": 25, "max_rsi": 65},
    "RSI:30-60": {"min_rsi": 30, "max_rsi": 60},
    "RSI<55": {"max_rsi": 55},

    # === EMA TREND ===
    "EMA_BULL": {"require_ema_bullish": True},

    # === VOLUME TREND ===
    "VOLTREND>0.8": {"min_volume_trend": 0.8},
    "VOLTREND>1.0": {"min_volume_trend": 1.0},
}


if __name__ == "__main__":
    days = 60
    symbols = config.SYMBOLS

    print(f"\n{'='*70}")
    print(f"SİNYAL KALİTESİ A/B TESTLERİ — {len(TESTS)} test")
    print(f"{'='*70}")
    print(f"Days: {days} | Symbols: {len(symbols)}")

    # Fetch data once
    data_map = {}
    for sym in symbols:
        print(f"  {sym}...", end=" ", flush=True)
        df = fetch_klines(sym, "4h", days + 10)
        if df is not None and len(df) >= 50:
            data_map[sym] = df
            print(f"{len(df)} ✓")
        else:
            print("SKIP")

    all_times = set()
    for df in data_map.values():
        all_times.update(df["open_time"].tolist())
    sorted_times = sorted(all_times)
    active_symbols = list(data_map.keys())

    print(f"\nVeri hazır. {len(sorted_times)} zaman dilimi, {len(active_symbols)} coin")
    print(f"\n{'─'*70}")

    # Run all tests
    results = []
    for i, (name, fc) in enumerate(TESTS.items()):
        print(f"[{i+1:2d}/{len(TESTS)}] {name:20s}...", end=" ", flush=True)
        r = run_test(name, fc, data_map, sorted_times, active_symbols)
        results.append(r)
        if r["trades"] > 0:
            print(f"{r['trades']:4d} trade | WR={r['wr']:5.1f}% | PnL=${r['pnl']:>+8.2f} | "
                  f"PF={r['pf']:.2f} | DD={r['dd']:.1f}% | Filtered={r['filtered']}")
        else:
            print("0 trade (tümü filtrelendi)")

    # Sort by PnL
    results.sort(key=lambda x: -x["pnl"])

    baseline = next(r for r in results if r["name"] == "BASELINE")

    print(f"\n{'='*70}")
    print(f"SONUÇ TABLOSU (PnL sırası)")
    print(f"{'='*70}")
    print(f"  {'Test':20s} | {'Trades':>6s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'DD':>5s} | {'Filt':>5s} | vs BL")
    print(f"  {'─'*20}─┼─{'─'*6}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*6}")

    for r in results:
        pnl_diff = r["pnl"] - baseline["pnl"]
        marker = " ★" if r["pnl"] > baseline["pnl"] and r["name"] != "BASELINE" else ""
        bl_mark = " (BL)" if r["name"] == "BASELINE" else ""
        print(f"  {r['name']:20s} | {r['trades']:>6d} | {r['wr']:>5.1f}% | ${r['pnl']:>+9.2f} | "
              f"{r['pf']:>5.2f} | {r['dd']:>4.1f}% | {r['filtered']:>5d} | ${pnl_diff:>+.0f}{marker}{bl_mark}")

    # Identify winners
    winners = [r for r in results if r["pnl"] > baseline["pnl"] and r["name"] != "BASELINE"]

    if winners:
        print(f"\n{'='*70}")
        print(f"KAZANANLAR (Baseline'ı geçenler)")
        print(f"{'='*70}")
        for r in winners[:5]:
            pnl_diff = r["pnl"] - baseline["pnl"]
            wr_diff = r["wr"] - baseline["wr"]
            print(f"\n  ★ {r['name']}")
            print(f"    PnL: ${r['pnl']:+.2f} (${pnl_diff:+.2f} vs BL)")
            print(f"    WR:  {r['wr']:.1f}% ({wr_diff:+.1f}% vs BL)")
            print(f"    PF:  {r['pf']:.2f} | Trades: {r['trades']} | Filtered: {r['filtered']}")
            if r.get("filter_reasons"):
                print(f"    Filtre nedenleri: {r['filter_reasons']}")
    else:
        print(f"\n⚠️  Hiçbir filtre baseline'ı geçemedi!")

    # === COMBO TESTS ===
    if winners:
        print(f"\n{'='*70}")
        print(f"KOMBİNASYON TESTLERİ (En iyi filtreleri birleştir)")
        print(f"{'='*70}")

        # Take top 3 winners and combine
        top_winners = winners[:3]
        combo_tests = {}

        # Merge all top winner configs
        combo1 = {}
        for w in top_winners:
            combo1.update(TESTS[w["name"]])
        combo_name = "+".join(w["name"] for w in top_winners[:3])
        combo_tests[f"COMBO:{combo_name}"] = combo1

        # Pairwise combos
        if len(top_winners) >= 2:
            for i in range(min(3, len(top_winners))):
                for j in range(i+1, min(3, len(top_winners))):
                    cfg = {}
                    cfg.update(TESTS[top_winners[i]["name"]])
                    cfg.update(TESTS[top_winners[j]["name"]])
                    cname = f"COMBO:{top_winners[i]['name']}+{top_winners[j]['name']}"
                    combo_tests[cname] = cfg

        combo_results = []
        for cname, cfg in combo_tests.items():
            print(f"  {cname:40s}...", end=" ", flush=True)
            r = run_test(cname, cfg, data_map, sorted_times, active_symbols)
            combo_results.append(r)
            if r["trades"] > 0:
                pnl_diff = r["pnl"] - baseline["pnl"]
                print(f"{r['trades']:4d} | WR={r['wr']:5.1f}% | ${r['pnl']:>+8.2f} | "
                      f"PF={r['pf']:.2f} | ${pnl_diff:>+.0f} vs BL")
            else:
                print("0 trade")

        # Best overall
        all_results = results + combo_results
        all_results.sort(key=lambda x: -x["pnl"])
        best = all_results[0]

        print(f"\n{'='*70}")
        print(f"EN İYİ SONUÇ: {best['name']}")
        print(f"{'='*70}")
        print(f"  Trades: {best['trades']}")
        print(f"  WR:     {best['wr']:.1f}%")
        print(f"  PnL:    ${best['pnl']:+.2f}")
        print(f"  PF:     {best['pf']:.2f}")
        print(f"  MaxDD:  {best['dd']:.1f}%")
        pnl_diff = best["pnl"] - baseline["pnl"]
        wr_diff = best["wr"] - baseline["wr"]
        print(f"  vs BL:  PnL ${pnl_diff:+.2f} | WR {wr_diff:+.1f}%")
