"""
backtest_futures.py — War Machine Kaldıraçlı Futures Simülasyonu
=================================================================
Gerçek Binance Futures koşullarını simüle eder:

  - Kaldıraç (leverage): 3x, 5x, 10x
  - Likidasyon fiyatı hesabı (maintenance margin %0.4)
  - Gerçek funding fee (%0.01 / 8 saat, dinamik)
  - Komisyon: Taker %0.04, Maker %0.02 (futures)
  - Marjin yönetimi (isolated margin)
  - PnL kaldıraçla çarpılır (gerçek futures)
  - Likidasyon İğnesi kontrolü

Kullanım:
  python -m backtest.backtest_futures --leverage 3 --days 60
  python -m backtest.backtest_futures --leverage 5 --days 60
  python -m backtest.backtest_futures --leverage 10 --days 60
  python -m backtest.backtest_futures --compare --days 60
"""

import sys
import os
import json
import logging
import requests
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
from strategies.indicators import calc_atr
from engine.voting import combine_signals

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# FUTURES CONSTANTS
# ═══════════════════════════════════════════════════════

FUTURES_TAKER_FEE = 0.0004       # %0.04 taker
FUTURES_MAKER_FEE = 0.0002       # %0.02 maker
FUTURES_FUNDING_RATE = 0.0001    # %0.01 per 8h (Binance default)
FUTURES_MAINTENANCE_MARGIN = 0.004  # %0.4 maintenance margin (tier 1)
FUTURES_FUNDING_INTERVAL = 2     # Her 2 candle (4h × 2 = 8h)


@dataclass
class FuturesPosition:
    symbol: str
    side: str
    entry_price: float
    size: float                  # Size in base asset
    notional: float              # entry_price × size
    margin: float                # notional / leverage
    leverage: int
    stop_loss: float
    take_profit: float
    take_profit_1: float
    entry_time: str
    strategy: str
    entry_regime: str
    original_entry_regime: str = ""
    entry_atr: float = 0.0
    liquidation_price: float = 0.0
    breakeven_applied: bool = False
    partial_closed: bool = False
    trailing_active: bool = False
    trailing_peak: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    candles_held: int = 0
    funding_paid: float = 0.0
    funding_count: int = 0


@dataclass
class FuturesTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    size: float
    notional: float
    margin: float
    leverage: int
    gross_pnl: float       # Kaldıraçsız PnL
    leveraged_pnl: float   # Kaldıraçlı PnL (ROE)
    commission: float
    funding_fee: float
    net_pnl: float          # Nihai PnL
    reason: str
    strategy: str
    entry_regime: str
    exit_regime: str
    mfe_pct: float
    mae_pct: float
    candles_held: int
    roe_pct: float           # Return on Equity (margin)
    liquidated: bool = False


@dataclass
class FuturesResult:
    leverage: int = 1
    period: str = ""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    total_funding: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    final_balance: float = 0.0
    liquidations: int = 0
    avg_roe: float = 0.0
    sharpe: float = 0.0
    trades: List[FuturesTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)


class FuturesBacktest:
    """Gerçek Binance Futures simülasyonu"""

    def __init__(self, leverage: int = 5):
        self.leverage = leverage
        self.balance = config.INITIAL_BALANCE
        self.positions: Dict[str, FuturesPosition] = {}
        self.trades: List[FuturesTrade] = []
        self.equity_curve: List[float] = [self.balance]
        self._daily_trades = 0
        self._daily_loss = 0.0
        self._funding_counters: Dict[str, int] = {}

        # Strategies
        self.strategies = [
            RSIReversionStrategy(),
            MomentumStrategy(),
            VWAPReversionStrategy(),
            EdgeDiscoveryStrategy(),
        ]

    def _calc_liquidation_price(self, entry_price: float, side: str,
                                 leverage: int) -> float:
        """Binance likidasyon fiyatı hesabı (isolated margin, tier 1)"""
        # Liq price = entry × (1 ∓ 1/leverage + maintenance_margin)
        if side == "LONG":
            return entry_price * (1 - (1 / leverage) + FUTURES_MAINTENANCE_MARGIN)
        else:
            return entry_price * (1 + (1 / leverage) - FUTURES_MAINTENANCE_MARGIN)

    def _fetch_candles(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        """Fetch historical candles from Binance"""
        interval = config.CANDLE_INTERVAL
        limit = days * 6 + 10
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
        try:
            r = requests.get(url, params=params, timeout=30)
            data = r.json()
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            print(f"  ERROR fetching {symbol}: {e}")
            return None

    def run(self, days: int = 60) -> FuturesResult:
        """Run futures backtest"""
        print("=" * 70)
        print(f"WAR MACHINE FUTURES BACKTEST — Leverage {self.leverage}x")
        print("=" * 70)
        print(f"Balance: ${self.balance:,.2f} | Days: {days} | Leverage: {self.leverage}x")
        print(f"Commission: {FUTURES_TAKER_FEE*100:.2f}% | Funding: {FUTURES_FUNDING_RATE*100:.3f}%/8h")
        print(f"Maintenance Margin: {FUTURES_MAINTENANCE_MARGIN*100:.1f}%")
        print("=" * 70)

        # Fetch all data
        symbols = config.SYMBOLS
        data_map = {}
        for sym in symbols:
            print(f"  Fetching {sym}...", end=" ")
            df = self._fetch_candles(sym, days)
            if df is not None and len(df) > 50:
                data_map[sym] = df
                print(f"{len(df)} candles ✓")
            else:
                print("SKIP")

        # Walk through candles
        all_timestamps = sorted(set(
            ts for df in data_map.values() for ts in df["timestamp"]
        ))
        print(f"\nTotal timestamps: {len(all_timestamps)}")
        print("Walking through candles...\n")

        result = FuturesResult(leverage=self.leverage, period=f"{days}d")

        for i, timestamp in enumerate(all_timestamps):
            ts_str = str(timestamp)

            # Reset daily counters at each day boundary
            if i > 0 and timestamp.hour == 0:
                self._daily_trades = 0
                self._daily_loss = 0.0

            for sym, df in data_map.items():
                mask = df["timestamp"] <= timestamp
                if mask.sum() < config.MIN_CANDLES_FOR_STRATEGY:
                    continue
                df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)
                price = df_window["close"].iloc[-1]
                high = df_window["high"].iloc[-1]
                low = df_window["low"].iloc[-1]

                # 1. Update MFE/MAE
                if sym in self.positions:
                    pos = self.positions[sym]
                    if pos.side == "LONG":
                        if high > pos.max_favorable:
                            pos.max_favorable = high
                            pos.mfe_pct = (high - pos.entry_price) / pos.entry_price * 100
                        if low < pos.max_adverse:
                            pos.max_adverse = low
                            pos.mae_pct = (pos.entry_price - low) / pos.entry_price * 100
                    else:
                        if low < pos.max_favorable:
                            pos.max_favorable = low
                            pos.mfe_pct = (pos.entry_price - low) / pos.entry_price * 100
                        if high > pos.max_adverse:
                            pos.max_adverse = high
                            pos.mae_pct = (high - pos.entry_price) / pos.entry_price * 100

                # 2. Check exits (includes liquidation check)
                if sym in self.positions:
                    self._check_exits(sym, price, high, low, ts_str, df_window)

                # 3. Funding fee
                if sym in self.positions:
                    counter = self._funding_counters.get(sym, 0) + 1
                    self._funding_counters[sym] = counter
                    if counter >= FUTURES_FUNDING_INTERVAL:
                        self._apply_funding(sym, price)
                        self._funding_counters[sym] = 0

                # 4. Evaluate new entries
                if sym not in self.positions:
                    self._evaluate_entry(sym, df_window, price, ts_str)

            # Track equity
            equity = self.balance
            for sym, pos in self.positions.items():
                if sym in data_map:
                    p = data_map[sym]
                    mask = p["timestamp"] <= timestamp
                    if mask.any():
                        cp = p[mask]["close"].iloc[-1]
                        if pos.side == "LONG":
                            equity += (cp - pos.entry_price) * pos.size
                        else:
                            equity += (pos.entry_price - cp) * pos.size
            self.equity_curve.append(equity)

        # Close remaining
        for sym in list(self.positions.keys()):
            if sym in data_map:
                df = data_map[sym]
                last_price = df["close"].iloc[-1]
                last_time = str(df["timestamp"].iloc[-1])
                last_regime = detect_regime(df.tail(100).reset_index(drop=True))
                self._close_position(sym, last_price, last_time, "END_OF_DATA", last_regime)

        result = self._calculate_results(result)
        self._print_results(result)
        return result

    def _evaluate_entry(self, symbol: str, df: pd.DataFrame,
                        price: float, timestamp: str):
        if len(self.positions) >= config.MAX_POSITIONS:
            return
        if self._daily_trades >= config.MAX_DAILY_TRADES:
            return
        if self._daily_loss >= config.MAX_DAILY_LOSS:
            return

        regime = detect_regime(df)

        if getattr(config, 'TREND_UP_BLOCK', False) and regime == "TREND_UP":
            return
        if symbol in getattr(config, 'COIN_BLACKLIST', []):
            return
        if regime == "VOLATILE":
            return

        # DIP_BUY filter
        if getattr(config, 'DIP_BUY_FILTER', False) and regime == "RANGING":
            if len(df) >= 2:
                if df["close"].iloc[-2] >= df["open"].iloc[-2]:
                    return

        signals = []
        for strat in self.strategies:
            try:
                sig = strat.evaluate(df, symbol, regime)
                if sig.action != "NONE":
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

        action = combined.action
        if action == "LONG" and regime == "TREND_DOWN":
            return
        if action == "SHORT" and not config.ALLOW_SHORT:
            return

        # ATR & R:R
        atr_s = calc_atr(df)
        atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02
        rr = config.DYNAMIC_RR.get(regime, {"sl": 1.5, "tp": 3.0})
        sl_dist = atr * rr["sl"]
        tp_dist = atr * rr["tp"]

        min_sl = price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        if action == "LONG":
            sl = price - sl_dist
            tp = price + tp_dist
            tp1 = price + tp_dist * config.PARTIAL_TP_RATIO
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            tp1 = price - tp_dist * config.PARTIAL_TP_RATIO

        # === FUTURES POSITION SIZING ===
        # Risk amount = %0.5 of equity
        risk_amount = self.balance * config.RISK_BASE_PCT
        size_by_risk = risk_amount / sl_dist

        # Max notional = %10 of equity × leverage
        max_notional = self.balance * 0.10 * self.leverage
        size_by_notional = max_notional / price
        size = min(size_by_risk, size_by_notional)

        if regime == "RANGING":
            size *= 0.50

        if size < 0.0001:
            return

        notional = price * size
        margin = notional / self.leverage

        # Margin check
        if margin > self.balance * 0.25:  # Max %25 margin per position
            size = (self.balance * 0.25 * self.leverage) / price
            notional = price * size
            margin = notional / self.leverage

        # Liquidation price
        liq_price = self._calc_liquidation_price(price, action, self.leverage)

        # SL likidasyon kontrolü: SL, likidasyon fiyatından ÖNCE olmalı
        if action == "LONG" and sl <= liq_price:
            sl = liq_price * 1.005  # SL likidasyon fiyatının %0.5 üstünde
        elif action == "SHORT" and sl >= liq_price:
            sl = liq_price * 0.995

        # Margin + commission check
        entry_comm = notional * FUTURES_TAKER_FEE
        required = margin + entry_comm
        if required > self.balance:
            return

        # Deduct margin + commission from balance
        self.balance -= required

        self.positions[symbol] = FuturesPosition(
            symbol=symbol, side=action, entry_price=price,
            size=size, notional=notional, margin=margin,
            leverage=self.leverage, stop_loss=sl, take_profit=tp,
            take_profit_1=tp1, entry_time=timestamp,
            strategy=combined.strategy, entry_regime=regime,
            original_entry_regime=regime, entry_atr=atr,
            liquidation_price=liq_price,
            max_favorable=price, max_adverse=price,
        )
        self._daily_trades += 1

    def _check_exits(self, symbol: str, price: float,
                     high: float, low: float, timestamp: str,
                     df: pd.DataFrame):
        pos = self.positions[symbol]
        pos.candles_held += 1
        current_regime = detect_regime(df)

        # === LIQUIDATION CHECK ===
        if pos.side == "LONG" and low <= pos.liquidation_price:
            self._close_position(symbol, pos.liquidation_price, timestamp,
                                 f"LIQUIDATED @ ${pos.liquidation_price:.2f}", current_regime,
                                 liquidated=True)
            return
        elif pos.side == "SHORT" and high >= pos.liquidation_price:
            self._close_position(symbol, pos.liquidation_price, timestamp,
                                 f"LIQUIDATED @ ${pos.liquidation_price:.2f}", current_regime,
                                 liquidated=True)
            return

        # Breakeven
        if not pos.breakeven_applied and pos.entry_atr > 0:
            be_dist = pos.entry_atr * config.BREAKEVEN_ATR_TRIGGER
            if pos.side == "LONG" and high >= pos.entry_price + be_dist:
                pos.stop_loss = max(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True
            elif pos.side == "SHORT" and low <= pos.entry_price - be_dist:
                pos.stop_loss = min(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True

        # Smart Exit
        if config.SMART_EXIT_ENABLED and pos.entry_regime:
            if current_regime != pos.entry_regime:
                if pos.side == "LONG":
                    unrealized = (price - pos.entry_price) * pos.size
                else:
                    unrealized = (pos.entry_price - price) * pos.size
                if unrealized > 0:
                    self._close_position(symbol, price, timestamp,
                                         f"SMART-EXIT: {pos.entry_regime}→{current_regime} (kârda)",
                                         current_regime)
                    return
                else:
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

        # Partial TP
        if config.PARTIAL_TP_ENABLED and not pos.partial_closed and pos.take_profit_1 > 0:
            if pos.side == "LONG" and high >= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)
            elif pos.side == "SHORT" and low <= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)

        # Time Exit
        max_hold = getattr(config, 'MAX_HOLD_CANDLES', 0)
        if max_hold > 0 and pos.candles_held >= max_hold:
            self._close_position(symbol, price, timestamp,
                                 f"TIME-EXIT: {pos.candles_held} candle", current_regime)
            return

        # SL
        if pos.side == "LONG" and low <= pos.stop_loss:
            self._close_position(symbol, pos.stop_loss, timestamp, "STOP-LOSS", current_regime)
            return
        elif pos.side == "SHORT" and high >= pos.stop_loss:
            self._close_position(symbol, pos.stop_loss, timestamp, "STOP-LOSS", current_regime)
            return

        # TP
        if pos.side == "LONG" and high >= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp, "TAKE-PROFIT", current_regime)
            return
        elif pos.side == "SHORT" and low <= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp, "TAKE-PROFIT", current_regime)
            return

    def _partial_close(self, symbol: str, price: float, timestamp: str):
        pos = self.positions[symbol]
        close_size = pos.size * config.PARTIAL_TP_CLOSE_PCT
        close_notional = price * close_size

        if pos.side == "LONG":
            gross = (price - pos.entry_price) * close_size
        else:
            gross = (pos.entry_price - price) * close_size

        comm = close_notional * FUTURES_TAKER_FEE
        net = gross - comm
        margin_for_closed = (pos.entry_price * close_size) / self.leverage
        roe = (net / margin_for_closed * 100) if margin_for_closed > 0 else 0

        # Return partial margin + PnL
        self.balance += margin_for_closed + net
        self.trades.append(FuturesTrade(
            symbol=symbol, side=pos.side,
            entry_price=pos.entry_price, exit_price=price,
            entry_time=pos.entry_time, exit_time=timestamp,
            size=close_size, notional=close_notional,
            margin=margin_for_closed, leverage=self.leverage,
            gross_pnl=gross, leveraged_pnl=gross,
            commission=comm, funding_fee=0, net_pnl=net,
            reason="PARTIAL-TP1", strategy=pos.strategy,
            entry_regime=pos.original_entry_regime or pos.entry_regime,
            exit_regime=pos.entry_regime,
            mfe_pct=pos.mfe_pct, mae_pct=pos.mae_pct,
            candles_held=pos.candles_held,
            roe_pct=roe,
        ))
        pos.size -= close_size
        pos.notional = pos.entry_price * pos.size
        pos.margin = pos.notional / self.leverage
        pos.partial_closed = True
        pos.stop_loss = pos.entry_price
        pos.breakeven_applied = True

    def _close_position(self, symbol: str, price: float, timestamp: str,
                        reason: str, exit_regime: str, liquidated: bool = False):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        if pos.side == "LONG":
            gross = (price - pos.entry_price) * pos.size
        else:
            gross = (pos.entry_price - price) * pos.size

        close_notional = price * pos.size
        comm = close_notional * FUTURES_TAKER_FEE
        net = gross - comm - pos.funding_paid

        if liquidated:
            # Likidasyonda margin kaybedilir (zaten düşülmüştü, geri gelmez)
            net = -pos.margin - pos.funding_paid
            # Margin already deducted on entry, no return
        else:
            # Return margin + PnL
            self.balance += pos.margin + gross - comm - pos.funding_paid
            net = gross - comm - pos.funding_paid

        roe = (net / pos.margin * 100) if pos.margin > 0 else 0

        self.trades.append(FuturesTrade(
            symbol=symbol, side=pos.side,
            entry_price=pos.entry_price, exit_price=price,
            entry_time=pos.entry_time, exit_time=timestamp,
            size=pos.size, notional=pos.notional,
            margin=pos.margin, leverage=self.leverage,
            gross_pnl=gross, leveraged_pnl=gross,
            commission=comm, funding_fee=pos.funding_paid,
            net_pnl=net, reason=reason, strategy=pos.strategy,
            entry_regime=pos.original_entry_regime or pos.entry_regime,
            exit_regime=exit_regime,
            mfe_pct=pos.mfe_pct, mae_pct=pos.mae_pct,
            candles_held=pos.candles_held, roe_pct=roe,
            liquidated=liquidated,
        ))

        if net < 0:
            self._daily_loss += abs(net)

        del self.positions[symbol]
        if symbol in self._funding_counters:
            del self._funding_counters[symbol]

    def _apply_funding(self, symbol: str, price: float):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        fee = pos.notional * FUTURES_FUNDING_RATE
        pos.funding_paid += fee
        pos.funding_count += 1
        self.balance -= fee

    def _calculate_results(self, result: FuturesResult) -> FuturesResult:
        result.trades = self.trades
        result.equity_curve = self.equity_curve
        result.total_trades = len(self.trades)
        wins = [t for t in self.trades if t.net_pnl > 0]
        result.wins = len(wins)
        result.losses = result.total_trades - result.wins
        result.win_rate = result.wins / result.total_trades * 100 if result.total_trades > 0 else 0
        result.total_pnl = sum(t.net_pnl for t in self.trades)
        result.total_commission = sum(t.commission for t in self.trades)
        result.total_funding = sum(t.funding_fee for t in self.trades)
        result.final_balance = self.balance
        result.liquidations = sum(1 for t in self.trades if t.liquidated)

        gross_wins = sum(t.net_pnl for t in wins) if wins else 0
        gross_losses = abs(sum(t.net_pnl for t in self.trades if t.net_pnl <= 0))
        result.profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0

        if self.trades:
            result.avg_roe = np.mean([t.roe_pct for t in self.trades])

        # Max drawdown
        peak = self.equity_curve[0]
        max_dd = 0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            dd = peak - eq
            max_dd = max(max_dd, dd)
        result.max_drawdown = max_dd
        result.max_drawdown_pct = max_dd / config.INITIAL_BALANCE * 100

        # Sharpe
        returns = []
        for i in range(1, len(self.equity_curve)):
            r = (self.equity_curve[i] - self.equity_curve[i - 1]) / self.equity_curve[i - 1]
            returns.append(r)
        if returns and np.std(returns) > 0:
            result.sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)

        return result

    def _print_results(self, result: FuturesResult):
        wins = [t for t in result.trades if t.net_pnl > 0]
        losses = [t for t in result.trades if t.net_pnl <= 0]
        liqs = [t for t in result.trades if t.liquidated]

        print("\n" + "=" * 70)
        print(f"FUTURES BACKTEST SONUÇLARI — {self.leverage}x LEVERAGE — {result.period}")
        print("=" * 70)
        print(f"\n  ─────────────────GENEL PERFORMANS─────────────────")
        print(f"  Leverage:          {self.leverage}x")
        print(f"  Toplam Trade:      {result.total_trades}")
        print(f"  Kazanç:            {result.wins} ({result.win_rate:.1f}%)")
        print(f"  Kayıp:             {result.losses}")
        print(f"  Toplam PnL:        ${result.total_pnl:+.2f}")
        print(f"  Komisyon:          ${result.total_commission:.2f}")
        print(f"  Funding Fee:       ${result.total_funding:.2f}")
        print(f"  Profit Factor:     {result.profit_factor:.2f}")
        print(f"  Sharpe:            {result.sharpe:.2f}")
        print(f"  Max Drawdown:      ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1f}%)")
        print(f"  Final Balance:     ${result.final_balance:,.2f}")
        print(f"  LİKİDASYON:        {result.liquidations} trade ⚠️{'  SIFIR ✅' if result.liquidations == 0 else '  DİKKAT!'}")
        print(f"\n  ────────────────TRADE ANALİTİKLERİ────────────────")
        if wins:
            print(f"  Ort. Kazanç:       ${np.mean([t.net_pnl for t in wins]):.2f}")
        if losses:
            print(f"  Ort. Kayıp:        ${np.mean([t.net_pnl for t in losses]):.2f}")
        print(f"  Ort. ROE:          {result.avg_roe:+.2f}%")
        print(f"  Ort. MFE:          {np.mean([t.mfe_pct for t in result.trades]):.2f}%")
        print(f"  Ort. MAE:          {np.mean([t.mae_pct for t in result.trades]):.2f}%")

        # Exit reasons
        print(f"\n  ─────────────────ÇIKIŞ NEDENLERİ──────────────────")
        reasons = {}
        for t in result.trades:
            r = t.reason.split(":")[0]
            if r not in reasons:
                reasons[r] = {"count": 0, "pnl": 0}
            reasons[r]["count"] += 1
            reasons[r]["pnl"] += t.net_pnl
        for r, d in sorted(reasons.items(), key=lambda x: -x[1]["count"]):
            print(f"  {r:20s}: {d['count']:3d} | PnL=${d['pnl']:+8.2f}")

        if liqs:
            print(f"\n  ⚡ LİKİDASYON DETAYI:")
            for t in liqs:
                print(f"    {t.symbol:12s} {t.side} | Entry=${t.entry_price:.4f} → Liq=${t.exit_price:.4f} | Loss=${t.net_pnl:.2f}")

        print("\n" + "=" * 70)


def compare_leverages(days: int = 60):
    """3x, 5x, 10x kaldıraç karşılaştırması"""
    results = {}
    for lev in [1, 3, 5, 10]:
        print(f"\n{'='*70}")
        print(f"KALDIRAÇ: {lev}x")
        print(f"{'='*70}")
        bt = FuturesBacktest(leverage=lev)
        results[lev] = bt.run(days=days)

    # Comparison table
    print("\n" + "=" * 70)
    print("KALDIRATÇLI FUTURES KARŞILAŞTIRMA TABLOSU")
    print("=" * 70)
    header = f"  {'Metrik':<20s}"
    for lev in [1, 3, 5, 10]:
        header += f" | {lev}x{' '*10}"
    print(header)
    print("  " + "─" * 72)

    def row(name, func):
        line = f"  {name:<20s}"
        for lev in [1, 3, 5, 10]:
            r = results[lev]
            val = func(r)
            line += f" | {val:>12s}"
        print(line)

    row("Trade", lambda r: str(r.total_trades))
    row("Win Rate", lambda r: f"{r.win_rate:.1f}%")
    row("PnL", lambda r: f"${r.total_pnl:+.2f}")
    row("Profit Factor", lambda r: f"{r.profit_factor:.2f}")
    row("Max Drawdown", lambda r: f"{r.max_drawdown_pct:.1f}%")
    row("Final Balance", lambda r: f"${r.final_balance:,.2f}")
    row("Likidasyon", lambda r: f"{r.liquidations}")
    row("Komisyon", lambda r: f"${r.total_commission:.2f}")
    row("Funding", lambda r: f"${r.total_funding:.2f}")
    row("Ort. ROE", lambda r: f"{r.avg_roe:+.2f}%")
    row("Sharpe", lambda r: f"{r.sharpe:.2f}")
    print("=" * 70)

    # Save comparison
    save_path = os.path.join(os.path.dirname(__file__), "futures_comparison.txt")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write("WAR MACHINE FUTURES KARŞILAŞTIRMA\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Periyot: {days} gün\n\n")
        for lev in [1, 3, 5, 10]:
            r = results[lev]
            f.write(f"\n{'='*50}\n")
            f.write(f"{lev}x LEVERAGE\n")
            f.write(f"{'='*50}\n")
            f.write(f"  Trade: {r.total_trades}\n")
            f.write(f"  WR: {r.win_rate:.1f}%\n")
            f.write(f"  PnL: ${r.total_pnl:+.2f}\n")
            f.write(f"  PF: {r.profit_factor:.2f}\n")
            f.write(f"  MaxDD: {r.max_drawdown_pct:.1f}%\n")
            f.write(f"  Final: ${r.final_balance:,.2f}\n")
            f.write(f"  Likidasyon: {r.liquidations}\n")
            f.write(f"  Komisyon: ${r.total_commission:.2f}\n")
            f.write(f"  Funding: ${r.total_funding:.2f}\n")
            f.write(f"  ROE: {r.avg_roe:+.2f}%\n")
    print(f"\n✅ Karşılaştırma kaydedildi: {save_path}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Futures Backtest")
    parser.add_argument("--leverage", type=int, default=5)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--compare", action="store_true", help="1x/3x/5x/10x karşılaştır")
    args = parser.parse_args()

    if args.compare:
        compare_leverages(args.days)
    else:
        bt = FuturesBacktest(leverage=args.leverage)
        result = bt.run(days=args.days)
