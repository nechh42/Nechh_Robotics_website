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
      - Persists to DB: survives restarts
    """

    def __init__(self, db=None):
        # Per-regime trade history: regime -> [(strategy, won)]
        self._history: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
        # Current learned weights per regime (overrides config defaults)
        self._learned: Dict[str, Dict[str, float]] = {}
        self._total_trades = 0
        self._db = db

        # Load from DB if available
        if self._db:
            self._load_from_db()

    def set_db(self, db):
        """Set database reference and load history"""
        self._db = db
        self._load_from_db()

    def _load_from_db(self):
        """Load trade outcome history from database"""
        if not self._db:
            return
        try:
            history = self._db.load_adaptive_history(lookback=LOOKBACK)
            for regime, outcomes in history.items():
                self._history[regime] = outcomes
                self._total_trades += len(outcomes)
            # Recalculate weights for all regimes with data
            for regime in self._history:
                self._recalculate(regime)
            if self._total_trades > 0:
                logger.info(
                    f"[ADAPTIVE] DB'den yüklendi: {self._total_trades} trade, "
                    f"{len(self._history)} regime"
                )
                for regime, weights in self._learned.items():
                    logger.info(
                        f"[ADAPTIVE] {regime}: "
                        + " ".join(f"{k}={v:.2f}" for k, v in weights.items())
                    )
        except Exception as e:
            logger.error(f"[ADAPTIVE] DB load failed: {e}")

    def record_outcome(self, strategy: str, regime: str, won: bool):
        """Record trade outcome for learning"""
        self._history[regime].append((strategy, won))
        # Trim to lookback window
        if len(self._history[regime]) > LOOKBACK:
            self._history[regime] = self._history[regime][-LOOKBACK:]
        
        self._total_trades += 1

        # Persist to DB
        if self._db:
            try:
                self._db.save_adaptive_outcome(regime, strategy, won)
            except Exception as e:
                logger.error(f"[ADAPTIVE] DB save failed: {e}")

        # Recalculate every 5 trades
        if self._total_trades % 5 == 0:
            self._recalculate(regime)

    def get_weights(self, regime: str) -> Dict[str, float]:
        """Get current weights for a regime (learned or default)"""
        if regime in self._learned:
            return self._learned[regime]
        return config.REGIME_WEIGHTS.get(regime, {"RSI": 0.25, "MOMENTUM": 0.25, "VWAP": 0.25, "EDGE_DISCOVERY": 0.25})

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
        for strat in ["RSI", "MOMENTUM", "VWAP", "EDGE_DISCOVERY"]:
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
