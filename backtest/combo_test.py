"""
combo_test.py — MAX_HOLD=2 üstüne kombinasyon testleri
Hedef: WR %50+ ve kârlı sistem
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from backtest.backtest_v3 import BacktestV3

def run_test(name, changes, revert):
    """Parametreleri değiştir, test et, geri al"""
    # Apply
    originals = {}
    for key, val in changes.items():
        if "." in key:
            parts = key.split(".")
            obj = getattr(config, parts[0])
            originals[key] = obj[parts[1]].copy() if isinstance(obj[parts[1]], dict) else obj[parts[1]]
            obj[parts[1]] = val
        else:
            originals[key] = getattr(config, key)
            setattr(config, key, val)

    bt = BacktestV3()
    r = bt.run(days=60)

    # Revert
    for key, val in originals.items():
        if "." in key:
            parts = key.split(".")
            obj = getattr(config, parts[0])
            obj[parts[1]] = val
        else:
            setattr(config, key, val)

    return r


tests = []

# Combo 1: MAX_HOLD=2 (already set) — baseline
print("\n=== COMBO 0: MAX_HOLD=2 (yeni baseline) ===")
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD=2 (base)", r))

# Combo 2: + PTP=80%
print("\n=== COMBO 1: MAX_HOLD=2 + PTP=80% ===")
r = run_test("HOLD2+PTP80", {"PARTIAL_TP_CLOSE_PCT": 0.80}, {})
tests.append(("HOLD2+PTP80%", r))

# Combo 3: + Blacklist BNB, XRP, LDO
print("\n=== COMBO 2: MAX_HOLD=2 + BL(BNB,XRP,LDO) ===")
old_bl = config.COIN_BLACKLIST.copy()
config.COIN_BLACKLIST = old_bl + ["BNBUSDT", "XRPUSDT", "LDOUSDT"]
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD2+BL3", r))
config.COIN_BLACKLIST = old_bl

# Combo 4: + PTP=80% + BL(BNB,XRP,LDO)
print("\n=== COMBO 3: MAX_HOLD=2 + PTP=80% + BL(BNB,XRP,LDO) ===")
old_bl = config.COIN_BLACKLIST.copy()
old_ptp = config.PARTIAL_TP_CLOSE_PCT
config.COIN_BLACKLIST = old_bl + ["BNBUSDT", "XRPUSDT", "LDOUSDT"]
config.PARTIAL_TP_CLOSE_PCT = 0.80
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD2+PTP80+BL3", r))
config.COIN_BLACKLIST = old_bl
config.PARTIAL_TP_CLOSE_PCT = old_ptp

# Combo 5: + Blacklist sadece LDOUSDT (en kötü -%46)
print("\n=== COMBO 4: MAX_HOLD=2 + BL(LDO) ===")
old_bl = config.COIN_BLACKLIST.copy()
config.COIN_BLACKLIST = old_bl + ["LDOUSDT"]
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD2+BL-LDO", r))
config.COIN_BLACKLIST = old_bl

# Combo 6: + PARTIAL_TP_RATIO 0.50 → 0.40 (daha erken TP1)
print("\n=== COMBO 5: MAX_HOLD=2 + TP1@40% (daha erken) ===")
old_ratio = config.PARTIAL_TP_RATIO
config.PARTIAL_TP_RATIO = 0.40
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD2+TP1@40%", r))
config.PARTIAL_TP_RATIO = old_ratio

# Combo 7: + PARTIAL_TP_RATIO=0.40 + PTP=80% (erken+çok kapat)
print("\n=== COMBO 6: MAX_HOLD=2 + TP1@40% + PTP=80% ===")
old_ratio = config.PARTIAL_TP_RATIO
old_ptp = config.PARTIAL_TP_CLOSE_PCT
config.PARTIAL_TP_RATIO = 0.40
config.PARTIAL_TP_CLOSE_PCT = 0.80
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("HOLD2+TP1@40+PTP80", r))
config.PARTIAL_TP_RATIO = old_ratio
config.PARTIAL_TP_CLOSE_PCT = old_ptp

# === SONUÇ TABLOSU ===
print("\n" + "="*80)
print("KOMBİNASYON TEST SONUÇLARI")
print("="*80)
print(f"  {'Test':<22s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'MaxDD':>6s} | {'AvgW':>6s} | {'AvgL':>6s}")
print(f"  {'─'*84}")

for name, r in tests:
    marker = " ★" if r.win_rate >= 50.0 else (" ✅" if r.total_pnl > 0 and r.win_rate > 48.5 else "")
    print(f"  {name:<22s} | {r.total_trades:5d} | {r.win_rate:5.1f}% | ${r.total_pnl:+8.2f} | {r.profit_factor:5.2f} | {r.max_drawdown_pct:5.1f}% | ${r.avg_win:+5.2f} | ${r.avg_loss:+5.2f}{marker}")

print(f"\n  ★ = WR ≥ %50  |  ✅ = Kârlı + WR > 48.5%")
print("="*80)
