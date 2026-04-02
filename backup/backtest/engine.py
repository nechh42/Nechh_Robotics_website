"""
backtest/engine.py - Historical Backtest Engine
==================================================
Tests strategies on historical kline data from Binance.
Downloads data, runs strategies, calculates PnL.

Usage:
  python -m backtest.engine --symbol BTCUSDT --days 30
"""

import logging
import sys
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from strategies.indicators import calc_rsi, calc_ema, calc_bollinger, calc_atr, calc_vwap
from strategies.regime import detect_regime
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from engine.voting import combine_signals

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    pnl: float
    commission: float
    net_pnl: float
    reason: str
    strategy: str


@dataclass
class BacktestResult:
    symbol: str
    period: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    avg_trade_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)


def fetch_klines(symbol: str, interval: str = "1h", days: int = 30) -> Optional[pd.DataFrame]:
    """Fetch historical klines from Binance REST API"""
    url = "https://api.binance.com/api/v3/klines"
    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)

    all_data = []
    current = start_ms

    while current < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "limit": 1000,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)
            current = data[-1][0] + 1
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            break

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades_count",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def run_backtest(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    days: int = 30,
    initial_balance: float = 10000.0,
    position_pct: float = 0.05,
    sl_pct: float = 0.015,
    tp_pct: float = 0.03,
    commission_rate: float = 0.001,
) -> BacktestResult:
    """
    Run backtest on historical data.

    Strategy: same as live system (RSI + Momentum + VWAP with regime voting)
    """
    print(f"\n{'='*60}")
    print(f"BACKTEST: {symbol} | {interval} | {days} days")
    print(f"Balance: ${initial_balance:,.2f} | SL: {sl_pct*100}% | TP: {tp_pct*100}%")
    print(f"{'='*60}")

    # Fetch data
    print(f"Fetching {days} days of {interval} data...")
    df = fetch_klines(symbol, interval, days)
    if df is None or len(df) < 50:
        print("ERROR: Insufficient data")
        return BacktestResult(symbol=symbol, period=f"{days}d")

    print(f"Got {len(df)} candles ({df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]})")

    # Init strategies
    rsi_strat = RSIReversionStrategy()
    mom_strat = MomentumStrategy()
    vwap_strat = VWAPReversionStrategy()

    # State
    balance = initial_balance
    position = None  # {side, entry_price, size, sl, tp, strategy, entry_idx}
    trades = []
    equity_curve = [initial_balance]

    # Walk through candles
    for i in range(50, len(df)):
        window = df.iloc[max(0, i - 100):i + 1].copy().reset_index(drop=True)
        price = window["close"].iloc[-1]
        timestamp = str(df["timestamp"].iloc[i])

        # Check SL/TP if in position
        if position is not None:
            hit = False
            if position["side"] == "LONG":
                if price <= position["sl"]:
                    hit = True
                    reason = "STOP-LOSS"
                elif price >= position["tp"]:
                    hit = True
                    reason = "TAKE-PROFIT"
            else:
                if price >= position["sl"]:
                    hit = True
                    reason = "STOP-LOSS"
                elif price <= position["tp"]:
                    hit = True
                    reason = "TAKE-PROFIT"

            if hit:
                # Close position
                if position["side"] == "LONG":
                    gross = (price - position["entry_price"]) * position["size"]
                else:
                    gross = (position["entry_price"] - price) * position["size"]

                comm = price * position["size"] * commission_rate
                net = gross - comm
                balance += net

                trades.append(BacktestTrade(
                    symbol=symbol, side=position["side"],
                    entry_price=position["entry_price"], exit_price=price,
                    entry_time=position["entry_time"], exit_time=timestamp,
                    pnl=gross, commission=comm, net_pnl=net,
                    reason=reason, strategy=position["strategy"],
                ))
                position = None

        # Evaluate strategies (only if no position)
        if position is None:
            regime = detect_regime(window)

            signals = []
            for strat in [rsi_strat, mom_strat, vwap_strat]:
                try:
                    sig = strat.evaluate(window, symbol, regime)
                    signals.append(sig)
                except Exception:
                    pass

            combined = combine_signals(signals, regime)

            if combined.action in ("LONG", "SHORT"):
                size = (balance * position_pct) / price
                entry_comm = price * size * commission_rate
                balance -= entry_comm

                if combined.action == "LONG":
                    sl = price * (1 - sl_pct)
                    tp = price * (1 + tp_pct)
                else:
                    sl = price * (1 + sl_pct)
                    tp = price * (1 - tp_pct)

                position = {
                    "side": combined.action,
                    "entry_price": price,
                    "size": size,
                    "sl": sl, "tp": tp,
                    "strategy": combined.strategy,
                    "entry_time": timestamp,
                }

        equity_curve.append(balance)

    # Close any remaining position at last price
    if position is not None:
        price = df["close"].iloc[-1]
        if position["side"] == "LONG":
            gross = (price - position["entry_price"]) * position["size"]
        else:
            gross = (position["entry_price"] - price) * position["size"]
        comm = price * position["size"] * commission_rate
        net = gross - comm
        balance += net
        trades.append(BacktestTrade(
            symbol=symbol, side=position["side"],
            entry_price=position["entry_price"], exit_price=price,
            entry_time=position["entry_time"], exit_time=str(df["timestamp"].iloc[-1]),
            pnl=gross, commission=comm, net_pnl=net,
            reason="END_OF_DATA", strategy=position["strategy"],
        ))

    # Calculate results
    result = BacktestResult(symbol=symbol, period=f"{days}d")
    result.total_trades = len(trades)
    result.trades = trades

    if trades:
        pnls = [t.net_pnl for t in trades]
        result.wins = sum(1 for p in pnls if p > 0)
        result.losses = sum(1 for p in pnls if p <= 0)
        result.win_rate = result.wins / len(pnls) * 100
        result.total_pnl = sum(pnls)
        result.total_commission = sum(t.commission for t in trades)
        result.avg_trade_pnl = np.mean(pnls)
        result.best_trade = max(pnls)
        result.worst_trade = min(pnls)

        if len(pnls) >= 2:
            avg = np.mean(pnls)
            std = np.std(pnls)
            result.sharpe = avg / std if std > 0 else 0

        # Max drawdown
        peak = initial_balance
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown = max_dd * 100

    # Print results
    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS: {symbol} ({days} days)")
    print(f"{'='*60}")
    print(f"  Trades:     {result.total_trades}")
    print(f"  Wins:       {result.wins}")
    print(f"  Losses:     {result.losses}")
    print(f"  Win Rate:   {result.win_rate:.1f}%")
    print(f"  Total PnL:  ${result.total_pnl:.2f}")
    print(f"  Commission: ${result.total_commission:.2f}")
    print(f"  Avg Trade:  ${result.avg_trade_pnl:.2f}")
    print(f"  Best Trade: ${result.best_trade:.2f}")
    print(f"  Worst Trade:${result.worst_trade:.2f}")
    print(f"  Max DD:     {result.max_drawdown:.1f}%")
    print(f"  Sharpe:     {result.sharpe:.2f}")
    print(f"  Final Bal:  ${balance:,.2f}")
    print(f"{'='*60}")

    return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="War Machine Backtest")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    result = run_backtest(args.symbol, args.interval, args.days)

    # Run for multiple symbols
    if args.symbol == "ALL":
        for sym in config.SYMBOLS:
            run_backtest(sym, args.interval, args.days)
