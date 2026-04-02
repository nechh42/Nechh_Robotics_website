"""
position_sizer.py - Dynamic Kelly Position Sizing
====================================================
Replaces fixed 5% position size with adaptive sizing based on:
  1. Historical win rate + win/loss ratio (Kelly Criterion)
  2. Market regime adjustment (conservative in downtrend/volatile)
  3. Performance momentum (hot/cold streak detection)

Based on: crypto_fund/src/risk/dynamic_kelly.py (simplified, no DB dependency)

Quarter Kelly used by default (reduces variance significantly).
Hard cap at 10% per position regardless of Kelly signal.
"""

import logging
import math
from typing import Dict, List

import config

logger = logging.getLogger(__name__)

# Regime multipliers for Kelly
REGIME_MULT = {
    "TREND_UP": 1.2,
    "TREND_DOWN": 0.6,
    "RANGING": 0.8,
    "VOLATILE": 0.4,
}

# Streak multipliers
STREAK_MULT = {
    "hot": 1.1,    # 4+ wins in last 5
    "cold": 0.5,   # 4+ losses in last 5
    "normal": 1.0,
}


class DynamicPositionSizer:
    """
    Kelly Criterion-based position sizing.
    
    Kelly formula: K = W - (1-W)/R
      W = win probability
      R = avg_win / avg_loss ratio
    
    Quarter Kelly (K * 0.25) used for safety.
    """

    def __init__(self, fractional: float = 0.25):
        self.fractional = fractional
        self._pnl_history: List[float] = []
        self._min_trades = 15  # Need at least 15 trades for Kelly

    def record_trade(self, net_pnl: float):
        """Record trade result for Kelly calculation"""
        self._pnl_history.append(net_pnl)
        # Keep last 100 trades
        if len(self._pnl_history) > 100:
            self._pnl_history = self._pnl_history[-100:]

    def get_position_pct(self, regime: str = "RANGING") -> float:
        """
        Get recommended position size as fraction of equity.
        
        Returns:
            Float between 0.01 (1%) and 0.10 (10%)
        """
        if len(self._pnl_history) < self._min_trades:
            # Not enough data - use conservative default
            base = config.MAX_POSITION_SIZE_PCT  # 5%
            regime_adj = REGIME_MULT.get(regime, 1.0)
            return max(0.01, min(0.10, base * regime_adj))

        # Calculate Kelly
        wins = [p for p in self._pnl_history if p > 0]
        losses = [p for p in self._pnl_history if p <= 0]

        if not wins or not losses:
            return 0.02  # Edge case: all wins or all losses

        win_rate = len(wins) / len(self._pnl_history)
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))

        if avg_loss == 0:
            return 0.02

        win_loss_ratio = avg_win / avg_loss

        # Kelly: K = W - (1-W)/R
        if win_loss_ratio > 0:
            kelly_full = win_rate - (1 - win_rate) / win_loss_ratio
        else:
            kelly_full = 0.0

        # Fractional Kelly
        kelly = max(0.0, kelly_full * self.fractional)

        # Regime adjustment
        regime_adj = REGIME_MULT.get(regime, 1.0)
        kelly *= regime_adj

        # Streak adjustment
        streak = self._detect_streak()
        kelly *= STREAK_MULT.get(streak, 1.0)

        # Hard caps: 1% min, 10% max
        final = max(0.01, min(kelly, 0.10))

        # Special: cold streak + volatile = ultra conservative
        if streak == "cold" and regime == "VOLATILE":
            final = min(final, 0.02)

        if len(self._pnl_history) % 10 == 0:
            logger.info(
                f"[KELLY] WR={win_rate:.0%} R={win_loss_ratio:.2f} "
                f"K_full={kelly_full:.4f} K_frac={kelly:.4f} "
                f"regime={regime}({regime_adj}) streak={streak} "
                f"final={final:.2%}"
            )

        return final

    def _detect_streak(self) -> str:
        """Detect hot/cold streak from last 5 trades"""
        if len(self._pnl_history) < 5:
            return "normal"
        
        last5 = self._pnl_history[-5:]
        wins = sum(1 for p in last5 if p > 0)
        
        if wins >= 4:
            return "hot"
        elif wins <= 1:
            return "cold"
        return "normal"

    def get_stats(self) -> Dict:
        """Get current Kelly statistics"""
        if not self._pnl_history:
            return {"trades": 0, "status": "insufficient_data"}

        wins = [p for p in self._pnl_history if p > 0]
        losses = [p for p in self._pnl_history if p <= 0]
        
        return {
            "trades": len(self._pnl_history),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self._pnl_history) if self._pnl_history else 0,
            "avg_win": sum(wins) / len(wins) if wins else 0,
            "avg_loss": abs(sum(losses) / len(losses)) if losses else 0,
            "streak": self._detect_streak(),
            "total_pnl": sum(self._pnl_history),
        }
