"""
state.py - Single Source of Truth
====================================
All trading state lives here. Thread-safe.
Positions, balance, equity - nothing else touches these.
"""

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import config

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Open position"""
    symbol: str
    side: str           # LONG or SHORT
    size: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    strategy: str = ""
    trailing_active: bool = False
    trailing_peak: float = 0.0
    unrealized_pnl: float = 0.0
    # MFE/MAE tracking (quant analysis)
    mfe: float = 0.0    # Max Favorable Excursion (best profit %)
    mae: float = 0.0    # Max Adverse Excursion (worst loss %)
    # Breakeven stop
    _entry_atr: float = 0.0
    _breakeven_applied: bool = False
    # Funding fee tracking
    _total_funding_paid: float = 0.0
    _last_funding_time: datetime = None
    # Partial TP
    take_profit_1: float = 0.0     # TP1 = yarı mesafe
    _partial_closed: bool = False  # TP1 tetiklendi mi?
    # Smart Exit (regime change)
    _entry_regime: str = ""        # Pozisyon açıldığındaki regime

    def update_pnl(self, price: float):
        if self.side == "LONG":
            self.unrealized_pnl = (price - self.entry_price) * self.size
            # Track MFE/MAE
            pnl_pct = (price - self.entry_price) / self.entry_price
            if pnl_pct > self.mfe:
                self.mfe = pnl_pct
            if pnl_pct < self.mae:
                self.mae = pnl_pct
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size
            # Track MFE/MAE
            pnl_pct = (self.entry_price - price) / self.entry_price
            if pnl_pct > self.mfe:
                self.mfe = pnl_pct
            if pnl_pct < self.mae:
                self.mae = pnl_pct


@dataclass
class ClosedTrade:
    """Completed trade record"""
    symbol: str
    side: str
    size: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    commission: float
    net_pnl: float
    strategy: str
    reason: str
    # MFE/MAE (quant analysis)
    mfe: float = 0.0    # Max Favorable Excursion (%)
    mae: float = 0.0    # Max Adverse Excursion (%)


class TradingState:
    """
    Thread-safe state container.
    All balance/position mutations go through here.
    """

    def __init__(self, initial_balance: float = None):
        self._lock = Lock()
        self.balance: float = initial_balance or config.INITIAL_BALANCE
        self.initial_balance: float = self.balance
        self.equity: float = self.balance
        self.positions: Dict[str, Position] = {}
        self.trades: List[ClosedTrade] = []
        self.total_commission: float = 0.0

        # Watchdog timestamps
        self.last_tick_time: Optional[datetime] = None
        self.last_candle_time: Optional[datetime] = None

    def update_price(self, symbol: str, price: float):
        """Update position PnL and equity on new price"""
        with self._lock:
            if symbol in self.positions:
                self.positions[symbol].update_pnl(price)
            self._recalc_equity()
            self.last_tick_time = datetime.now()

    def open_position(self, symbol: str, side: str, size: float,
                      entry_price: float, stop_loss: float, take_profit: float,
                      strategy: str = "") -> Position:
        """Open new position, deduct entry commission"""
        with self._lock:
            commission = entry_price * size * config.COMMISSION_RATE
            self.balance -= commission
            self.total_commission += commission

            pos = Position(
                symbol=symbol, side=side, size=size,
                entry_price=entry_price, entry_time=datetime.now(),
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=strategy,
            )
            self.positions[symbol] = pos
            self._recalc_equity()

            logger.info(
                f"[STATE] OPENED {side} {symbol}: size={size:.6f} @ ${entry_price:.2f} "
                f"SL=${stop_loss:.2f} TP=${take_profit:.2f} comm=${commission:.4f}"
            )
            return pos

    def close_position(self, symbol: str, exit_price: float, reason: str = "") -> Optional[ClosedTrade]:
        """Close position, calculate PnL, update balance"""
        with self._lock:
            if symbol not in self.positions:
                return None

            pos = self.positions[symbol]

            # Gross PnL
            if pos.side == "LONG":
                gross_pnl = (exit_price - pos.entry_price) * pos.size
            else:
                gross_pnl = (pos.entry_price - exit_price) * pos.size

            # Exit commission
            exit_commission = exit_price * pos.size * config.COMMISSION_RATE
            net_pnl = gross_pnl - exit_commission

            # Update balance
            self.balance += net_pnl
            self.total_commission += exit_commission

            # Create trade record
            trade = ClosedTrade(
                symbol=symbol, side=pos.side, size=pos.size,
                entry_price=pos.entry_price, exit_price=exit_price,
                entry_time=pos.entry_time, exit_time=datetime.now(),
                gross_pnl=gross_pnl, commission=exit_commission,
                net_pnl=net_pnl, strategy=pos.strategy, reason=reason,
                mfe=pos.mfe, mae=pos.mae,  # Save MFE/MAE for analysis
            )
            self.trades.append(trade)

            # Remove position
            del self.positions[symbol]
            self._recalc_equity()

            logger.info(
                f"[STATE] CLOSED {pos.side} {symbol}: "
                f"${pos.entry_price:.2f} -> ${exit_price:.2f} "
                f"gross=${gross_pnl:.4f} comm=${exit_commission:.4f} net=${net_pnl:.4f} "
                f"reason={reason}"
            )
            return trade

    def partial_close_position(self, symbol: str, exit_price: float, close_pct: float,
                               reason: str = "") -> Optional[ClosedTrade]:
        """Partially close a position (e.g. 50% at TP1)"""
        with self._lock:
            if symbol not in self.positions:
                return None

            pos = self.positions[symbol]
            close_size = pos.size * close_pct

            # Gross PnL for closed portion
            if pos.side == "LONG":
                gross_pnl = (exit_price - pos.entry_price) * close_size
            else:
                gross_pnl = (pos.entry_price - exit_price) * close_size

            # Commission on closed portion
            exit_commission = exit_price * close_size * config.COMMISSION_RATE
            net_pnl = gross_pnl - exit_commission

            # Update balance
            self.balance += net_pnl
            self.total_commission += exit_commission

            # Reduce position size (keep position open with remaining)
            pos.size -= close_size
            pos._partial_closed = True

            # Create trade record for partial close
            trade = ClosedTrade(
                symbol=symbol, side=pos.side, size=close_size,
                entry_price=pos.entry_price, exit_price=exit_price,
                entry_time=pos.entry_time, exit_time=datetime.now(),
                gross_pnl=gross_pnl, commission=exit_commission,
                net_pnl=net_pnl, strategy=pos.strategy, reason=reason,
                mfe=pos.mfe, mae=pos.mae,
            )
            self.trades.append(trade)
            self._recalc_equity()

            logger.info(
                f"[STATE] PARTIAL CLOSE {pos.side} {symbol}: "
                f"{close_pct*100:.0f}% closed @ ${exit_price:.2f} "
                f"net=${net_pnl:.4f} | remaining size={pos.size:.6f}"
            )
            return trade

    def restore_position(self, symbol: str, pos_data: Dict):
        """Restore position from database (after restart)"""
        with self._lock:
            pos = Position(
                symbol=symbol,
                side=pos_data["side"],
                size=pos_data["size"],
                entry_price=pos_data["entry_price"],
                entry_time=datetime.fromisoformat(pos_data["entry_time"]),
                stop_loss=pos_data["stop_loss"],
                take_profit=pos_data["take_profit"],
                strategy=pos_data.get("strategy", ""),
                trailing_active=pos_data.get("trailing_active", False),
                trailing_peak=pos_data.get("trailing_peak", 0.0),
            )
            pos._entry_atr = pos_data.get("entry_atr", 0.0)
            pos._breakeven_applied = pos_data.get("breakeven_applied", False)
            pos._partial_closed = pos_data.get("partial_closed", False)
            pos.take_profit_1 = pos_data.get("take_profit_1", 0.0)
            pos._entry_regime = pos_data.get("entry_regime", "")
            self.positions[symbol] = pos
            logger.info(f"[STATE] Restored position: {symbol} {pos_data['side']}")

    def _recalc_equity(self):
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self.equity = self.balance + unrealized

    def get_status(self) -> Dict:
        with self._lock:
            total = len(self.trades)
            wins = sum(1 for t in self.trades if t.net_pnl > 0)
            return {
                "balance": self.balance,
                "equity": self.equity,
                "total_trades": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": (wins / total * 100) if total > 0 else 0.0,
                "total_commission": self.total_commission,
                "num_positions": len(self.positions),
                "total_pnl": self.equity - self.initial_balance,
            }
