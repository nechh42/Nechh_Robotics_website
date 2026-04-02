"""
voting.py - Regime-Weighted Strategy Voting
==============================================
Combines signals from multiple strategies using regime-aware weights.
Trend market → Momentum ağırlıklı
Ranging market → RSI + VWAP ağırlıklı
"""

import logging
from typing import List

import config
from engine.signal import Signal

logger = logging.getLogger(__name__)


def combine_signals(signals: List[Signal], regime: str, custom_weights: dict = None) -> Signal:
    """
    Combine multiple strategy signals using regime-weighted voting.

    Args:
        signals: List of signals from individual strategies
        regime: Current market regime
        custom_weights: Optional learned weights from AdaptiveWeights

    Returns:
        Single combined Signal with weighted confidence
    """
    # Filter out NONE signals
    active = [s for s in signals if s.action != "NONE" and s.confidence > 0]

    if not active:
        return Signal(
            symbol=signals[0].symbol if signals else "UNKNOWN",
            action="NONE", confidence=0.0,
            reason="No active signals", strategy="VOTE",
        )

    symbol = active[0].symbol
    weights = custom_weights or config.REGIME_WEIGHTS.get(regime, {"RSI": 0.33, "MOMENTUM": 0.34, "VWAP": 0.33})

    # Calculate votes: raw confidence for threshold, weighted for direction
    long_score = 0.0
    short_score = 0.0
    long_max_conf = 0.0
    short_max_conf = 0.0
    long_reasons = []
    short_reasons = []

    for sig in active:
        w = weights.get(sig.strategy, 0.33)
        weighted = sig.confidence * w

        if sig.action == "LONG":
            long_score += weighted
            long_max_conf = max(long_max_conf, sig.confidence)
            long_reasons.append(f"{sig.strategy}({sig.confidence:.2f})")
        elif sig.action == "SHORT":
            short_score += weighted
            short_max_conf = max(short_max_conf, sig.confidence)
            short_reasons.append(f"{sig.strategy}({sig.confidence:.2f})")

    # Smart conflict detection - only STRONG signals count as conflict
    # Weak signals (<0.30 confidence) are noise, not real disagreement
    CONFLICT_THRESHOLD = 0.55  # Sadece çok güçlü çakışmalar engellenir
    strong_long = [s for s in active if s.action == "LONG" and s.confidence >= CONFLICT_THRESHOLD]
    strong_short = [s for s in active if s.action == "SHORT" and s.confidence >= CONFLICT_THRESHOLD]
    n_long = len(long_reasons)
    n_short = len(short_reasons)
    has_real_conflict = len(strong_long) > 0 and len(strong_short) > 0

    # Only block when TWO STRONG signals genuinely disagree
    if has_real_conflict:
        return Signal(
            symbol=symbol, action="NONE", confidence=0.0,
            reason=f"CONFLICT: L({len(strong_long)})={long_score:.3f} vs S({len(strong_short)})={short_score:.3f}",
            strategy="VOTE",
        )

    # Confidence boost when 2+ strategies agree
    agreement_bonus = 1.0
    if n_long >= 2 or n_short >= 2:
        agreement_bonus = 1.15  # 15% bonus for multi-strategy confirmation

    # Determine winner using RAW confidence for threshold, weighted for direction
    # This prevents regime weights from crushing valid signals to zero
    if long_score > short_score and long_max_conf >= config.STRATEGY_MIN_CONFIDENCE:
        final_conf = min(long_max_conf * agreement_bonus, 0.95)
        reason = f"VOTE LONG: {'+'.join(long_reasons)} [{regime}]"
        logger.info(f"[VOTE] {symbol}: LONG conf={final_conf:.3f} ({n_long} agree) - {reason}")
        return Signal(
            symbol=symbol, action="LONG",
            confidence=final_conf,
            reason=reason, strategy="VOTE",
            price=active[0].price, atr=active[0].atr,
        )

    elif short_score > long_score and short_max_conf >= config.STRATEGY_MIN_CONFIDENCE:
        final_conf = min(short_max_conf * agreement_bonus, 0.95)
        reason = f"VOTE SHORT: {'+'.join(short_reasons)} [{regime}]"
        logger.info(f"[VOTE] {symbol}: SHORT conf={final_conf:.3f} ({n_short} agree) - {reason}")
        return Signal(
            symbol=symbol, action="SHORT",
            confidence=final_conf,
            reason=reason, strategy="VOTE",
            price=active[0].price, atr=active[0].atr,
        )

    elif long_max_conf >= config.STRATEGY_MIN_CONFIDENCE and n_long > 0:
        # Only LONG signals, no SHORT competition
        final_conf = min(long_max_conf * agreement_bonus, 0.95)
        reason = f"VOTE LONG: {'+'.join(long_reasons)} [{regime}]"
        logger.info(f"[VOTE] {symbol}: LONG conf={final_conf:.3f} (solo) - {reason}")
        return Signal(
            symbol=symbol, action="LONG",
            confidence=final_conf,
            reason=reason, strategy="VOTE",
            price=active[0].price, atr=active[0].atr,
        )

    elif short_max_conf >= config.STRATEGY_MIN_CONFIDENCE and n_short > 0:
        # Only SHORT signals, no LONG competition
        final_conf = min(short_max_conf * agreement_bonus, 0.95)
        reason = f"VOTE SHORT: {'+'.join(short_reasons)} [{regime}]"
        logger.info(f"[VOTE] {symbol}: SHORT conf={final_conf:.3f} (solo) - {reason}")
        return Signal(
            symbol=symbol, action="SHORT",
            confidence=final_conf,
            reason=reason, strategy="VOTE",
            price=active[0].price, atr=active[0].atr,
        )

    return Signal(
        symbol=symbol, action="NONE", confidence=0.0,
        reason=f"Below threshold (L={long_max_conf:.3f} S={short_max_conf:.3f})",
        strategy="VOTE",
    )