"""
time_exit_optimize.py — TIME-EXIT kayıplarını azaltma testleri
================================================================
Mevcut sorun: 238 TIME-EXIT trade, -$936 kayıp (%37.8 WR)
Bu trade'lerin 59'u MFE≥0.5% (kârdaydı ama döndü)

Test stratejileri:
  1. Akıllı time-exit: sadece zarardaysa kapat, kârdaysa devam et
  2. Time-exit'te kârlıysa TP1'e kaydır (partial close)
  3. MAX_HOLD=2 yerine candle bazlı SL sıkılaştırma
  4. FLOWUSDT blacklist (en kötü time-exit coin)
  5. Daha agresif breakeven (0.7 → 0.6)
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from backtest.backtest_v3 import BacktestV3

def run_and_collect(name):
    bt = BacktestV3()
    r = bt.run(days=60)
    return (name, r)

tests = []

# Baseline (v15.7)
print("\n=== BASELINE v15.7 ===")
tests.append(run_and_collect("BASELINE"))

# Test 1: FLOWUSDT blacklist (en çok time-exit kaybeden coin)
print("\n=== Test 1: +FLOWUSDT blacklist ===")
old_bl = config.COIN_BLACKLIST.copy()
config.COIN_BLACKLIST = old_bl + ["FLOWUSDT"]
tests.append(run_and_collect("+BL:FLOW"))
config.COIN_BLACKLIST = old_bl

# Test 2: BREAKEVEN 0.7 → 0.6
print("\n=== Test 2: BE=0.6 ===")
old_be = config.BREAKEVEN_ATR_TRIGGER
config.BREAKEVEN_ATR_TRIGGER = 0.6
tests.append(run_and_collect("BE=0.6"))
config.BREAKEVEN_ATR_TRIGGER = old_be

# Test 3: BREAKEVEN 0.7 → 0.5 + HOLD=2 (kombo)
# BE=0.5 tek başına kötüydü ama HOLD=2 ile belki
print("\n=== Test 3: BE=0.5 (HOLD=2 ile) ===")
old_be = config.BREAKEVEN_ATR_TRIGGER
config.BREAKEVEN_ATR_TRIGGER = 0.5
tests.append(run_and_collect("BE=0.5"))
config.BREAKEVEN_ATR_TRIGGER = old_be

# Test 4: TP 1.2 → 1.3 (TP biraz genişlet, daha çok kazansın)
print("\n=== Test 4: TP=1.3 ===")
old_rr = config.DYNAMIC_RR["RANGING"].copy()
config.DYNAMIC_RR["RANGING"] = {"sl": 1.0, "tp": 1.3}
tests.append(run_and_collect("TP=1.3"))
config.DYNAMIC_RR["RANGING"] = old_rr

# Test 5: BL:FLOW + BE=0.6
print("\n=== Test 5: BL:FLOW + BE=0.6 ===")
old_bl = config.COIN_BLACKLIST.copy()
old_be = config.BREAKEVEN_ATR_TRIGGER
config.COIN_BLACKLIST = old_bl + ["FLOWUSDT"]
config.BREAKEVEN_ATR_TRIGGER = 0.6
tests.append(run_and_collect("FLOW+BE0.6"))
config.COIN_BLACKLIST = old_bl
config.BREAKEVEN_ATR_TRIGGER = old_be

# Test 6: ADAUSDT blacklist (time-exit'te -$27 en kötü trade)
print("\n=== Test 6: +ADAUSDT blacklist ===")
old_bl = config.COIN_BLACKLIST.copy()
config.COIN_BLACKLIST = old_bl + ["ADAUSDT"]
tests.append(run_and_collect("+BL:ADA"))
config.COIN_BLACKLIST = old_bl

# Test 7: BL:FLOW + BL:ADA + BE=0.6
print("\n=== Test 7: BL(FLOW+ADA) + BE=0.6 ===")
old_bl = config.COIN_BLACKLIST.copy()
old_be = config.BREAKEVEN_ATR_TRIGGER
config.COIN_BLACKLIST = old_bl + ["FLOWUSDT", "ADAUSDT"]
config.BREAKEVEN_ATR_TRIGGER = 0.6
tests.append(run_and_collect("FL+AD+BE0.6"))
config.COIN_BLACKLIST = old_bl
config.BREAKEVEN_ATR_TRIGGER = old_be

# Test 8: PTP_RATIO 0.50 → 0.45 (biraz daha erken TP1)
print("\n=== Test 8: TP1@45% ===")
old_ratio = config.PARTIAL_TP_RATIO
config.PARTIAL_TP_RATIO = 0.45
tests.append(run_and_collect("TP1@45%"))
config.PARTIAL_TP_RATIO = old_ratio

# === SONUÇ TABLOSU ===
print("\n" + "="*85)
print("TIME-EXIT OPTİMİZASYON SONUÇLARI")
print("="*85)
print(f"  {'Test':<18s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'MaxDD':>6s} | {'AvgW':>6s} | {'AvgL':>6s} | {'TE cnt':>6s}")
print(f"  {'─'*90}")

for name, r in tests:
    te_count = sum(1 for t in r.trades if "TIME-EXIT" in t.reason)
    te_pnl = sum(t.net_pnl for t in r.trades if "TIME-EXIT" in t.reason)
    marker = " ★" if r.win_rate >= 51.0 and r.total_pnl > tests[0][1].total_pnl else (" ✅" if r.total_pnl > tests[0][1].total_pnl else "")
    print(f"  {name:<18s} | {r.total_trades:5d} | {r.win_rate:5.1f}% | ${r.total_pnl:+8.2f} | {r.profit_factor:5.2f} | {r.max_drawdown_pct:5.1f}% | ${r.avg_win:+5.2f} | ${r.avg_loss:+5.2f} | {te_count:3d}({te_pnl:+.0f}){marker}")

print(f"\n  ★ = WR≥51% + PnL baseline'dan iyi  |  ✅ = PnL iyi")
print("="*85)
