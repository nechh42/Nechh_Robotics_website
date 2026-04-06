"""
backtest_v3.py - War Machine Backtest Engine v3.0
====================================================
Live sistemi birebir simüle eder. Tüm v15.3 özellikleri dahil:
  - Regime detection + Dynamic R:R
  - 4 strategy voting (RSI, Momentum, VWAP, EdgeDiscovery)
  - Pre-trade risk (regime filter, notional cap, volatility sizing)
  - Partial TP (TP1 @ 50% mesafe → %50 kapat → SL→breakeven)
  - Breakeven stop (+1×ATR → SL to entry)
  - Smart exit (regime change → kârda kapat, zararda TP daralt)
  - Funding fee (0.01% per 8h)
  - Commission (0.1%)
  - MFE/MAE analizi per trade
  - Trailing stop

Kullanım:
  python -m backtest.backtest_v3 --days 60
  python -m backtest.backtest_v3 --symbol BTCUSDT --days 30
  python -m backtest.backtest_v3 --all --days 90
"""

import sys
import os
import json
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from strategies.regime import detect_regime
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.edge_discovery import EdgeDiscoveryStrategy
from strategies.indicators import calc_atr, calc_rsi
from engine.voting import combine_signals

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════

@dataclass
class BTPosition:
    """Simulated position matching live Position"""
    symbol: str
    side: str
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    take_profit_1: float
    entry_time: str
    strategy: str
    entry_regime: str
    entry_atr: float
    original_entry_regime: str = ""  # Never modified by Smart Exit
    breakeven_applied: bool = False
    partial_closed: bool = False
    trailing_active: bool = False
    trailing_peak: float = 0.0
    # MFE/MAE
    max_favorable: float = 0.0    # Maximum Favorable Excursion (price)
    max_adverse: float = 0.0      # Maximum Adverse Excursion (price)
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    candles_held: int = 0
    funding_paid: float = 0.0


@dataclass
class BTTrade:
    """Completed trade with full analytics"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    size: float
    gross_pnl: float
    commission: float
    funding_fee: float
    net_pnl: float
    reason: str
    strategy: str
    entry_regime: str
    exit_regime: str
    mfe_pct: float       # Max favorable move %
    mae_pct: float       # Max adverse move %
    candles_held: int
    entry_atr: float
    sl_distance: float
    tp_distance: float
    rr_ratio: float


@dataclass
class BTResult:
    """Backtest results with full analytics"""
    period: str
    symbols_tested: List[str] = field(default_factory=list)
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    total_funding: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_candles: float = 0.0
    avg_mfe: float = 0.0
    avg_mae: float = 0.0
    final_balance: float = 0.0
    trades: List[BTTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    # Per-regime stats
    regime_stats: Dict = field(default_factory=dict)
    # Per-strategy stats
    strategy_stats: Dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════

def fetch_klines(symbol: str, interval: str = "4h", days: int = 60) -> Optional[pd.DataFrame]:
    """Fetch historical klines from Binance"""
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
            logger.error(f"Fetch error {symbol}: {e}")
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


# ═══════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════

class BacktestV3:
    """
    Walk-forward backtest matching live system behavior.
    Processes 4h candles sequentially, applies all v15.3 features.
    """

    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, BTPosition] = {}
        self.trades: List[BTTrade] = []
        self.equity_curve: List[float] = [initial_balance]

        # Strategies (same as live)
        self.strategies = [
            RSIReversionStrategy(),
            MomentumStrategy(),
            VWAPReversionStrategy(),
            EdgeDiscoveryStrategy(),
        ]

        # Daily counters
        self._daily_trades = 0
        self._daily_loss = 0.0
        self._current_day = None
        self._funding_counter = 0  # candle counter for funding

    def run(self, symbols: List[str] = None, days: int = 60,
            interval: str = "4h") -> BTResult:
        """Run full backtest"""
        symbols = symbols or config.SYMBOLS
        result = BTResult(period=f"{days}d", symbols_tested=symbols)

        print(f"\n{'='*70}")
        print(f"WAR MACHINE BACKTEST v3.0")
        print(f"{'='*70}")
        print(f"Balance: ${self.initial_balance:,.2f} | Days: {days}")
        print(f"Symbols: {len(symbols)} | Interval: {interval}")
        print(f"Features: DynamicRR + PartialTP + Breakeven + SmartExit + Funding")
        print(f"{'='*70}")

        # Fetch all data first
        data_map: Dict[str, pd.DataFrame] = {}
        for sym in symbols:
            print(f"  Fetching {sym}...", end=" ", flush=True)
            df = fetch_klines(sym, interval, days + 10)  # extra for warmup
            if df is not None and len(df) >= 50:
                data_map[sym] = df
                print(f"{len(df)} candles ✓")
            else:
                print("SKIP (insufficient data)")

        if not data_map:
            print("ERROR: No data fetched")
            return result

        # Find common time range
        all_times = set()
        for sym, df in data_map.items():
            all_times.update(df["open_time"].tolist())
        sorted_times = sorted(all_times)

        print(f"\nTotal unique timestamps: {len(sorted_times)}")
        print(f"Walking through candles...\n")

        # Walk forward candle by candle
        for t_idx, timestamp in enumerate(sorted_times):
            # Day reset
            dt = datetime.fromtimestamp(timestamp / 1000)
            if self._current_day != dt.date():
                self._daily_trades = 0
                self._daily_loss = 0.0
                self._current_day = dt.date()

            # Process each symbol at this timestamp
            for sym in list(data_map.keys()):
                df = data_map[sym]
                mask = df["open_time"] <= timestamp
                df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)

                if len(df_window) < 50:
                    continue

                price = df_window["close"].iloc[-1]
                high = df_window["high"].iloc[-1]
                low = df_window["low"].iloc[-1]
                ts_str = str(df_window["timestamp"].iloc[-1])

                # 1. Update MFE/MAE BEFORE exit checks (capture final candle)
                if sym in self.positions:
                    self._update_mfe_mae(sym, high, low)

                # 2. Check exits for existing positions
                if sym in self.positions:
                    self._check_exits(sym, price, high, low, ts_str, df_window)

                # 3. Funding fee (every 2 candles for 4h = 8h)
                if sym in self.positions:
                    self._funding_counter += 1
                    if self._funding_counter >= 2:  # 2 × 4h = 8h
                        self._apply_funding(sym, price)
                        self._funding_counter = 0

                # 4. Evaluate new positions
                if sym not in self.positions:
                    self._evaluate_entry(sym, df_window, price, ts_str)

            # Track equity
            equity = self._calc_equity(data_map, timestamp)
            self.equity_curve.append(equity)

        # Close remaining positions at last prices
        for sym in list(self.positions.keys()):
            if sym in data_map:
                df = data_map[sym]
                last_price = df["close"].iloc[-1]
                last_time = str(df["timestamp"].iloc[-1])
                last_regime = detect_regime(df.tail(100).reset_index(drop=True))
                self._close_position(sym, last_price, last_time,
                                     "END_OF_DATA", last_regime)

        # Calculate results
        result = self._calculate_results(result)
        self._print_results(result)
        return result

    # ─── ENTRY LOGIC ─────────────────────────────────────

    def _evaluate_entry(self, symbol: str, df: pd.DataFrame,
                        price: float, timestamp: str):
        """Evaluate strategies + pre-trade risk (matches live system)"""
        if len(self.positions) >= config.MAX_POSITIONS:
            return
        if self._daily_trades >= config.MAX_DAILY_TRADES:
            return
        if self._daily_loss >= config.MAX_DAILY_LOSS:
            return

        regime = detect_regime(df)

        # Evaluate all 4 strategies
        signals = []
        for strat in self.strategies:
            try:
                sig = strat.evaluate(df, symbol, regime)
                if sig.action != "NONE":
                    # Inject ATR
                    atr_s = calc_atr(df)
                    sig.atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02
                    sig.price = price
                    signals.append(sig)
            except Exception:
                pass

        if not signals:
            return

        combined = combine_signals(signals, regime)

        if combined.action == "NONE":
            return

        # Pre-trade risk checks
        action = combined.action

        # VOLATILE — block
        if regime == "VOLATILE":
            return

        # LONG in TREND_DOWN — block
        if action == "LONG" and regime == "TREND_DOWN":
            return

        # SHORT — block (unless conditional)
        if action == "SHORT":
            if not config.ALLOW_SHORT:
                if not (getattr(config, 'ALLOW_SHORT_CONDITIONAL', False) and regime == "TREND_DOWN"):
                    return

        # ATR & position sizing
        atr_s = calc_atr(df)
        atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02

        rr = config.DYNAMIC_RR.get(regime, {"sl": 1.5, "tp": 3.0})
        sl_dist = atr * rr["sl"]
        tp_dist = atr * rr["tp"]

        # SL floor
        min_sl = price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        # Stop/TP prices
        if action == "LONG":
            sl = price - sl_dist
            tp = price + tp_dist
            tp1 = price + tp_dist * config.PARTIAL_TP_RATIO
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            tp1 = price - tp_dist * config.PARTIAL_TP_RATIO

        # Position sizing
        risk_amount = self.balance * config.RISK_BASE_PCT
        size_by_risk = risk_amount / sl_dist
        size_by_notional = (self.balance * 0.10) / price
        size = min(size_by_risk, size_by_notional)

        if regime == "RANGING":
            size *= 0.50

        if size < 0.0001:
            return

        # Entry commission
        entry_comm = price * size * config.COMMISSION_RATE
        self.balance -= entry_comm

        # Create position
        self.positions[symbol] = BTPosition(
            symbol=symbol, side=action, entry_price=price,
            size=size, stop_loss=sl, take_profit=tp,
            take_profit_1=tp1, entry_time=timestamp,
            strategy=combined.strategy, entry_regime=regime,
            original_entry_regime=regime,
            entry_atr=atr, max_favorable=price, max_adverse=price,
        )
        self._daily_trades += 1

    # ─── EXIT LOGIC ──────────────────────────────────────

    def _check_exits(self, symbol: str, price: float,
                     high: float, low: float, timestamp: str,
                     df: pd.DataFrame):
        """Check all exit conditions (matches live stop_manager + smart exit)"""
        pos = self.positions[symbol]
        pos.candles_held += 1
        current_regime = detect_regime(df)

        # ─── BREAKEVEN STOP ───────────────────────────
        if not pos.breakeven_applied and pos.entry_atr > 0:
            be_dist = pos.entry_atr * config.BREAKEVEN_ATR_TRIGGER
            if pos.side == "LONG" and high >= pos.entry_price + be_dist:
                pos.stop_loss = max(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True
            elif pos.side == "SHORT" and low <= pos.entry_price - be_dist:
                pos.stop_loss = min(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True

        # ─── TRAILING STOP ────────────────────────────
        if pos.trailing_active:
            if pos.side == "LONG" and high > pos.trailing_peak:
                pos.trailing_peak = high
                new_sl = high * (1 - config.TRAILING_STOP_DISTANCE)
                if new_sl > pos.stop_loss:
                    pos.stop_loss = new_sl
            elif pos.side == "SHORT" and low < pos.trailing_peak:
                pos.trailing_peak = low
                new_sl = low * (1 + config.TRAILING_STOP_DISTANCE)
                if new_sl < pos.stop_loss:
                    pos.stop_loss = new_sl

        if not pos.trailing_active:
            if pos.side == "LONG":
                pct = (high - pos.entry_price) / pos.entry_price
                if pct >= config.TRAILING_STOP_ACTIVATE:
                    pos.trailing_active = True
                    pos.trailing_peak = high
            else:
                pct = (pos.entry_price - low) / pos.entry_price
                if pct >= config.TRAILING_STOP_ACTIVATE:
                    pos.trailing_active = True
                    pos.trailing_peak = low

        # ─── SMART EXIT (regime change) ───────────────
        if config.SMART_EXIT_ENABLED and pos.entry_regime:
            if current_regime != pos.entry_regime:
                # Calculate unrealized PnL
                if pos.side == "LONG":
                    unrealized = (price - pos.entry_price) * pos.size
                else:
                    unrealized = (pos.entry_price - price) * pos.size

                if unrealized > 0:
                    # Profitable + regime change → close
                    self._close_position(symbol, price, timestamp,
                                         f"SMART-EXIT: {pos.entry_regime}→{current_regime} (kârda)",
                                         current_regime)
                    return
                else:
                    # Losing + regime change → narrow TP
                    new_rr = config.DYNAMIC_RR.get(current_regime, None)
                    if new_rr and pos.entry_atr > 0:
                        new_tp_dist = pos.entry_atr * new_rr["tp"]
                        if pos.side == "LONG":
                            new_tp = pos.entry_price + new_tp_dist
                            if new_tp < pos.take_profit:
                                pos.take_profit = new_tp
                                pos.take_profit_1 = pos.entry_price + new_tp_dist * config.PARTIAL_TP_RATIO
                        else:
                            new_tp = pos.entry_price - new_tp_dist
                            if new_tp > pos.take_profit:
                                pos.take_profit = new_tp
                                pos.take_profit_1 = pos.entry_price - new_tp_dist * config.PARTIAL_TP_RATIO
                        pos.entry_regime = current_regime

        # ─── PARTIAL TP CHECK ─────────────────────────
        if (config.PARTIAL_TP_ENABLED and not pos.partial_closed
                and pos.take_profit_1 > 0):
            if pos.side == "LONG" and high >= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)
            elif pos.side == "SHORT" and low <= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)

        # ─── STOP LOSS CHECK ──────────────────────────
        if pos.side == "LONG" and low <= pos.stop_loss:
            exit_price = pos.stop_loss  # Assume fills at SL level
            self._close_position(symbol, exit_price, timestamp,
                                 "STOP-LOSS", current_regime)
            return
        elif pos.side == "SHORT" and high >= pos.stop_loss:
            exit_price = pos.stop_loss
            self._close_position(symbol, exit_price, timestamp,
                                 "STOP-LOSS", current_regime)
            return

        # ─── TAKE PROFIT CHECK ────────────────────────
        if pos.side == "LONG" and high >= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp,
                                 "TAKE-PROFIT", current_regime)
            return
        elif pos.side == "SHORT" and low <= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp,
                                 "TAKE-PROFIT", current_regime)
            return

    def _partial_close(self, symbol: str, price: float, timestamp: str):
        """Partial TP: Close 50%, move SL to entry"""
        pos = self.positions[symbol]
        close_size = pos.size * config.PARTIAL_TP_CLOSE_PCT

        if pos.side == "LONG":
            gross = (price - pos.entry_price) * close_size
        else:
            gross = (pos.entry_price - price) * close_size

        comm = price * close_size * config.COMMISSION_RATE
        net = gross - comm
        self.balance += net

        # Record partial close as trade
        self.trades.append(BTTrade(
            symbol=symbol, side=pos.side,
            entry_price=pos.entry_price, exit_price=price,
            entry_time=pos.entry_time, exit_time=timestamp,
            size=close_size, gross_pnl=gross, commission=comm,
            funding_fee=0, net_pnl=net,
            reason="PARTIAL-TP1", strategy=pos.strategy,
            entry_regime=pos.original_entry_regime or pos.entry_regime,
            exit_regime=pos.entry_regime,
            mfe_pct=pos.mfe_pct, mae_pct=pos.mae_pct,
            candles_held=pos.candles_held, entry_atr=pos.entry_atr,
            sl_distance=abs(pos.entry_price - pos.stop_loss),
            tp_distance=abs(pos.take_profit - pos.entry_price),
            rr_ratio=abs(pos.take_profit - pos.entry_price) / max(abs(pos.entry_price - pos.stop_loss), 0.0001),
        ))

        # Update position
        pos.size -= close_size
        pos.partial_closed = True
        pos.stop_loss = pos.entry_price  # SL → breakeven
        pos.breakeven_applied = True

    def _close_position(self, symbol: str, price: float,
                        timestamp: str, reason: str, exit_regime: str):
        """Close full position"""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]

        if pos.side == "LONG":
            gross = (price - pos.entry_price) * pos.size
        else:
            gross = (pos.entry_price - price) * pos.size

        comm = price * pos.size * config.COMMISSION_RATE
        net = gross - comm - pos.funding_paid
        self.balance += net

        if net < 0:
            self._daily_loss += abs(net)

        sl_dist = abs(pos.entry_price - pos.stop_loss)
        tp_dist = abs(pos.take_profit - pos.entry_price)

        self.trades.append(BTTrade(
            symbol=symbol, side=pos.side,
            entry_price=pos.entry_price, exit_price=price,
            entry_time=pos.entry_time, exit_time=timestamp,
            size=pos.size, gross_pnl=gross, commission=comm,
            funding_fee=pos.funding_paid, net_pnl=net,
            reason=reason, strategy=pos.strategy,
            entry_regime=pos.original_entry_regime or pos.entry_regime,
            exit_regime=exit_regime,
            mfe_pct=pos.mfe_pct, mae_pct=pos.mae_pct,
            candles_held=pos.candles_held, entry_atr=pos.entry_atr,
            sl_distance=sl_dist, tp_distance=tp_dist,
            rr_ratio=tp_dist / max(sl_dist, 0.0001),
        ))

        del self.positions[symbol]

    # ─── MFE/MAE TRACKING ────────────────────────────────

    def _update_mfe_mae(self, symbol: str, high: float, low: float):
        """Track Maximum Favorable/Adverse Excursion"""
        pos = self.positions[symbol]

        if pos.side == "LONG":
            if high > pos.max_favorable:
                pos.max_favorable = high
                pos.mfe_pct = (high - pos.entry_price) / pos.entry_price * 100
            if low < pos.max_adverse:
                pos.max_adverse = low
                pos.mae_pct = (pos.entry_price - low) / pos.entry_price * 100
        else:  # SHORT
            if low < pos.max_favorable:
                pos.max_favorable = low
                pos.mfe_pct = (pos.entry_price - low) / pos.entry_price * 100
            if high > pos.max_adverse:
                pos.max_adverse = high
                pos.mae_pct = (high - pos.entry_price) / pos.entry_price * 100

    # ─── FUNDING FEE ─────────────────────────────────────

    def _apply_funding(self, symbol: str, price: float):
        """Simulate funding fee (0.01% per 8h)"""
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        notional = pos.size * price
        fee = notional * config.FUNDING_FEE_RATE
        pos.funding_paid += fee
        self.balance -= fee

    # ─── EQUITY CALCULATION ──────────────────────────────

    def _calc_equity(self, data_map: Dict, timestamp: int) -> float:
        """Calculate total equity including unrealized PnL"""
        equity = self.balance
        for sym, pos in self.positions.items():
            if sym in data_map:
                df = data_map[sym]
                mask = df["open_time"] <= timestamp
                if mask.any():
                    price = df[mask]["close"].iloc[-1]
                    if pos.side == "LONG":
                        equity += (price - pos.entry_price) * pos.size
                    else:
                        equity += (pos.entry_price - price) * pos.size
        return equity

    # ─── RESULTS CALCULATION ─────────────────────────────

    def _calculate_results(self, result: BTResult) -> BTResult:
        """Calculate comprehensive statistics"""
        result.trades = self.trades
        result.equity_curve = self.equity_curve
        result.total_trades = len(self.trades)
        result.final_balance = self.balance

        if not self.trades:
            return result

        pnls = [t.net_pnl for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.wins = len(wins)
        result.losses = len(losses)
        result.win_rate = len(wins) / len(pnls) * 100 if pnls else 0
        result.total_pnl = sum(pnls)
        result.total_commission = sum(t.commission for t in self.trades)
        result.total_funding = sum(t.funding_fee for t in self.trades)
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0
        result.avg_hold_candles = np.mean([t.candles_held for t in self.trades])
        result.avg_mfe = np.mean([t.mfe_pct for t in self.trades])
        result.avg_mae = np.mean([t.mae_pct for t in self.trades])

        # Profit Factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Sharpe
        if len(pnls) >= 2:
            std = np.std(pnls)
            result.sharpe = np.mean(pnls) / std if std > 0 else 0

        # Max Drawdown
        peak = self.initial_balance
        max_dd = 0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = dd / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                result.max_drawdown_pct = dd_pct * 100
        result.max_drawdown = max_dd

        # Per-regime stats
        for regime in ["TREND_UP", "TREND_DOWN", "RANGING", "VOLATILE"]:
            rt = [t for t in self.trades if t.entry_regime == regime]
            if rt:
                rw = [t for t in rt if t.net_pnl > 0]
                result.regime_stats[regime] = {
                    "trades": len(rt),
                    "wins": len(rw),
                    "win_rate": len(rw) / len(rt) * 100,
                    "pnl": sum(t.net_pnl for t in rt),
                    "avg_mfe": np.mean([t.mfe_pct for t in rt]),
                    "avg_mae": np.mean([t.mae_pct for t in rt]),
                }

        # Per-strategy stats
        strat_names = set(t.strategy for t in self.trades)
        for sname in strat_names:
            st = [t for t in self.trades if t.strategy == sname]
            sw = [t for t in st if t.net_pnl > 0]
            result.strategy_stats[sname] = {
                "trades": len(st),
                "wins": len(sw),
                "win_rate": len(sw) / len(st) * 100,
                "pnl": sum(t.net_pnl for t in st),
            }

        # Exit reason breakdown
        reasons = {}
        for t in self.trades:
            r = t.reason.split(":")[0] if ":" in t.reason else t.reason
            if r not in reasons:
                reasons[r] = {"count": 0, "pnl": 0}
            reasons[r]["count"] += 1
            reasons[r]["pnl"] += t.net_pnl
        result.regime_stats["exit_reasons"] = reasons

        return result

    # ─── PRINT RESULTS ───────────────────────────────────

    def _print_results(self, result: BTResult):
        """Print comprehensive results"""
        print(f"\n{'='*70}")
        print(f"BACKTEST v3.0 SONUÇLARI — {result.period}")
        print(f"{'='*70}")

        print(f"\n  {'GENEL PERFORMANS':─^50}")
        print(f"  Toplam Trade:    {result.total_trades}")
        print(f"  Kazanç:          {result.wins} ({result.win_rate:.1f}%)")
        print(f"  Kayıp:           {result.losses}")
        print(f"  Toplam PnL:      ${result.total_pnl:+.2f}")
        print(f"  Komisyon:        ${result.total_commission:.2f}")
        print(f"  Funding Fee:     ${result.total_funding:.2f}")
        print(f"  Profit Factor:   {result.profit_factor:.2f}")
        print(f"  Sharpe:          {result.sharpe:.2f}")
        print(f"  Max Drawdown:    ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1f}%)")
        print(f"  Final Balance:   ${result.final_balance:,.2f}")

        print(f"\n  {'TRADE ANALİTİKLERİ':─^50}")
        print(f"  Ort. Kazanç:     ${result.avg_win:+.2f}")
        print(f"  Ort. Kayıp:      ${result.avg_loss:+.2f}")
        print(f"  Ort. MFE:        {result.avg_mfe:.2f}%")
        print(f"  Ort. MAE:        {result.avg_mae:.2f}%")
        print(f"  Ort. Holding:    {result.avg_hold_candles:.1f} candle")

        if result.regime_stats:
            print(f"\n  {'REGIME BAZLI PERFORMANS':─^50}")
            for regime, stats in result.regime_stats.items():
                if regime == "exit_reasons":
                    continue
                print(f"  {regime:12s}: {stats['trades']:3d} trade | "
                      f"WR={stats['win_rate']:5.1f}% | "
                      f"PnL=${stats['pnl']:+8.2f} | "
                      f"MFE={stats['avg_mfe']:.2f}% MAE={stats['avg_mae']:.2f}%")

        if result.strategy_stats:
            print(f"\n  {'STRATEJİ BAZLI PERFORMANS':─^50}")
            for sname, stats in result.strategy_stats.items():
                print(f"  {sname:18s}: {stats['trades']:3d} trade | "
                      f"WR={stats['win_rate']:5.1f}% | "
                      f"PnL=${stats['pnl']:+8.2f}")

        if "exit_reasons" in result.regime_stats:
            print(f"\n  {'ÇIKIŞ NEDENLERİ':─^50}")
            for reason, data in result.regime_stats["exit_reasons"].items():
                print(f"  {reason:20s}: {data['count']:3d} | PnL=${data['pnl']:+8.2f}")

        # Top 5 best/worst trades
        sorted_trades = sorted(self.trades, key=lambda t: t.net_pnl, reverse=True)
        if len(sorted_trades) >= 5:
            print(f"\n  {'EN İYİ 5 TRADE':─^50}")
            for t in sorted_trades[:5]:
                print(f"  {t.symbol:10s} {t.side:5s} ${t.net_pnl:+8.2f} | "
                      f"MFE={t.mfe_pct:.2f}% | {t.reason}")

            print(f"\n  {'EN KÖTÜ 5 TRADE':─^50}")
            for t in sorted_trades[-5:]:
                print(f"  {t.symbol:10s} {t.side:5s} ${t.net_pnl:+8.2f} | "
                      f"MAE={t.mae_pct:.2f}% | {t.reason}")

        print(f"\n{'='*70}\n")


def save_results(result: BTResult, filename: str = None):
    """Save results to JSON file"""
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest/results_v3_{ts}.json"

    data = {
        "period": result.period,
        "total_trades": result.total_trades,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate": result.win_rate,
        "total_pnl": result.total_pnl,
        "profit_factor": result.profit_factor,
        "sharpe": result.sharpe,
        "max_drawdown": result.max_drawdown,
        "max_drawdown_pct": result.max_drawdown_pct,
        "final_balance": result.final_balance,
        "avg_mfe": result.avg_mfe,
        "avg_mae": result.avg_mae,
        "regime_stats": result.regime_stats,
        "strategy_stats": result.strategy_stats,
        "trades": [
            {
                "symbol": t.symbol, "side": t.side,
                "entry": t.entry_price, "exit": t.exit_price,
                "pnl": t.net_pnl, "reason": t.reason,
                "regime": t.entry_regime, "strategy": t.strategy,
                "mfe": t.mfe_pct, "mae": t.mae_pct,
                "candles": t.candles_held,
            }
            for t in result.trades
        ],
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {filename}")


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="War Machine Backtest v3.0")
    parser.add_argument("--symbol", default=None, help="Single symbol (e.g. BTCUSDT)")
    parser.add_argument("--days", type=int, default=60, help="Days of history")
    parser.add_argument("--all", action="store_true", help="Test all config.SYMBOLS")
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    args = parser.parse_args()

    if args.symbol:
        symbols = [args.symbol]
    elif args.all:
        symbols = config.SYMBOLS
    else:
        # Default: top coins
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
                    "DOGEUSDT", "ADAUSDT", "VETUSDT", "ARPAUSDT"]

    bt = BacktestV3(initial_balance=args.balance)
    result = bt.run(symbols=symbols, days=args.days)

    if args.save:
        save_results(result)
