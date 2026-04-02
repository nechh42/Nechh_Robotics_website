"""
query_status.py - Quick Status Query
=======================================
Run anytime to check system status from database + logs.

Usage: python query_status.py
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = "data/war_machine.db"
LOG_PATH = "logs/engine.log"


def main():
    print(f"\n{'='*50}")
    print(f"WAR MACHINE STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # Database stats
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        total = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        wins = c.execute("SELECT COUNT(*) FROM trades WHERE net_pnl > 0").fetchone()[0]
        pnl = c.execute("SELECT COALESCE(SUM(net_pnl),0) FROM trades").fetchone()[0]
        comm = c.execute("SELECT COALESCE(SUM(commission),0) FROM trades").fetchone()[0]
        wr = (wins / total * 100) if total > 0 else 0

        print(f"\nTrades: {total} (W:{wins} L:{total-wins})")
        print(f"Win Rate: {wr:.1f}%")
        print(f"Net PnL: ${pnl:.2f}")
        print(f"Commission: ${comm:.2f}")

        # Recent trades
        rows = c.execute(
            "SELECT timestamp,symbol,side,entry_price,exit_price,net_pnl,reason "
            "FROM trades ORDER BY timestamp DESC LIMIT 5"
        ).fetchall()
        if rows:
            print(f"\nLast {len(rows)} trades:")
            for r in rows:
                sign = "+" if r[5] >= 0 else ""
                print(f"  {r[0][:19]} {r[1]:10} {r[2]:5} ${r[3]:.2f}->${r[4]:.2f} {sign}${r[5]:.2f} [{r[6][:30]}]")

        # Open positions
        pos = c.execute("SELECT * FROM positions").fetchall()
        if pos:
            print(f"\nOpen Positions ({len(pos)}):")
            for p in pos:
                print(f"  {p[0]:10} {p[1]:5} @ ${p[2]:.2f} SL=${p[4]:.2f} TP=${p[5]:.2f}")
        else:
            print(f"\nOpen Positions: None")

        conn.close()
    else:
        print("\nDatabase not found")

    # Last log entries
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"\nLast 5 log entries:")
        for line in lines[-5:]:
            print(f"  {line.strip()[:100]}")

    # Process check
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command", "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id"],
            capture_output=True, text=True, timeout=5
        )
        pids = [l.strip() for l in result.stdout.strip().split("\n") if l.strip().isdigit()]
        print(f"\nPython processes: {len(pids)} ({', '.join(pids)})" if pids else "\nPython processes: 0")
    except Exception:
        pass

    print(f"\n{'='*50}")


if __name__ == "__main__":
    main()
