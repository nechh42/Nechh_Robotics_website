"""
run_all.py - Multi-Symbol Backtest Runner
============================================
Tests all symbols and produces a combined summary report.

Usage: python -m backtest.run_all --days 30
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import config
from backtest.engine import run_backtest

logging.basicConfig(level=logging.WARNING)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()

    results = []
    for sym in config.SYMBOLS:
        try:
            r = run_backtest(sym, args.interval, args.days)
            results.append(r)
        except Exception as e:
            print(f"ERROR {sym}: {e}")

    # Summary
    print(f"\n{'='*70}")
    print(f"COMBINED BACKTEST REPORT ({args.days} days, {args.interval})")
    print(f"{'='*70}")
    print(f"{'Symbol':<12} {'Trades':>6} {'WR%':>6} {'PnL':>10} {'MaxDD%':>7} {'Sharpe':>7} {'Status':>8}")
    print(f"{'-'*12} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*7} {'-'*8}")

    total_pnl = 0
    total_trades = 0
    profitable = 0

    for r in results:
        status = "✅" if r.total_pnl > 0 else "❌"
        if r.total_pnl > 0:
            profitable += 1
        total_pnl += r.total_pnl
        total_trades += r.total_trades

        print(
            f"{r.symbol:<12} {r.total_trades:>6} {r.win_rate:>5.1f}% "
            f"${r.total_pnl:>9.2f} {r.max_drawdown:>6.1f}% {r.sharpe:>7.2f} {status:>8}"
        )

    print(f"{'-'*70}")
    print(f"{'TOTAL':<12} {total_trades:>6} {'':>6} ${total_pnl:>9.2f}")
    print(f"Profitable: {profitable}/{len(results)} symbols")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
