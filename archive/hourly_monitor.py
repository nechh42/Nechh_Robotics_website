"""
hourly_monitor.py - Hourly Status Reporter
=============================================
Reads engine logs and reports status every hour.
Run in background: python hourly_monitor.py
"""

import os
import time
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
DB_PATH = Path("data/war_machine.db")

def get_latest_engine_log():
    """Find the latest engine log file"""
    logs = sorted(LOG_DIR.glob("engine_*.log"))
    if logs:
        return logs[-1]
    return LOG_DIR / "engine.log"

def parse_engine_stats(log_path):
    """Parse key metrics from engine log"""
    if not log_path.exists():
        return None
    
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    stats = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trades_opened": len(re.findall(r"\[RISK OK\]", content)),
        "trades_closed": len(re.findall(r"\[EXIT\]", content)),
        "sl_hits": len(re.findall(r"STOP-LOSS", content)),
        "tp_hits": len(re.findall(r"TAKE-PROFIT", content)),
        "errors": len(re.findall(r"\[ERROR\]", content)),
        "warnings": len(re.findall(r"\[WARNING\]", content)),
    }
    
    # Try to find latest equity (from performance log if available)
    equity_match = re.findall(r"Equity: \$([0-9,]+\.[0-9]+)", content)
    if equity_match:
        stats["equity"] = equity_match[-1]
    
    # Get latest price points
    prices = re.findall(r"\[(CANDLE|TICK)\].*@ \$([0-9]+\.[0-9]+)", content)
    if prices:
        stats["last_price"] = prices[-1][1]
    
    return stats

def print_hourly_report():
    """Print hourly status report"""
    log_path = get_latest_engine_log()
    stats = parse_engine_stats(log_path)
    
    if not stats:
        print("[MONITOR] No engine log found")
        return
    
    print("\n" + "="*70)
    print(f"⏰ HOURLY REPORT - {stats['timestamp']}")
    print("="*70)
    print(f"📊 Trade Activity:")
    print(f"   Opened:  {stats['trades_opened']}")
    print(f"   Closed:  {stats['trades_closed']}")
    print(f"   TP Hits: {stats['tp_hits']}")
    print(f"   SL Hits: {stats['sl_hits']}")
    print(f"💰 Equity: ${stats.get('equity', 'N/A')}")
    print(f"📈 Last Price: ${stats.get('last_price', 'N/A')}")
    print(f"⚠️  Errors: {stats['errors']} / Warnings: {stats['warnings']}")
    print("="*70 + "\n")

def monitor_loop():
    """Run hourly monitoring"""
    print("[MONITOR] Started - Will report every hour at :00")
    
    while True:
        now = datetime.now()
        # Wait until next hour boundary
        seconds_until_hour = (3600 - (now.minute * 60 + now.second)) % 3600
        
        if seconds_until_hour == 0:
            seconds_until_hour = 3600
        
        print(f"[MONITOR] Next report in {seconds_until_hour}s...")
        time.sleep(seconds_until_hour)
        
        print_hourly_report()

if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\n[MONITOR] Stopped by user")
