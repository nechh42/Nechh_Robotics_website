"""
base.py - Strategy Interface
===============================
All strategies must implement this interface.
"""

from abc import ABC, abstractmethod
import pandas as pd
from engine.signal import Signal


class BaseStrategy(ABC):
    """Abstract base for all strategies"""

    name: str = "BASE"

    @abstractmethod
    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        """
        Evaluate strategy on candle DataFrame.

        Args:
            df: OHLCV DataFrame (columns: open, high, low, close, volume)
            symbol: Trading symbol
            regime: Market regime (TREND_UP, TREND_DOWN, RANGING)

        Returns:
            Signal with action, confidence, reason
        """
        ...
