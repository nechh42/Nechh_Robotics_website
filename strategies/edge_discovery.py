"""
edge_discovery.py - Edge Discovery Based Strategy (v2.0 — FIXED)
===============================================================
Uses patterns discovered by the Edge Discovery Engine (edge_discovery.py).
CRITICAL FIX v2.0: Edge patterns predict FORWARD RETURNS.
  Positive AvgRet after "trend_down" = price RECOVERS = LONG signal!
  Previous version incorrectly classified these as SHORT signals.

Edge Discovery Results (edge_top.txt, 2026-04-03):
  Top contrarian/mean-reversion LONG edges:
    #1  VETUSDT   strong_mom_down      87.1% WR  +2.59% avg  @12h
    #2  ARPAUSDT  squeeze_breakout_down 84.1% WR  +1.78% avg  @24h
    #3  ARPAUSDT  low_volatility       81.5% WR  +1.45% avg  @24h
    #13 LDOUSDT   high_volatility      74.4% WR  +1.50% avg  @24h
    #21 SOLUSDT   ranging_bb_upper     69.0% WR  +0.77% avg  @4h
    #30 XRPUSDT   rsi_below_30         66.7% WR  +0.37% avg  @4h

  Top breakout LONG edges:
    #23 PEPEUSDT  momentum_cont_up     65.8% WR  +0.45% avg  @1h
    #18 FLOWUSDT  rsi_above_65         63.8% WR  +1.77% avg  @4h

Strategy: ALL edge patterns with positive AvgRet → LONG direction.
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
    v2.0: ALL edges have positive forward returns → ALL are LONG signals.
    Contrarian patterns (trend_down, oversold) = mean reversion bounce = LONG.
    """

    name = "EDGE_DISCOVERY"

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

        # ALL edges have positive forward returns → only LONG scoring
        long_score, long_reasons = self._calculate_long_score(patterns, symbol)

        if long_score > 0.30:
            action = "LONG"
            confidence = min(0.85, long_score)
            reason = " | ".join(long_reasons[:3])

            if not config.ALLOW_LONG:
                return Signal(symbol=symbol, action="NONE", confidence=0.0,
                              reason="LONG disabled", strategy=self.name, price=price)

            logger.info(
                f"[EDGE_DISCOVERY] {symbol}: LONG conf={confidence:.2f} "
                f"score={long_score:.2f} - {reason}"
            )

            return Signal(
                symbol=symbol, action=action, confidence=confidence,
                reason=reason, strategy=self.name, price=price
            )

        return Signal(symbol=symbol, action="NONE", confidence=0.0,
                      reason="No strong edge pattern", strategy=self.name, price=price)

    def _detect_patterns(self, df: pd.DataFrame, symbol: str, regime: str) -> dict:
        """Detect all edge patterns in current candle"""
        patterns = {
            # === MEAN REVERSION / CONTRARIAN (en güçlü edge'ler!) ===
            "strong_momentum_down": detect_strong_momentum_down(df, -0.05).iloc[-1] if len(df) > 24 else False,
            "squeeze_breakout_down": detect_squeeze_breakout_down(df).iloc[-1] if len(df) > 20 else False,
            "low_volatility": detect_low_volatility(df).iloc[-1] if len(df) > 50 else False,
            "trend_down": detect_trend_down(df).iloc[-1] if len(df) > 50 else False,
            "trend_down_oversold": detect_trend_down_oversold(df, 35).iloc[-1] if len(df) > 50 else False,
            "rsi_oversold": detect_rsi_oversold(df, 40).iloc[-1] if len(df) > 14 else False,
            "bb_lower_high_volume": detect_bb_lower_high_volume(df).iloc[-1] if len(df) > 20 else False,
            "oversold_high_volume": detect_oversold_high_volume(df, 35).iloc[-1] if len(df) > 20 else False,
            "bb_near_lower": detect_bb_near_lower(df).iloc[-1] if len(df) > 20 else False,
            "price_below_ema50": detect_price_below_ema50(df).iloc[-1] if len(df) > 50 else False,
            "rsi_30_50": detect_rsi_30_50(df).iloc[-1] if len(df) > 14 else False,

            # === BREAKOUT / MOMENTUM ===
            "high_volatility": detect_high_volatility(df).iloc[-1] if len(df) > 50 else False,
            "momentum_continuation_up": detect_momentum_continuation_up(df).iloc[-1] if len(df) > 4 else False,
            "bb_upper_high_volume": detect_bb_upper_high_volume(df).iloc[-1] if len(df) > 20 else False,
            "strong_momentum_up": detect_strong_momentum_up(df, 0.05).iloc[-1] if len(df) > 24 else False,
            "ranging_bb_upper": detect_ranging_bb_upper(df).iloc[-1] if len(df) > 20 else False,

            # === COMPRESSION ===
            "bb_squeeze": detect_bb_squeeze(df).iloc[-1] if len(df) > 50 else False,
            "trend_mixed": detect_trend_mixed(df).iloc[-1] if len(df) > 50 else False,
        }

        # === COIN-SPECIFIC WEIGHTS (edge_top_validated.csv'den) ===
        coin_weights = self._get_coin_weights(symbol)
        patterns.update(coin_weights)

        # Regime adjustments — [v17] multiplier'lar hafifletildi (1.3→1.15, 1.2→1.10)
        if regime == "TREND_DOWN":
            # Contrarian bounce daha güçlü
            patterns["strong_momentum_down_weight"] = patterns.get("strong_momentum_down_weight", 1.0) * 1.15
            patterns["trend_down_oversold_weight"] = patterns.get("trend_down_oversold_weight", 1.0) * 1.10
            patterns["rsi_oversold_weight"] = patterns.get("rsi_oversold_weight", 1.0) * 1.10
        elif regime == "RANGING":
            patterns["ranging_bb_upper_weight"] = patterns.get("ranging_bb_upper_weight", 1.0) * 1.10
            patterns["bb_squeeze_weight"] = patterns.get("bb_squeeze_weight", 1.0) * 1.05
            patterns["low_volatility_weight"] = patterns.get("low_volatility_weight", 1.0) * 1.05
        elif regime == "TREND_UP":
            patterns["momentum_continuation_up_weight"] = patterns.get("momentum_continuation_up_weight", 1.0) * 1.10
            patterns["high_volatility_weight"] = patterns.get("high_volatility_weight", 1.0) * 1.05

        return patterns

    def _get_coin_weights(self, symbol: str) -> dict:
        """
        [v17] Coin-specific weights KALDIRILDI — overfitting kaynağıydı.
        Tüm coinler eşit ağırlık (1.0) kullanır.
        Ablation testi: Hiçbir bileşen tek başına overfitted değil,
        ama coin-specific tuning IS verisine uydurulmuş.
        """
        return {}

    def _calculate_long_score(self, patterns: dict, symbol: str) -> tuple:
        """
        Calculate LONG score. ALL edge patterns have positive AvgRet → ALL are LONG.

        Tier 1 (WR ≥ 75%): strong_mom_down bounce, squeeze_breakout bounce, low_vol breakout
        Tier 2 (WR 60-75%): high_vol, ranging_bb, rsi_oversold, bb_squeeze
        Tier 3 (WR 50-60%): trend_down, trend_mixed, price_below_ema50
        """
        score = 0.0
        reasons = []

        # ═══ TIER 1: CONTRARIAN BOUNCE (en güçlü edge'ler) ═══
        if patterns.get("strong_momentum_down", False):
            w = patterns.get("strong_momentum_down_weight", 1.0)
            add = 0.40 * w
            score += add
            reasons.append(f"MomBounce↑ ({add:.2f})")

        if patterns.get("squeeze_breakout_down", False):
            w = patterns.get("squeeze_breakout_down_weight", 1.0)
            add = 0.35 * w
            score += add
            reasons.append(f"SqzBounce↑ ({add:.2f})")

        if patterns.get("low_volatility", False):
            w = patterns.get("low_volatility_weight", 1.0)
            add = 0.30 * w
            score += add
            reasons.append(f"LowVol↑ ({add:.2f})")

        # ═══ TIER 2: MODERATE EDGE (WR 60-75%) ═══
        if patterns.get("high_volatility", False):
            w = patterns.get("high_volatility_weight", 1.0)
            add = 0.25 * w
            score += add
            reasons.append(f"HiVol↑ ({add:.2f})")

        if patterns.get("ranging_bb_upper", False):
            w = patterns.get("ranging_bb_upper_weight", 1.0)
            add = 0.20 * w
            score += add
            reasons.append(f"RangeBB↑ ({add:.2f})")

        if patterns.get("rsi_oversold", False):
            w = patterns.get("rsi_oversold_weight", 1.0)
            add = 0.20 * w
            score += add
            reasons.append(f"RSI-OS↑ ({add:.2f})")

        if patterns.get("bb_lower_high_volume", False):
            w = patterns.get("bb_lower_high_volume_weight", 1.0)
            add = 0.18 * w
            score += add
            reasons.append(f"BB↓vol↑ ({add:.2f})")

        if patterns.get("oversold_high_volume", False):
            w = patterns.get("oversold_high_volume_weight", 1.0)
            add = 0.18 * w
            score += add
            reasons.append(f"OSlVol↑ ({add:.2f})")

        if patterns.get("momentum_continuation_up", False):
            w = patterns.get("momentum_continuation_up_weight", 1.0)
            add = 0.20 * w
            score += add
            reasons.append(f"Mom↑ ({add:.2f})")

        if patterns.get("bb_squeeze", False):
            w = patterns.get("bb_squeeze_weight", 1.0)
            add = 0.15 * w
            score += add
            reasons.append(f"Squeeze ({add:.2f})")

        if patterns.get("bb_upper_high_volume", False):
            w = patterns.get("bb_upper_high_volume_weight", 1.0)
            add = 0.15 * w
            score += add
            reasons.append(f"BB↑vol ({add:.2f})")

        if patterns.get("bb_near_lower", False):
            w = patterns.get("bb_near_lower_weight", 1.0)
            add = 0.15 * w
            score += add
            reasons.append(f"BBnear↓ ({add:.2f})")

        # ═══ TIER 3: LOWER EDGE (WR 50-56%, large sample) ═══
        if patterns.get("trend_down", False):
            w = patterns.get("trend_down_weight", 1.0)
            add = 0.12 * w
            score += add
            reasons.append(f"T↓bounce ({add:.2f})")

        if patterns.get("trend_down_oversold", False):
            w = patterns.get("trend_down_oversold_weight", 1.0)
            add = 0.15 * w
            score += add
            reasons.append(f"T↓OS↑ ({add:.2f})")

        if patterns.get("trend_mixed", False):
            w = patterns.get("trend_mixed_weight", 1.0)
            add = 0.10 * w
            score += add
            reasons.append(f"Mixed ({add:.2f})")

        if patterns.get("rsi_30_50", False):
            w = patterns.get("rsi_30_50_weight", 1.0)
            add = 0.10 * w
            score += add
            reasons.append(f"RSI3050 ({add:.2f})")

        if patterns.get("price_below_ema50", False):
            w = patterns.get("price_below_ema50_weight", 1.0)
            add = 0.08 * w
            score += add
            reasons.append(f"<EMA50 ({add:.2f})")

        if patterns.get("strong_momentum_up", False):
            add = 0.15
            score += add
            reasons.append("Mom24↑")

        # Focus mode: Top 3 coinlerde confidence artışı
        if getattr(config, 'EDGE_DISCOVERY_FOCUS_MODE', False):
            if symbol in getattr(config, 'TOP_3_COINS', []):
                score *= 1.15
                if reasons:
                    reasons.append("FOCUS×1.15")

        return min(1.0, score), reasons
