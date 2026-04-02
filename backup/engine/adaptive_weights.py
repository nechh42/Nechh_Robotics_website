"""
adaptive_weights.py - Self-Learning Strategy Weights
=======================================================
Tracks which strategy predicted correctly and adjusts voting weights.
After each closed trade, the strategy that suggested it gets rewarded
or penalized based on PnL outcome.

Based on: crypto_fund/src/agents/swarm.py update_agent_weights()
Improved: per-regime tracking, decay, minimum floor
"""

import logging
from typing import Dict, List, Tuple
from collections import defaultdict

import config

logger = logging.getLogger(__name__)

# Minimum weight floor - no strategy goes below 5%
WEIGHT_FLOOR = 0.05
# How many recent trades to consider
LOOKBACK = 50


class AdaptiveWeights:
    """
    Learns optimal strategy weights from trade outcomes.
    
    After each trade:
      - Record which strategy suggested it and if it won/lost
      - Every 10 trades, recalculate weights proportional to accuracy
      - Per-regime tracking: weights learned separately for each regime
    """

    def __init__(self):
        # Per-regime trade history: regime -> [(strategy, won)]
        self._history: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
        # Current learned weights per regime (overrides config defaults)
        self._learned: Dict[str, Dict[str, float]] = {}
        self._total_trades = 0

    def record_outcome(self, strategy: str, regime: str, won: bool):
        """Record trade outcome for learning"""
        self._history[regime].append((strategy, won))
        # Trim to lookback window
        if len(self._history[regime]) > LOOKBACK:
            self._history[regime] = self._history[regime][-LOOKBACK:]
        
        self._total_trades += 1

        # Recalculate every 5 trades
        if self._total_trades % 5 == 0:
            self._recalculate(regime)

    def get_weights(self, regime: str) -> Dict[str, float]:
        """Get current weights for a regime (learned or default)"""
        if regime in self._learned:
            return self._learned[regime]
        return config.REGIME_WEIGHTS.get(regime, {"RSI": 0.33, "MOMENTUM": 0.34, "VWAP": 0.33})

    def _recalculate(self, regime: str):
        """Recalculate weights based on accuracy"""
        history = self._history.get(regime, [])
        if len(history) < 10:
            return  # Not enough data

        # Count accuracy per strategy
        accuracy: Dict[str, float] = {}
        counts: Dict[str, int] = defaultdict(int)
        wins: Dict[str, int] = defaultdict(int)

        for strategy, won in history:
            counts[strategy] += 1
            if won:
                wins[strategy] += 1

        for strat, total in counts.items():
            if total >= 3:  # Need at least 3 trades
                accuracy[strat] = wins[strat] / total

        if not accuracy:
            return

        # Normalize to weights with floor
        total_acc = sum(accuracy.values())
        if total_acc == 0:
            return

        new_weights = {}
        for strat in ["RSI", "MOMENTUM", "VWAP"]:
            if strat in accuracy:
                raw = accuracy[strat] / total_acc
                new_weights[strat] = max(WEIGHT_FLOOR, raw)
            else:
                # Keep default for strategies without data
                defaults = config.REGIME_WEIGHTS.get(regime, {})
                new_weights[strat] = defaults.get(strat, 0.33)

        # Normalize to sum=1
        total_w = sum(new_weights.values())
        if total_w > 0:
            new_weights = {k: v / total_w for k, v in new_weights.items()}

        self._learned[regime] = new_weights

        logger.info(
            f"[ADAPTIVE] {regime} weights updated: "
            + " ".join(f"{k}={v:.2f}" for k, v in new_weights.items())
            + f" (from {len(history)} trades)"
        )

    def get_stats(self) -> Dict:
        """Get learning statistics"""
        stats = {"total_trades": self._total_trades, "regimes": {}}
        for regime, history in self._history.items():
            wins = sum(1 for _, w in history if w)
            stats["regimes"][regime] = {
                "trades": len(history),
                "wins": wins,
                "win_rate": (wins / len(history) * 100) if history else 0,
                "weights": self._learned.get(regime, config.REGIME_WEIGHTS.get(regime, {})),
            }
        return stats
