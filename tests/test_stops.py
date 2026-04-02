"""
test_stops.py - Unit Tests for SL/TP/Trailing Stop Logic
==========================================================
Verifies stop-loss, take-profit, and trailing stop work correctly.

Usage: python -m tests.test_stops
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state import Position
from risk.stop_manager import check_exit
from datetime import datetime
import config


def make_pos(symbol="TEST", side="LONG", entry=100.0, sl=98.0, tp=106.0):
    return Position(
        symbol=symbol, side=side, size=1.0,
        entry_price=entry, entry_time=datetime.now(),
        stop_loss=sl, take_profit=tp,
    )


def test_long_stop_loss():
    """LONG position should close when price hits stop loss"""
    pos = make_pos(side="LONG", entry=100, sl=98, tp=106)
    assert check_exit(pos, 99.0) is None, "Should not exit at 99"
    assert check_exit(pos, 98.5) is None, "Should not exit at 98.5"
    result = check_exit(pos, 97.5)
    assert result is not None, "Should exit at 97.5 (below SL 98)"
    assert "STOP-LOSS" in result
    print(f"  PASS: LONG SL hit at 97.5 (SL=98) → {result}")


def test_long_take_profit():
    """LONG position should close when price hits take profit"""
    pos = make_pos(side="LONG", entry=100, sl=98, tp=106)
    assert check_exit(pos, 105.0) is None, "Should not exit at 105"
    result = check_exit(pos, 106.5)
    assert result is not None, "Should exit at 106.5 (above TP 106)"
    assert "TAKE-PROFIT" in result
    print(f"  PASS: LONG TP hit at 106.5 (TP=106) → {result}")


def test_short_stop_loss():
    """SHORT position should close when price rises above stop loss"""
    pos = make_pos(side="SHORT", entry=100, sl=102, tp=94)
    assert check_exit(pos, 101.0) is None, "Should not exit at 101"
    result = check_exit(pos, 102.5)
    assert result is not None, "Should exit at 102.5 (above SL 102)"
    assert "STOP-LOSS" in result
    print(f"  PASS: SHORT SL hit at 102.5 (SL=102) → {result}")


def test_short_take_profit():
    """SHORT position should close when price drops below take profit"""
    pos = make_pos(side="SHORT", entry=100, sl=102, tp=94)
    assert check_exit(pos, 95.0) is None, "Should not exit at 95"
    result = check_exit(pos, 93.5)
    assert result is not None, "Should exit at 93.5 (below TP 94)"
    assert "TAKE-PROFIT" in result
    print(f"  PASS: SHORT TP hit at 93.5 (TP=94) → {result}")


def test_trailing_activation():
    """Trailing stop should activate after TRAILING_STOP_ACTIVATE profit"""
    pos = make_pos(side="LONG", entry=100, sl=98, tp=110)
    assert pos.trailing_active is False

    # Price rises 1% → should activate trailing
    activate_price = 100 * (1 + config.TRAILING_STOP_ACTIVATE)
    check_exit(pos, activate_price + 0.1)
    assert pos.trailing_active is True, f"Trailing should activate at {activate_price}"
    assert pos.trailing_peak > 0
    print(f"  PASS: Trailing activated at ${activate_price:.2f} (peak=${pos.trailing_peak:.2f})")


def test_trailing_ratchet():
    """Trailing stop should ratchet up (never lower) as price rises"""
    pos = make_pos(side="LONG", entry=100, sl=95, tp=120)
    pos.trailing_active = True
    pos.trailing_peak = 105

    # Price rises to 108 → SL should ratchet up
    check_exit(pos, 108)
    sl_after_108 = pos.stop_loss
    assert sl_after_108 > 95, f"SL should ratchet up from 95, got {sl_after_108}"

    # Price drops to 106 → SL should NOT decrease
    check_exit(pos, 106)
    assert pos.stop_loss >= sl_after_108, f"SL should not decrease: {pos.stop_loss} < {sl_after_108}"

    print(f"  PASS: Trailing ratcheted: 95 → {sl_after_108:.2f} (held at {pos.stop_loss:.2f})")


def test_trailing_exit():
    """Trailing stop should trigger exit when price drops below trailing SL"""
    pos = make_pos(side="LONG", entry=100, sl=95, tp=120)
    pos.trailing_active = True
    pos.trailing_peak = 110

    # Set trailing SL manually for test
    trail_sl = 110 * (1 - config.TRAILING_STOP_DISTANCE)
    pos.stop_loss = trail_sl

    # Price drops below trailing SL
    result = check_exit(pos, trail_sl - 0.5)
    assert result is not None, f"Should exit below trailing SL {trail_sl}"
    assert "STOP-LOSS" in result
    print(f"  PASS: Trailing exit at ${trail_sl - 0.5:.2f} (trailing SL=${trail_sl:.2f})")


def test_no_false_exit():
    """Position should NOT exit during normal price movement"""
    pos = make_pos(side="LONG", entry=100, sl=95, tp=110)
    # Test many prices between SL and TP - none should trigger exit
    for p in [96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109]:
        result = check_exit(pos, float(p))
        assert result is None, f"False exit at {p}: {result}"
    print(f"  PASS: No false exits between SL=95 and TP=110")


def main():
    tests = [
        ("LONG Stop Loss", test_long_stop_loss),
        ("LONG Take Profit", test_long_take_profit),
        ("SHORT Stop Loss", test_short_stop_loss),
        ("SHORT Take Profit", test_short_take_profit),
        ("Trailing Activation", test_trailing_activation),
        ("Trailing Ratchet", test_trailing_ratchet),
        ("Trailing Exit", test_trailing_exit),
        ("No False Exit", test_no_false_exit),
    ]

    print(f"\n{'='*50}")
    print("STOP MANAGER UNIT TESTS")
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
