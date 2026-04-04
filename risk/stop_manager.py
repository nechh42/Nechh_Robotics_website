"""
stop_manager.py - Stop Loss / Take Profit / Trailing Stop
============================================================
Checks every tick if SL, TP, or trailing stop is hit.
Returns close reason if position should be closed.
"""

import logging
from typing import Optional

import config
from engine.state import Position

logger = logging.getLogger(__name__)


def check_exit(pos: Position, price: float) -> Optional[str]:
    """
    Check if position should be closed based on current price.

    Exit rules:
      1. Stop Loss
      2. Take Profit
      3. Trailing Stop (if activated)
      4. Time-based: 4h duration (16*3600 seconds)

    Args:
        pos: Open position
        price: Current market price

    Returns:
        Close reason string if exit triggered, None otherwise.
        Also updates trailing stop state on the position object.
    """
    symbol = pos.symbol
    
    # ─── TIME-BASED EXIT (4h duration) ───────────────
    if pos.entry_time:
        from datetime import datetime
        duration_sec = (datetime.now() - pos.entry_time).total_seconds()
        max_duration_sec = 4 * 3600  # 4 hours
        if duration_sec > max_duration_sec:
            return f"TIME-BASED EXIT: Position held {duration_sec/3600:.1f}h (max 4h)"

    # ─── TRAILING STOP UPDATE ───────────────────────────
    if pos.trailing_active:
        if pos.side == "LONG":
            if price > pos.trailing_peak:
                pos.trailing_peak = price
                new_sl = price * (1 - config.TRAILING_STOP_DISTANCE)
                if new_sl > pos.stop_loss:
                    pos.stop_loss = new_sl
        else:  # SHORT
            if price < pos.trailing_peak:
                pos.trailing_peak = price
                new_sl = price * (1 + config.TRAILING_STOP_DISTANCE)
                if new_sl < pos.stop_loss:
                    pos.stop_loss = new_sl

    # ─── ACTIVATE TRAILING ──────────────────────────────
    if not pos.trailing_active:
        if pos.side == "LONG":
            profit_pct = (price - pos.entry_price) / pos.entry_price
            if profit_pct >= config.TRAILING_STOP_ACTIVATE:
                pos.trailing_active = True
                pos.trailing_peak = price
                logger.info(f"[TRAIL] {symbol}: Trailing activated at ${price:.2f} (+{profit_pct*100:.2f}%)")
        else:  # SHORT
            profit_pct = (pos.entry_price - price) / pos.entry_price
            if profit_pct >= config.TRAILING_STOP_ACTIVATE:
                pos.trailing_active = True
                pos.trailing_peak = price
                logger.info(f"[TRAIL] {symbol}: Trailing activated at ${price:.2f} (+{profit_pct*100:.2f}%)")

    # ─── CHECK STOP LOSS ────────────────────────────────
    if pos.side == "LONG" and price <= pos.stop_loss:
        return f"STOP-LOSS: ${price:.2f} <= SL ${pos.stop_loss:.2f}"

    if pos.side == "SHORT" and price >= pos.stop_loss:
        return f"STOP-LOSS: ${price:.2f} >= SL ${pos.stop_loss:.2f}"

    # ─── CHECK TAKE PROFIT ──────────────────────────────
    if pos.side == "LONG" and price >= pos.take_profit:
        return f"TAKE-PROFIT: ${price:.2f} >= TP ${pos.take_profit:.2f}"

    if pos.side == "SHORT" and price <= pos.take_profit:
        return f"TAKE-PROFIT: ${price:.2f} <= TP ${pos.take_profit:.2f}"

    return None
