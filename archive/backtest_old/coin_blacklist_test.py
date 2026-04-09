"""
coin_blacklist_test.py - LTC ve BTC blacklist testi
=====================================================
dynamic_coin_test sonuçları:
  - LTC: 44 trade, 43.2% WR, -$3.41
  - BTC: 35 trade, 45.7% WR, -$6.42
Bunları blacklist'e alınca PF yükselir mi?

Testler:
  1. BASELINE: Mevcut 15 coin (v15.9)
  2. BL+LTC: LTC blacklist'e ekle → 14 aktif coin
  3. BL+BTC: BTC blacklist'e ekle → 14 aktif coin
  4. BL+LTC+BTC: İkisini de ekle → 13 aktif coin

Kullanım:
  python -m backtest.coin_blacklist_test
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from backtest.backtest_v3 import BacktestV3
import numpy as np


def run_test(label, extra_blacklist):
    """Backtest çalıştır, ekstra blacklist coin'leri ile."""
    # Geçici olarak blacklist'e ekle
    original_bl = list(config.COIN_BLACKLIST)
    config.COIN_BLACKLIST = original_bl + extra_blacklist

    active = [s for s in config.SYMBOLS if s not in config.COIN_BLACKLIST]

    bt = BacktestV3()
    result = bt.run(symbols=config.SYMBOLS, days=60)

    # Restore
    config.COIN_BLACKLIST = original_bl

    trades = result.trades
    if not trades:
        return {"label": label, "trades": 0, "wr": 0, "pnl": 0, "pf": 0, "dd": 0, "active": len(active)}

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
        "label": label,
        "trades": len(trades),
        "wr": wr,
        "pnl": pnl,
        "pf": pf,
        "dd": dd_pct,
        "active": len(active),
        "avg_win": np.mean(wins) if wins else 0,
        "avg_loss": np.mean(losses) if losses else 0,
    }


if __name__ == "__main__":
    tests = [
        ("BASELINE (15 coin)", []),
        ("BL+LTC (14 coin)", ["LTCUSDT"]),
        ("BL+BTC (14 coin)", ["BTCUSDT"]),
        ("BL+LTC+BTC (13 coin)", ["LTCUSDT", "BTCUSDT"]),
    ]

    print(f"\n{'='*70}")
    print(f"LTC / BTC BLACKLİST TESTİ")
    print(f"{'='*70}")

    results = []
    for i, (label, extra_bl) in enumerate(tests):
        print(f"\n[{i+1}/{len(tests)}] {label}...", flush=True)
        r = run_test(label, extra_bl)
        results.append(r)
        print(f"  → {r['trades']} trade | WR={r['wr']:.1f}% | PnL=${r['pnl']:+.2f} | PF={r['pf']:.2f} | DD={r['dd']:.1f}%")

    baseline = results[0]

    print(f"\n{'='*70}")
    print(f"SONUÇ TABLOSU")
    print(f"{'='*70}")
    print(f"  {'Test':25s} | {'Coin':>4s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'DD':>5s} | vs BL")
    print(f"  {'─'*25}─┼─{'─'*4}─┼─{'─'*5}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*5}─┼─{'─'*5}─┼─{'─'*8}")

    for r in results:
        diff = r["pnl"] - baseline["pnl"]
        marker = " ★" if diff > 0 else ""
        bl = " (BL)" if r == baseline else ""
        print(f"  {r['label']:25s} | {r['active']:>4d} | {r['trades']:>5d} | {r['wr']:>5.1f}% | "
              f"${r['pnl']:>+9.2f} | {r['pf']:>5.2f} | {r['dd']:>4.1f}% | ${diff:>+.0f}{marker}{bl}")
