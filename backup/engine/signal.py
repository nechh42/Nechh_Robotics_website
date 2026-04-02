"""
signal.py - Signal Data Structure
===================================
Single signal definition used by all strategies and engine components.
"""

from dataclasses import dataclass


@dataclass
class Signal:
    """Trading signal produced by a strategy"""
    symbol: str
    action: str        # LONG, SHORT, NONE
    confidence: float  # 0.0 - 1.0
    reason: str
    strategy: str      # Which strategy produced this
    price: float = 0.0
    atr: float = 0.0   # Current ATR (for dynamic SL/TP)
