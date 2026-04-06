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

    Args:
        pos: Open position
        price: Current market price

    Returns:
        Close reason string if exit triggered, None otherwise.
        Also updates trailing stop state on the position object.
    """
    symbol = pos.symbol

    # ─── BREAKEVEN STOP ────────────────────────────────
    # Fiyat +1×ATR kâra geçtiyse, SL → entry price (asla zarara dönmesin)
    if not getattr(pos, '_breakeven_applied', False):
        be_trigger = getattr(config, 'BREAKEVEN_ATR_TRIGGER', 0)
        if be_trigger > 0 and getattr(pos, '_entry_atr', 0) > 0:
            atr_dist = pos._entry_atr * be_trigger
            if pos.side == "LONG":
                if price >= pos.entry_price + atr_dist:
                    old_sl = pos.stop_loss
                    pos.stop_loss = max(pos.stop_loss, pos.entry_price)
                    pos._breakeven_applied = True
                    logger.info(f"[BREAKEVEN] {symbol}: SL ${old_sl:.2f} → ${pos.stop_loss:.2f} (entry)")
            else:  # SHORT
                if price <= pos.entry_price - atr_dist:
                    old_sl = pos.stop_loss
                    pos.stop_loss = min(pos.stop_loss, pos.entry_price)
                    pos._breakeven_applied = True
                    logger.info(f"[BREAKEVEN] {symbol}: SL ${old_sl:.2f} → ${pos.stop_loss:.2f} (entry)")

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

    # ─── CHECK PARTIAL TP (TP1) ─────────────────────────
    if (getattr(config, 'PARTIAL_TP_ENABLED', False)
            and not getattr(pos, '_partial_closed', False)
            and getattr(pos, 'take_profit_1', 0) > 0):
        if pos.side == "LONG" and price >= pos.take_profit_1:
            return f"PARTIAL-TP1: ${price:.2f} >= TP1 ${pos.take_profit_1:.2f}"
        if pos.side == "SHORT" and price <= pos.take_profit_1:
            return f"PARTIAL-TP1: ${price:.2f} <= TP1 ${pos.take_profit_1:.2f}"

    # ─── CHECK TAKE PROFIT (TP2 — full close) ──────────
    if pos.side == "LONG" and price >= pos.take_profit:
        return f"TAKE-PROFIT: ${price:.2f} >= TP ${pos.take_profit:.2f}"

    if pos.side == "SHORT" and price <= pos.take_profit:
        return f"TAKE-PROFIT: ${price:.2f} <= TP ${pos.take_profit:.2f}"

    return None
