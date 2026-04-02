"""
performance.py - Performance Metrics Tracker
================================================
Tracks win rate, PnL, Sharpe ratio, max drawdown.
Uses logger (not print) so everything goes to log file.
"""

import math
import logging
from typing import List

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Real-time performance metrics"""

    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.trade_pnls: List[float] = []
        self.max_equity = initial_balance
        self.max_drawdown_pct = 0.0
        self.max_drawdown_dollar = 0.0

    def record_trade(self, net_pnl: float):
        self.trade_pnls.append(net_pnl)

    def update_equity(self, equity: float):
        if equity > self.max_equity:
            self.max_equity = equity
        dd_dollar = self.max_equity - equity
        dd_pct = (dd_dollar / self.max_equity) * 100 if self.max_equity > 0 else 0
        if dd_pct > self.max_drawdown_pct:
            self.max_drawdown_pct = dd_pct
            self.max_drawdown_dollar = dd_dollar

    @property
    def total_trades(self) -> int:
        return len(self.trade_pnls)

    @property
    def wins(self) -> int:
        return sum(1 for p in self.trade_pnls if p > 0)

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0

    @property
    def total_pnl(self) -> float:
        return sum(self.trade_pnls) if self.trade_pnls else 0.0

    @property
    def sharpe(self) -> float:
        if len(self.trade_pnls) < 2:
            return 0.0
        avg = sum(self.trade_pnls) / len(self.trade_pnls)
        var = sum((p - avg) ** 2 for p in self.trade_pnls) / len(self.trade_pnls)
        std = math.sqrt(var) if var > 0 else 0.0
        return avg / std if std > 0 else 0.0

    def log_summary(self, tick_count: int):
        logger.info(
            f"[PERF @ {tick_count}] "
            f"Trades={self.total_trades} WinRate={self.win_rate:.1f}% "
            f"PnL=${self.total_pnl:.2f} Sharpe={self.sharpe:.2f} "
            f"MaxDD=${self.max_drawdown_dollar:.2f}({self.max_drawdown_pct:.1f}%)"
        )
