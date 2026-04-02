"""
paper.py - Paper Trading Execution
=====================================
Simulates order execution at current market price.
No real money, no real orders. Safe for testing.
"""

import logging
from typing import Dict, Optional

import config
from engine.state import TradingState, ClosedTrade

logger = logging.getLogger(__name__)


class PaperExecutor:
    """Paper trading execution engine"""

    def __init__(self, state: TradingState):
        self.state = state

    # Realistic slippage: 0.15% total (spread + slippage)
    SLIPPAGE_PCT = 0.0015

    def open_order(self, params: dict) -> Dict:
        """
        Open a new position with simulated slippage.
        Entry price worsened by SLIPPAGE_PCT to prevent fake profit.
        """
        try:
            price = params["price"]
            slip = price * self.SLIPPAGE_PCT

            # Slippage worsens entry: LONG buys higher, SHORT sells lower
            if params["action"] == "LONG":
                price += slip
            else:
                price -= slip

            pos = self.state.open_position(
                symbol=params["symbol"],
                side=params["action"],
                size=params["size"],
                entry_price=price,
                stop_loss=params["stop_loss"],
                take_profit=params["take_profit"],
                strategy=params.get("strategy", ""),
            )
            return {"status": "FILLED", "position": pos}

        except Exception as e:
            logger.error(f"[EXEC] Open failed: {e}")
            return {"status": "REJECTED", "reason": str(e)}

    def close_order(self, symbol: str, price: float, reason: str = "") -> Optional[ClosedTrade]:
        """
        Close an existing position.

        Returns:
            ClosedTrade if successful, None if no position
        """
        trade = self.state.close_position(symbol, price, reason)
        if trade:
            logger.info(
                f"[EXEC] CLOSED {trade.side} {symbol}: "
                f"${trade.entry_price:.2f}->${trade.exit_price:.2f} "
                f"net=${trade.net_pnl:.4f} ({reason})"
            )
        return trade
