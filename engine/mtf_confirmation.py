"""
mtf_confirmation.py - Multi-Timeframe Confirmation Layer
============================================================
4h trend → 1h entry → 15m trigger confirmation.

When 4h voting generates a signal, this layer checks 15m data
for micro-level confirmation before trade execution.

Confirmation criteria (LONG):
  1. RSI(14) > 40 on 15m (not deeply oversold on micro level)
  2. Price above EMA9 on 15m (short-term up momentum)
  3. Last 3 candles: at least 2 green (buying pressure)
  4. Volume above average (no low-liquidity entries)

Confirmation criteria (SHORT):
  1. RSI(14) < 60 on 15m
  2. Price below EMA9 on 15m
  3. Last 3 candles: at least 2 red
  4. Volume above average

If confirmation fails → signal is queued for next 15m check
(max 4 retries = 1 hour, then signal expires).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import pandas as pd
import numpy as np

import config
from strategies.indicators import calc_rsi, calc_ema

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════

MTF_ENABLED = True                    # Aktif/Pasif
MTF_MAX_RETRIES = 4                   # Max 4×15m = 1 saat bekleme
MTF_MIN_CANDLES = 20                  # Minimum 15m candle for analysis
MTF_RSI_LONG_MIN = 40                 # LONG: RSI > 40
MTF_RSI_SHORT_MAX = 60               # SHORT: RSI < 60
MTF_GREEN_CANDLE_MIN = 2             # Last 3'ten minimum yeşil
MTF_VOLUME_RATIO_MIN = 0.8          # Ortalama volume'un min %80'i


from dataclasses import dataclass


@dataclass
class PendingSignal:
    """Signal waiting for 15m confirmation"""
    symbol: str
    action: str  # LONG or SHORT
    confidence: float
    strategy: str
    regime: str
    params: dict  # Pre-trade risk approved params
    created_at: datetime
    retries: int = 0
    max_retries: int = MTF_MAX_RETRIES


class MTFConfirmation:
    """
    Multi-Timeframe Confirmation Gate.
    Holds pending signals until 15m confirms direction.
    """

    def __init__(self):
        self.pending: Dict[str, PendingSignal] = {}  # symbol → pending signal

    def add_pending(self, symbol: str, action: str, confidence: float,
                    strategy: str, regime: str, params: dict):
        """Add a new signal waiting for 15m confirmation"""
        if not MTF_ENABLED:
            return  # Disabled, skip

        self.pending[symbol] = PendingSignal(
            symbol=symbol, action=action, confidence=confidence,
            strategy=strategy, regime=regime, params=params,
            created_at=datetime.now(),
        )
        logger.info(
            f"[MTF] {symbol}: {action} signal QUEUED for 15m confirmation "
            f"(conf={confidence:.2f}, regime={regime})"
        )

    def check_confirmation(self, symbol: str, df_15m: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if 15m data confirms the pending signal.

        Returns:
            (confirmed: bool, reason: str)
        """
        if symbol not in self.pending:
            return False, "No pending signal"

        signal = self.pending[symbol]

        if df_15m is None or len(df_15m) < MTF_MIN_CANDLES:
            return False, "Insufficient 15m data"

        # Increment retry counter
        signal.retries += 1

        # Expired?
        if signal.retries > signal.max_retries:
            logger.info(f"[MTF] {symbol}: Signal EXPIRED after {signal.retries} retries")
            del self.pending[symbol]
            return False, "Signal expired"

        # ─── CALCULATE 15m INDICATORS ─────────────────
        close = df_15m["close"]
        volume = df_15m["volume"]

        rsi = calc_rsi(close, period=14)
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50.0

        ema9 = calc_ema(close, 9)
        current_ema9 = ema9.iloc[-1] if not ema9.empty else close.iloc[-1]

        current_price = close.iloc[-1]

        # Last 3 candles green/red count
        last_3_open = df_15m["open"].iloc[-3:]
        last_3_close = df_15m["close"].iloc[-3:]
        green_count = sum(1 for o, c in zip(last_3_open, last_3_close) if c > o)
        red_count = 3 - green_count

        # Volume ratio
        avg_volume = volume.iloc[-20:].mean()
        current_volume = volume.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # ─── CONFIRMATION LOGIC ───────────────────────
        reasons = []
        score = 0

        if signal.action == "LONG":
            # 1. RSI check
            if current_rsi >= MTF_RSI_LONG_MIN:
                score += 1
                reasons.append(f"RSI={current_rsi:.0f}≥{MTF_RSI_LONG_MIN}")
            else:
                reasons.append(f"RSI={current_rsi:.0f}<{MTF_RSI_LONG_MIN}✗")

            # 2. Price above EMA9
            if current_price > current_ema9:
                score += 1
                reasons.append("Price>EMA9✓")
            else:
                reasons.append("Price<EMA9✗")

            # 3. Green candles
            if green_count >= MTF_GREEN_CANDLE_MIN:
                score += 1
                reasons.append(f"Green={green_count}/3✓")
            else:
                reasons.append(f"Green={green_count}/3✗")

            # 4. Volume
            if volume_ratio >= MTF_VOLUME_RATIO_MIN:
                score += 1
                reasons.append(f"Vol={volume_ratio:.1f}x✓")
            else:
                reasons.append(f"Vol={volume_ratio:.1f}x✗")

        elif signal.action == "SHORT":
            # 1. RSI check
            if current_rsi <= MTF_RSI_SHORT_MAX:
                score += 1
                reasons.append(f"RSI={current_rsi:.0f}≤{MTF_RSI_SHORT_MAX}")
            else:
                reasons.append(f"RSI={current_rsi:.0f}>{MTF_RSI_SHORT_MAX}✗")

            # 2. Price below EMA9
            if current_price < current_ema9:
                score += 1
                reasons.append("Price<EMA9✓")
            else:
                reasons.append("Price>EMA9✗")

            # 3. Red candles
            if red_count >= MTF_GREEN_CANDLE_MIN:
                score += 1
                reasons.append(f"Red={red_count}/3✓")
            else:
                reasons.append(f"Red={red_count}/3✗")

            # 4. Volume
            if volume_ratio >= MTF_VOLUME_RATIO_MIN:
                score += 1
                reasons.append(f"Vol={volume_ratio:.1f}x✓")
            else:
                reasons.append(f"Vol={volume_ratio:.1f}x✗")

        confirmed = score >= 3  # At least 3 out of 4 criteria

        reason_str = " | ".join(reasons)

        if confirmed:
            logger.info(
                f"[MTF] {symbol}: {signal.action} CONFIRMED on 15m "
                f"({score}/4) retry={signal.retries} - {reason_str}"
            )
            del self.pending[symbol]
        else:
            logger.info(
                f"[MTF] {symbol}: {signal.action} NOT confirmed "
                f"({score}/4) retry={signal.retries}/{signal.max_retries} - {reason_str}"
            )

        return confirmed, reason_str

    def get_pending_params(self, symbol: str) -> Optional[dict]:
        """Get params for a confirmed signal (before deletion)"""
        if symbol in self.pending:
            return self.pending[symbol].params
        return None

    def has_pending(self, symbol: str) -> bool:
        """Check if symbol has a pending signal"""
        return symbol in self.pending

    def clear_expired(self):
        """Remove all expired signals"""
        expired = [
            sym for sym, sig in self.pending.items()
            if sig.retries > sig.max_retries
        ]
        for sym in expired:
            del self.pending[sym]
        if expired:
            logger.info(f"[MTF] Cleared {len(expired)} expired signals")

    def get_status(self) -> dict:
        """Return status for monitoring"""
        return {
            "pending_count": len(self.pending),
            "pending_symbols": list(self.pending.keys()),
            "details": {
                sym: {
                    "action": sig.action,
                    "retries": sig.retries,
                    "max_retries": sig.max_retries,
                    "confidence": sig.confidence,
                }
                for sym, sig in self.pending.items()
            },
        }
