"""
test_trade_trigger.py - Manual test to force candle close event
Simulates a candle close to trigger strategy evaluation
"""

import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "/war_machine")

import config
from data.candle_manager import Candle
from engine.orchestrator import Orchestrator

async def manual_test():
    """Manually trigger a 1h candle close to test trading"""
    
    # Create orchestrator
    orch = Orchestrator()
    
    # Initialize (load candles, connect datafeed)
    await orch.candles_4h.initialize()
    await orch.candles_1h.initialize()
    
    print("[TEST] Orchestrator initialized")
    print(f"[TEST] 4h candles: BTC={len(orch.candles_4h.candles['BTCUSDT'])}, ETH={len(orch.candles_4h.candles['ETHUSDT'])}")
    print(f"[TEST] 1h candles: BTC={len(orch.candles_1h.candles['BTCUSDT'])}, ETH={len(orch.candles_1h.candles['ETHUSDT'])}")
    
    # Manually create a closing candle from current prices
    btc_price = orch.candles_1h.get_current_price("BTCUSDT") or 67000
    eth_price = orch.candles_1h.get_current_price("ETHUSDT") or 2065
    
    print(f"\n[TEST] Simulating 1h candle close:")
    print(f"  BTC: ${btc_price:,.2f}")
    print(f"  ETH: ${eth_price:,.2f}")
    
    # Create fake closing candles
    import time
    closing_time_ms = int((time.time() - 3600) * 1000)  # 1 hour ago
    
    btc_candle = Candle(
        timestamp=closing_time_ms,
        open=btc_price * 0.99,
        high=btc_price * 1.01,
        low=btc_price * 0.98,
        close=btc_price,
        volume=1000,
        closed=True
    )
    
    eth_candle = Candle(
        timestamp=closing_time_ms,
        open=eth_price * 0.99,
        high=eth_price * 1.01,
        low=eth_price * 0.98,
        close=eth_price,
        volume=500,
        closed=True
    )
    
    # Simulate closes manually
    print("\n[TEST] Triggering regime detection...")
    
    # Call evaluate_strategies (which gets called on candle close)
    await orch._evaluate_strategies("BTCUSDT")
    await orch._evaluate_strategies("ETHUSDT")
    
    print("\n[TEST] Strategy evaluation complete - check logs for trades")
    await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(manual_test())
    print("\n[TEST] Done")
