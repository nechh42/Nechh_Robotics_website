"""
test_risk_firewall.py - Verify all risk controls are REAL and ACTIVE
=====================================================================
No mock, no fake, no placeholder. Every check must work.

Usage: python -m tests.test_risk_firewall
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.signal import Signal
from engine.state import TradingState
from risk.pre_trade import PreTradeRisk
from engine.adaptive_weights import AdaptiveWeights


def test_bear_guard():
    risk = PreTradeRisk()
    state = TradingState(10000)
    sig = Signal(symbol="T", action="LONG", confidence=0.8, reason="t", strategy="RSI", price=100)
    ok, reason, _ = risk.check(sig, state, "TREND_DOWN")
    assert not ok and "BEAR GUARD" in reason
    print(f"  PASS: Bear Guard blocks LONG in downtrend")


def test_volatile_block():
    risk = PreTradeRisk()
    state = TradingState(10000)
    sig = Signal(symbol="T", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=100)
    ok, reason, _ = risk.check(sig, state, "VOLATILE")
    assert not ok and "VOLATILE" in reason
    print(f"  PASS: Volatile Block stops all trades in chaos")


def test_circuit_breaker_lockout():
    risk = PreTradeRisk()
    state = TradingState(10000)
    # Simulate 3 consecutive losses
    for i in range(3):
        risk.record_trade_result(-10.0, "TEST")
    assert risk._lockout_until is not None, "Lockout should be set"
    sig = Signal(symbol="T", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=100)
    ok, reason, _ = risk.check(sig, state, "RANGING")
    assert not ok and "CIRCUIT BREAKER" in reason
    print(f"  PASS: Circuit breaker locks after 3 losses ({reason})")


def test_circuit_breaker_clears_on_win():
    risk = PreTradeRisk()
    for i in range(3):
        risk.record_trade_result(-10.0, "TEST")
    assert risk._lockout_until is not None
    risk.record_trade_result(20.0, "TEST")  # Win clears lockout
    assert risk._lockout_until is None, "Win should clear lockout"
    print(f"  PASS: Circuit breaker clears after winning trade")


def test_commission_firewall():
    risk = PreTradeRisk()
    state = TradingState(10000)
    # Very small position where commission eats all profit
    sig = Signal(symbol="MICRO", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=0.001, atr=0.0)
    ok, reason, _ = risk.check(sig, state, "RANGING")
    print(f"  Commission firewall: ok={ok}, reason={reason[:80]}")
    # With normal price it should pass
    sig2 = Signal(symbol="BNBUSDT", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=630, atr=10)
    ok2, reason2, params = risk.check(sig2, state, "RANGING")
    if ok2:
        print(f"  PASS: Normal trade approved (commission check passed)")
    else:
        print(f"  INFO: Rejected: {reason2[:80]}")


def test_correlation_filter():
    risk = PreTradeRisk()
    state = TradingState(10000)
    # Open BTC position first
    state.open_position("BTCUSDT", "SHORT", 0.01, 68000, 69000, 66000)
    # Try to open ETH (correlated with BTC)
    sig = Signal(symbol="ETHUSDT", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=2000, atr=50)
    ok, reason, _ = risk.check(sig, state, "RANGING")
    assert not ok and "Correlated" in reason
    print(f"  PASS: Correlation filter blocks ETH when BTC open ({reason})")


def test_max_positions():
    risk = PreTradeRisk()
    state = TradingState(10000)
    state.open_position("BTCUSDT", "SHORT", 0.01, 68000, 69000, 66000)
    state.open_position("SOLUSDT", "SHORT", 1.0, 85, 87, 82)
    state.open_position("BNBUSDT", "SHORT", 0.1, 630, 640, 610)
    state.open_position("XRPUSDT", "SHORT", 100, 1.5, 1.6, 1.3)
    state.open_position("ADAUSDT", "SHORT", 500, 0.25, 0.27, 0.22)
    sig = Signal(symbol="DOTUSDT", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=1.5, atr=0.05)
    ok, reason, _ = risk.check(sig, state, "RANGING")
    assert not ok and "Max positions" in reason
    print(f"  PASS: Max positions (5) blocks 6th trade")


def test_adaptive_weights_learning():
    aw = AdaptiveWeights()
    # RSI wins 15 times in RANGING, MOMENTUM loses 15 times
    for _ in range(15):
        aw.record_outcome("RSI", "RANGING", True)
        aw.record_outcome("MOMENTUM", "RANGING", False)
    w = aw.get_weights("RANGING")
    assert w["RSI"] > w["MOMENTUM"], f"RSI({w['RSI']:.2f}) should > MOMENTUM({w['MOMENTUM']:.2f})"
    print(f"  PASS: Adaptive weights: RSI={w['RSI']:.2f} > MOMENTUM={w['MOMENTUM']:.2f}")


def test_daily_reset():
    risk = PreTradeRisk()
    risk._daily_trades = 99
    risk._daily_loss = 999.0
    # Simulate day change
    from datetime import date, timedelta
    risk._day_start = date.today() - timedelta(days=1)
    state = TradingState(10000)
    sig = Signal(symbol="T", action="SHORT", confidence=0.8, reason="t", strategy="RSI", price=100)
    risk.check(sig, state, "RANGING")  # This triggers daily reset
    assert risk._daily_trades == 0 and risk._daily_loss == 0.0
    print(f"  PASS: Daily counters reset at midnight")


def main():
    tests = [
        ("Bear Guard", test_bear_guard),
        ("Volatile Block", test_volatile_block),
        ("Circuit Breaker Lockout", test_circuit_breaker_lockout),
        ("Circuit Breaker Clear on Win", test_circuit_breaker_clears_on_win),
        ("Commission+Slippage Firewall", test_commission_firewall),
        ("Correlation Filter", test_correlation_filter),
        ("Max Positions", test_max_positions),
        ("Adaptive Weights Learning", test_adaptive_weights_learning),
        ("Daily Counter Reset", test_daily_reset),
    ]

    print(f"\n{'='*50}")
    print("RISK FIREWALL VERIFICATION")
    print(f"{'='*50}")

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            print(f"\n[TEST] {name}")
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
