"""
test_strategies.py - Unit Tests for Strategy Logic
=====================================================
Verifies strategies produce correct signals on known data patterns.

Usage: python -m tests.test_strategies
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.regime import detect_regime
from strategies.indicators import calc_rsi, calc_ema, calc_bollinger, calc_atr, calc_macd
from engine.voting import combine_signals
from engine.signal import Signal
from risk.pre_trade import PreTradeRisk
from engine.state import TradingState


def make_df(closes, high_offset=0.5, low_offset=0.5, volume=1000):
    """Create a test DataFrame from close prices"""
    closes = np.array(closes, dtype=float)
    return pd.DataFrame({
        "open": closes * 0.999,
        "high": closes + high_offset,
        "low": closes - low_offset,
        "close": closes,
        "volume": [volume] * len(closes),
    })


def test_rsi_oversold_long():
    """RSI < 30 in RANGING should produce LONG signal"""
    # Create declining prices to get low RSI
    prices = list(range(100, 60, -1)) + [59] * 10  # Drop then stay low
    df = make_df(prices)
    
    strat = RSIReversionStrategy()
    sig = strat.evaluate(df, "TESTUSDT", "RANGING")
    
    rsi = calc_rsi(df["close"]).iloc[-1]
    if rsi < 30:
        assert sig.action == "LONG", f"Expected LONG for RSI={rsi:.1f}, got {sig.action}"
        assert sig.confidence > 0, f"Expected positive confidence, got {sig.confidence}"
        print(f"  PASS: RSI={rsi:.1f} → LONG (conf={sig.confidence:.2f})")
    else:
        print(f"  SKIP: RSI={rsi:.1f} not oversold enough for test")


def test_rsi_overbought_short():
    """RSI > 70 in RANGING should produce SHORT signal"""
    prices = list(range(60, 100)) + [101] * 10  # Rise then stay high
    df = make_df(prices)
    
    strat = RSIReversionStrategy()
    sig = strat.evaluate(df, "TESTUSDT", "RANGING")
    
    rsi = calc_rsi(df["close"]).iloc[-1]
    if rsi > 70:
        assert sig.action == "SHORT", f"Expected SHORT for RSI={rsi:.1f}, got {sig.action}"
        print(f"  PASS: RSI={rsi:.1f} → SHORT (conf={sig.confidence:.2f})")
    else:
        print(f"  SKIP: RSI={rsi:.1f} not overbought enough for test")


def test_regime_trend_up():
    """Steadily rising prices should detect TREND_UP"""
    prices = [100 + i * 0.5 for i in range(60)]  # Steady uptrend
    df = make_df(prices)
    regime = detect_regime(df)
    assert regime == "TREND_UP", f"Expected TREND_UP, got {regime}"
    print(f"  PASS: Rising prices → {regime}")


def test_regime_trend_down():
    """Steadily falling prices should detect TREND_DOWN"""
    prices = [100 - i * 0.5 for i in range(60)]  # Steady downtrend
    df = make_df(prices)
    regime = detect_regime(df)
    assert regime == "TREND_DOWN", f"Expected TREND_DOWN, got {regime}"
    print(f"  PASS: Falling prices → {regime}")


def test_regime_ranging():
    """Sideways prices should detect RANGING"""
    np.random.seed(42)
    prices = [100 + np.random.uniform(-0.3, 0.3) for _ in range(60)]  # Flat with tiny noise
    df = make_df(prices)
    regime = detect_regime(df)
    assert regime == "RANGING", f"Expected RANGING, got {regime}"
    print(f"  PASS: Sideways prices → {regime}")


def test_conflict_detection():
    """Conflicting signals should be blocked"""
    signals = [
        Signal(symbol="TEST", action="LONG", confidence=0.7, reason="RSI", strategy="RSI", price=100),
        Signal(symbol="TEST", action="SHORT", confidence=0.8, reason="MOM", strategy="MOMENTUM", price=100),
    ]
    result = combine_signals(signals, "RANGING")
    assert result.action == "NONE", f"Expected NONE (conflict), got {result.action}"
    assert "CONFLICT" in result.reason, f"Expected CONFLICT in reason, got {result.reason}"
    print(f"  PASS: LONG+SHORT conflict → NONE ({result.reason})")


def test_bear_guard():
    """LONG should be blocked in TREND_DOWN"""
    risk = PreTradeRisk()
    state = TradingState(10000)
    sig = Signal(symbol="TEST", action="LONG", confidence=0.8, reason="test",
                 strategy="RSI", price=100)
    
    approved, reason, _ = risk.check(sig, state, "TREND_DOWN")
    assert not approved, f"Expected rejection, got approved"
    assert "BEAR GUARD" in reason, f"Expected BEAR GUARD, got {reason}"
    print(f"  PASS: LONG in TREND_DOWN → REJECTED ({reason})")


def test_volatile_block():
    """All trades should be blocked in VOLATILE"""
    risk = PreTradeRisk()
    state = TradingState(10000)
    sig = Signal(symbol="TEST", action="SHORT", confidence=0.8, reason="test",
                 strategy="MOMENTUM", price=100)
    
    approved, reason, _ = risk.check(sig, state, "VOLATILE")
    assert not approved, f"Expected rejection, got approved"
    assert "VOLATILE" in reason, f"Expected VOLATILE, got {reason}"
    print(f"  PASS: SHORT in VOLATILE → REJECTED ({reason})")


def test_indicators():
    """Basic indicator calculations should work"""
    prices = pd.Series([100 + i * 0.1 + np.sin(i / 3) for i in range(50)])
    
    rsi = calc_rsi(prices)
    assert not rsi.iloc[-1] != rsi.iloc[-1], "RSI should not be NaN"  # NaN check
    assert 0 <= rsi.iloc[-1] <= 100, f"RSI out of range: {rsi.iloc[-1]}"
    
    ema = calc_ema(prices, 20)
    assert len(ema) == len(prices), "EMA length mismatch"
    
    macd, signal, hist = calc_macd(prices)
    assert len(macd) == len(prices), "MACD length mismatch"
    
    print(f"  PASS: RSI={rsi.iloc[-1]:.1f}, EMA20={ema.iloc[-1]:.2f}, MACD={macd.iloc[-1]:.4f}")


def test_state_accounting():
    """State balance should be correct after open/close"""
    state = TradingState(10000)
    
    # Open position
    state.open_position("TEST", "LONG", 1.0, 100.0, 95.0, 103.0, "RSI")
    assert state.balance < 10000, "Balance should decrease after open (commission)"
    
    # Close at profit
    trade = state.close_position("TEST", 103.0, "TP")
    assert trade is not None, "Trade should be returned"
    assert trade.net_pnl > 0, f"Expected profit, got {trade.net_pnl}"
    assert "TEST" not in state.positions, "Position should be removed"
    
    print(f"  PASS: Open/Close accounting correct (PnL=${trade.net_pnl:.4f})")


def main():
    tests = [
        ("Indicators", test_indicators),
        ("RSI Oversold → LONG", test_rsi_oversold_long),
        ("RSI Overbought → SHORT", test_rsi_overbought_short),
        ("Regime: Trend Up", test_regime_trend_up),
        ("Regime: Trend Down", test_regime_trend_down),
        ("Regime: Ranging", test_regime_ranging),
        ("Conflict Detection", test_conflict_detection),
        ("Bear Guard", test_bear_guard),
        ("Volatile Block", test_volatile_block),
        ("State Accounting", test_state_accounting),
    ]

    print(f"\n{'='*50}")
    print("WAR MACHINE UNIT TESTS")
    print(f"{'='*50}")

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            print(f"\n[TEST] {name}")
            test_fn()
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
