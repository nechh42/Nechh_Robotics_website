"""
edge_discovery.py - Edge Discovery Based Strategy (v1.0)
===============================================================
Uses patterns discovered by the Edge Discovery Engine.
Implements the top edge patterns with highest win rates.

Top Patterns (from 2026-04-03 discovery):
  1. High Volatility (78.6% WR @ 4h across multiple coins)
  2. Momentum Continuation Up (80% WR @ 4h - PEPEUSDT)
  3. BB Upper + High Volume (75% WR @ 4h - PEPEUSDT)
  4. Trend Down (54% WR @ 24h - BNBUSDT)
  5. RSI Oversold + Downtrend (58% WR @ 24h - ADAUSDT)

Strategy Logic:
  - PRIMARY signal: High volatility breakout (short-term, +4h window)
  - SECONDARY signal: Momentum continuation in uptrend (aggressive, +4h)
  - TERTIARY signal: Oversold bounce in downtrend (conservative, +24h)
  - Use coin-specific rules when applicable
  - Multiple edge patterns increase confidence instead of replacing each other
"""

import logging
import pandas as pd

import config
from engine.signal import Signal
from strategies.base import BaseStrategy
from strategies.indicators import (
    calc_rsi,
    calc_ema,
    calc_atr,
    detect_high_volatility,
    detect_momentum_continuation_up,
    detect_bb_upper_high_volume,
    detect_trend_down,
    detect_rsi_oversold,
    detect_bb_lower_high_volume,
    detect_trend_down_oversold,
    detect_strong_momentum_up,
    detect_strong_momentum_down,
    detect_squeeze_breakout_down,
    detect_low_volatility,
    detect_bb_squeeze,
    detect_trend_mixed,
    detect_rsi_30_50,
    detect_price_below_ema50,
    detect_bb_near_lower,
    detect_oversold_high_volume,
    detect_ranging_bb_upper,
)

logger = logging.getLogger(__name__)


class EdgeDiscoveryStrategy(BaseStrategy):
    """
    Implements discovered edge patterns from backtest analysis.
    Prioritizes patterns with >60% win rate and >+10% edge vs baseline.
    """

    name = "EDGE_DISCOVERY"

    def __init__(self):
        # Pattern weights (based on discovery results)
        self.pattern_weights = {
            "high_volatility": 0.25,              # Common, strong edge
            "momentum_continuation_up": 0.20,     # Aggressive, highest WR
            "bb_upper_high_volume": 0.15,         # Secondary breakout
            "trend_down": 0.10,                   # Conservative short
            "trend_down_oversold": 0.15,          # Reversal opportunity
            "rsi_oversold": 0.08,                 # Mean reversion base
            "bb_lower_high_volume": 0.07,         # Reversal
        }

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        """Evaluate using discovered edge patterns"""
        
        if df is None or len(df) < 50:
            return Signal(
                symbol=symbol, action="NONE", confidence=0.0,
                reason="Insufficient data", strategy=self.name
            )

        price = df["close"].iloc[-1]
        
        # Detect all patterns
        patterns = self._detect_patterns(df, symbol, regime)
        
        # Score long and short setups
        long_score, long_reasons = self._calculate_long_score(patterns)
        short_score, short_reasons = self._calculate_short_score(patterns)

        # Determine action
        if long_score > short_score and long_score > 0.35:
            action = "LONG"
            confidence = min(0.85, long_score)
            reason = " | ".join(long_reasons[:3])  # Top 3 reasons
            
            if not config.ALLOW_LONG:
                return Signal(symbol=symbol, action="NONE", confidence=0.0,
                              reason="LONG disabled", strategy=self.name, price=price)
        
        elif short_score > long_score and short_score > 0.35:
            action = "SHORT"
            confidence = min(0.85, short_score)
            reason = " | ".join(short_reasons[:3])
            
            if not config.ALLOW_SHORT and not getattr(config, 'ALLOW_SHORT_CONDITIONAL', False):
                return Signal(symbol=symbol, action="NONE", confidence=0.0,
                              reason="SHORT disabled", strategy=self.name, price=price)
        
        else:
            return Signal(symbol=symbol, action="NONE", confidence=0.0,
                          reason="No strong edge pattern", strategy=self.name, price=price)

        if action != "NONE":
            logger.info(
                f"[EDGE_DISCOVERY] {symbol}: {action} conf={confidence:.2f} "
                f"long={long_score:.2f} short={short_score:.2f} - {reason}"
            )

        return Signal(
            symbol=symbol, action=action, confidence=confidence,
            reason=reason, strategy=self.name, price=price
        )

    def _detect_patterns(self, df: pd.DataFrame, symbol: str, regime: str) -> dict:
        """Detect all edge patterns in current candle"""
        patterns = {
            # ======================== UPTREND PATTERNS ========================
            "high_volatility": detect_high_volatility(df).iloc[-1] if len(df) > 50 else False,
            "momentum_continuation_up": detect_momentum_continuation_up(df).iloc[-1] if len(df) > 4 else False,
            "bb_upper_high_volume": detect_bb_upper_high_volume(df).iloc[-1] if len(df) > 20 else False,
            "strong_momentum_up": detect_strong_momentum_up(df, 0.05).iloc[-1] if len(df) > 24 else False,
            "ranging_bb_upper": detect_ranging_bb_upper(df).iloc[-1] if len(df) > 20 else False,
            
            # ======================== DOWNTREND/REVERSAL ========================
            "trend_down": detect_trend_down(df).iloc[-1] if len(df) > 50 else False,
            "trend_down_oversold": detect_trend_down_oversold(df, 35).iloc[-1] if len(df) > 50 else False,
            "rsi_oversold": detect_rsi_oversold(df, 40).iloc[-1] if len(df) > 14 else False,
            "bb_lower_high_volume": detect_bb_lower_high_volume(df).iloc[-1] if len(df) > 20 else False,
            "oversold_high_volume": detect_oversold_high_volume(df, 35).iloc[-1] if len(df) > 20 else False,
            "bb_near_lower": detect_bb_near_lower(df).iloc[-1] if len(df) > 20 else False,
            "price_below_ema50": detect_price_below_ema50(df).iloc[-1] if len(df) > 50 else False,
            
            # ======================== COMPRESSION/BREAKOUT ========================
            "bb_squeeze": detect_bb_squeeze(df).iloc[-1] if len(df) > 50 else False,
            "squeeze_breakout_down": detect_squeeze_breakout_down(df).iloc[-1] if len(df) > 20 else False,
            "low_volatility": detect_low_volatility(df).iloc[-1] if len(df) > 50 else False,
            
            # ======================== NEUTRAL/MIXED ========================
            "trend_mixed": detect_trend_mixed(df).iloc[-1] if len(df) > 50 else False,
            "rsi_30_50": detect_rsi_30_50(df).iloc[-1] if len(df) > 14 else False,
            
            # ======================== MOMENTUM ========================
            "strong_momentum_down": detect_strong_momentum_down(df, -0.05).iloc[-1] if len(df) > 24 else False,
        }
        
        # ======================== COIN-SPECIFIC OVERRIDES ========================
        # Based on Edge Discovery v2.0 validation results
        
        if symbol == "VETUSDT":
            # strong_mom_down: 87.1% WR @ 12h
            patterns["strong_momentum_down_weight"] = 2.0
        
        elif symbol == "ARPAUSDT":
            # squeeze_breakout_down: 84.1% WR, low_volatility: 81.5% WR
            patterns["squeeze_breakout_down_weight"] = 1.8
            patterns["low_volatility_weight"] = 1.7
            patterns["bb_squeeze_weight"] = 1.3
        
        elif symbol == "XRPUSDT":
            # rsi_below_40: 59.1% WR, trend_down: 54.4% WR
            patterns["rsi_oversold_weight"] = 1.4
            patterns["trend_down_weight"] = 1.3
        
        elif symbol == "LDOUSDT":
            # high_volatility: 74.4% WR @ 24h
            patterns["high_volatility_weight"] = 1.5
        
        elif symbol == "FLOWUSDT":
            # trend_mixed: 52.5% WR but +3.48% avg return!!
            patterns["trend_mixed_weight"] = 1.5
        
        elif symbol == "AAVEUSDT":
            # strong_mom_down: 63.9% WR @ 12h
            patterns["strong_momentum_down_weight"] = 1.4
        
        elif symbol == "SOLUSDT":
            # ranging_bb_upper: 69% WR @ 4h
            patterns["ranging_bb_upper_weight"] = 1.5
        
        elif symbol == "PEPEUSDT":
            # momentum_continuation_up: high WR patterns
            patterns["momentum_continuation_up_weight"] = 1.5
            patterns["bb_upper_high_volume_weight"] = 1.3
        
        elif symbol == "DOGEUSDT":
            # trend_down: 54.5% WR @ 24h (large sample 455)
            patterns["trend_down_weight"] = 1.2
            patterns["rsi_30_50_weight"] = 1.2
        
        # Regime adjustments
        if regime == "TREND_UP":
            patterns["momentum_continuation_up_weight"] = 1.2
            patterns["high_volatility_weight"] = 1.1
        elif regime == "TREND_DOWN":
            patterns["trend_down_weight"] = 1.1
            patterns["trend_down_oversold_weight"] = 1.2
        elif regime == "RANGING":
            patterns["ranging_bb_upper_weight"] = 1.1
            patterns["trend_mixed_weight"] = 1.1
        
        return patterns

    def _calculate_long_score(self, patterns: dict) -> tuple:
        """Calculate long setup score based on patterns"""
        score = 0.0
        reasons = []
        
        # HIGH PRIORITY LONG SIGNALS
        # Momentum continuation (primary long signal)
        if patterns.get("momentum_continuation_up", False):
            weight = patterns.get("momentum_continuation_up_weight", 1.0)
            add = 0.35 * weight
            score += add
            reasons.append(f"Momentum↑ ({add:.2f})")
        
        # High volatility (opportunity signal)
        if patterns.get("high_volatility", False):
            weight = patterns.get("high_volatility_weight", 1.0)
            add = 0.25 * weight
            score += add
            reasons.append(f"Vol↑ ({add:.2f})")
        
        # BB upper breakout
        if patterns.get("bb_upper_high_volume", False):
            weight = patterns.get("bb_upper_high_volume_weight", 1.0)
            add = 0.20 * weight
            score += add
            reasons.append(f"BB↑vol ({add:.2f})")
        
        # Strong momentum over 24h
        if patterns.get("strong_momentum_up", False):
            score += 0.15
            reasons.append("Mom24↑")
        
        # SECONDARY LONG SIGNALS
        # Ranging market at BB upper (fading overbought)
        if patterns.get("ranging_bb_upper", False):
            weight = patterns.get("ranging_bb_upper_weight", 1.0)
            add = 0.15 * weight
            score += add
            reasons.append(f"Range↑ ({add:.2f})")
        
        # Breakout from squeeze
        if patterns.get("bb_squeeze", False):
            weight = patterns.get("bb_squeeze_weight", 1.0)
            add = 0.10 * weight
            score += add
            reasons.append(f"Squeeze ({add:.2f})")
        
        return min(1.0, score), reasons

    def _calculate_short_score(self, patterns: dict) -> tuple:
        """Calculate short setup score based on patterns"""
        score = 0.0
        reasons = []
        
        # NOTE: SHORT is DISABLED in config (ALLOW_SHORT = False)
        # But we still calculate for informational purposes / future use
        
        # HIGH PRIORITY SHORT SIGNALS
        # Strong momentum down (87% WR in VETUSDT)
        if patterns.get("strong_momentum_down", False):
            weight = patterns.get("strong_momentum_down_weight", 1.0)
            add = 0.35 * weight
            score += add
            reasons.append(f"Mom↓ ({add:.2f})")
        
        # Squeeze + Breakout down (84% WR in ARPAUSDT)
        if patterns.get("squeeze_breakout_down", False):
            weight = patterns.get("squeeze_breakout_down_weight", 1.0)
            add = 0.30 * weight
            score += add
            reasons.append(f"Sqz↓ ({add:.2f})")
        
        # Trend down (primary short signal)
        if patterns.get("trend_down", False):
            weight = patterns.get("trend_down_weight", 1.0)
            add = 0.25 * weight
            score += add
            reasons.append(f"Trend↓ ({add:.2f})")
        
        # Trend down + oversold (strong reversal setup)
        if patterns.get("trend_down_oversold", False):
            weight = patterns.get("trend_down_oversold_weight", 1.0)
            add = 0.30 * weight
            score += add
            reasons.append(f"T↓OS ({add:.2f})")
        
        # SECONDARY SHORT SIGNALS
        # BB lower reversal
        if patterns.get("bb_lower_high_volume", False):
            weight = patterns.get("bb_lower_high_volume_weight", 1.0)
            add = 0.15 * weight
            score += add
            reasons.append(f"BB↓vol ({add:.2f})")
        
        # Oversold + High Volume (capitulation)
        if patterns.get("oversold_high_volume", False):
            weight = patterns.get("oversold_high_volume_weight", 1.0)
            add = 0.20 * weight
            score += add
            reasons.append(f"OSlvol ({add:.2f})")
        
        # Price below EMA50 (weakness)
        if patterns.get("price_below_ema50", False):
            weight = patterns.get("price_below_ema50_weight", 1.0)
            add = 0.12 * weight
            score += add
            reasons.append(f"EMA50↓ ({add:.2f})")
        
        # Low volatility (before breakout)
        if patterns.get("low_volatility", False):
            weight = patterns.get("low_volatility_weight", 1.0)
            add = 0.10 * weight
            score += add
            reasons.append(f"Vol↓ ({add:.2f})")
        
        return min(1.0, score), reasons
        return min(1.0, score), reasons
