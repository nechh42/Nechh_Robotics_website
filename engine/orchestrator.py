"""
orchestrator.py - Central Coordinator v10.0
========================================
The brain. Connects all modules in a single event loop.

Flow:
  Tick -> CandleManager -> Candle closes -> Regime detect ->
  Strategies evaluate -> Voting -> Pre-trade risk -> Execute ->
  Database + Telegram

Degisiklikler (v10.0):
  [FIX-1] REGIME-EXIT tamamen kaldirildi (_on_tick icinden)
          Onceki: Her tick'te detect_regime() + pozisyon kapama
          Yeni: Pozisyonlar SADECE SL/TP ile kapanir
  [FIX-2] _check_regime_exit metodu kaldirildi (olü kod temizligi)
  [FIX-3] _on_tick sadestirild, gereksiz df yukleme yok
"""

import asyncio
import logging
from datetime import datetime

import config
from data.candle_manager import CandleManager, Candle
from data.datafeed import DataFeed
from engine.state import TradingState
from engine.signal import Signal
from engine.voting import combine_signals
from engine.adaptive_weights import AdaptiveWeights
from strategies.regime import detect_regime
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.edge_discovery import EdgeDiscoveryStrategy
from strategies.indicators import calc_atr
from risk.pre_trade import PreTradeRisk
from risk.stop_manager import check_exit
from risk.position_sizer import DynamicPositionSizer
from execution.paper import PaperExecutor
from persistence.database import Database
from persistence.trade_journal import record_entry as journal_entry, record_exit as journal_exit
from monitoring.telegram import telegram
from monitoring.performance import PerformanceTracker

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central coordinator - single event loop, no module-to-module calls"""

    def __init__(self):
        self._running = False
        self._tick_count = 0

        # Core state
        self.state = TradingState()
        self.db = Database()
        self.performance = PerformanceTracker(config.INITIAL_BALANCE)
        self.risk = PreTradeRisk()
        self.executor = PaperExecutor(self.state)
        self.adaptive = AdaptiveWeights()
        self.sizer = DynamicPositionSizer()

        # Dual Candle managers: 4h (trend) + 1h (mean reversion)
        self.candles_4h = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=self._on_candle_close,
            interval=config.CANDLE_INTERVAL,
            max_candles=config.CANDLE_MAX_STORED,
        )
        self.candles_1h = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=None,  # 1h candle close is not signaling
            interval=config.CANDLE_INTERVAL_SHORT,
            max_candles=config.CANDLE_MAX_STORED,
        )

        # Datafeed feeds both managers
        self.feed = DataFeed(
            symbols=config.SYMBOLS,
            on_tick=self._on_tick_sync,
        )

        # Strategies (RSI gets 1h manager injected)
        self.strategies = [
            RSIReversionStrategy(candles_1h_manager=self.candles_1h),
            MomentumStrategy(),
            VWAPReversionStrategy(),
            EdgeDiscoveryStrategy(),
        ]

        # Restore positions from database (survive restarts)
        self._restore_positions()

    def _restore_positions(self):
        """Load saved positions from database"""
        saved = self.db.load_positions()
        for symbol, pos_data in saved.items():
            self.state.restore_position(symbol, pos_data)
            logger.info(f"[RESTORE] Position loaded: {symbol} {pos_data['side']}")
        if saved:
            logger.info(f"[RESTORE] {len(saved)} positions restored from DB")

    async def start(self):
        """Start the war machine"""
        self._running = True

        logger.info("=" * 60)
        logger.info("WAR MACHINE STARTING")
        logger.info(f"Mode: {'LIVE' if config.REAL_TRADING_ENABLED else 'PAPER'}")
        logger.info(f"Balance: ${config.INITIAL_BALANCE:,.2f}")
        logger.info(f"Symbols: {len(config.SYMBOLS)}")
        logger.info(f"Strategies: {[s.name for s in self.strategies]}")
        logger.info(f"Timeframes: 4h (trend) + 1h (mean reversion)")
        logger.info("=" * 60)

        self._start_time = datetime.now()

        # Initialize candle histories from REST API (both 4h and 1h)
        await self.candles_4h.initialize()
        await self.candles_1h.initialize()

        # TEST MODE: Force first trade after initialization
        if config.TEST_MODE:
            logger.warning("[TEST] TEST_MODE ENABLED - Forcing first trade evaluation...")
            await asyncio.sleep(1)
            # Manually call evaluation for testing
            await self._evaluate_strategies("BTCUSDT")
            await asyncio.sleep(0.5)
            await self._evaluate_strategies("ETHUSDT")

        # Send Telegram startup alert
        asyncio.create_task(telegram.startup_alert())

        # Start periodic health report
        from monitoring.health import health_loop
        asyncio.create_task(health_loop(self))

        # Start WebSocket feed
        await self.feed.start()

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the war machine"""
        logger.info("[ENGINE] Shutting down...")
        self._running = False
        await self.feed.stop()

        # Save all open positions to database
        for symbol, pos in self.state.positions.items():
            self.db.save_position(symbol, {
                "side": pos.side, "entry_price": pos.entry_price,
                "size": pos.size, "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "entry_time": pos.entry_time.isoformat(),
                "strategy": pos.strategy,
                "trailing_active": pos.trailing_active,
                "trailing_peak": pos.trailing_peak,
            })
        logger.info(f"[ENGINE] {len(self.state.positions)} positions saved to DB")

        # Print final stats
        status = self.state.get_status()
        logger.info("=" * 60)
        logger.info("FINAL STATS")
        logger.info(f"Balance: ${status['balance']:,.2f}")
        logger.info(f"Equity: ${status['equity']:,.2f}")
        logger.info(f"PnL: ${status['total_pnl']:,.2f}")
        logger.info(f"Trades: {status['total_trades']} (W:{status['wins']} L:{status['losses']})")
        logger.info(f"Win Rate: {status['win_rate']:.1f}%")
        logger.info("=" * 60)

    def _on_tick_sync(self, symbol: str, price: float):
        """Sync wrapper for async tick handler"""
        try:
            asyncio.create_task(self._on_tick(symbol, price))
        except RuntimeError as e:
            logger.error(f"[TICK] Task creation failed: {e}")

    async def _on_tick(self, symbol: str, price: float):
        """
        Handle every incoming tick.
        Update BOTH 4h and 1h candles.
        SADECE SL/TP kontrolu yapar. Regime exit YOK.
        """
        try:
            self._tick_count += 1

            # Update state price
            self.state.update_price(symbol, price)

            # Update BOTH candle aggregations
            self.candles_4h.on_tick(symbol, price)
            self.candles_1h.on_tick(symbol, price)

            # Update performance tracking
            self.performance.update_equity(self.state.equity)

            # Log performance every 500 ticks
            if self._tick_count % 500 == 0:
                self.performance.log_summary(self._tick_count)

            # SL/TP kontrolu — SADECE bu, baska hicbir sey
            if symbol in self.state.positions:
                pos = self.state.positions[symbol]
                exit_reason = check_exit(pos, price)

                if exit_reason:
                    logger.warning(f"[EXIT] {symbol} {pos.side}: {exit_reason}")
                    trade = self.executor.close_order(symbol, price, exit_reason)

                    if trade:
                        self._on_trade_closed(trade, exit_reason)
                        self.db.delete_position(symbol)

        except Exception as e:
            logger.error(f"[TICK] Error processing {symbol} @ {price}: {e}")

    def _on_candle_close(self, symbol: str, candle: Candle):
        """Called when a candle closes - run strategies"""
        try:
            asyncio.create_task(self._evaluate_strategies(symbol))
        except RuntimeError as e:
            logger.error(f"[CANDLE] Strategy task creation failed: {e}")

    async def _evaluate_strategies(self, symbol: str):
        """Run all strategies on closed 4h candle data"""
        if not self.candles_4h.has_enough_data(symbol):
            return

        df = self.candles_4h.get_dataframe(symbol, 100)
        if df is None:
            return

        regime = detect_regime(df)
        price = df["close"].iloc[-1]
        logger.info(f"[CANDLE] {symbol} closed @ ${price:.4f} | regime={regime} | candles={len(df)}")

        # Pozisyon varsa strateji calistirma
        if symbol in self.state.positions:
            return

        # ATR hesapla
        atr_series = calc_atr(df)
        current_atr = atr_series.iloc[-1] if not atr_series.empty else 0.0

        # Stratejileri calistir
        signals = []
        for strategy in self.strategies:
            try:
                sig = strategy.evaluate(df, symbol, regime)
                if sig.atr == 0.0:
                    sig.atr = current_atr
                signals.append(sig)
            except Exception as e:
                logger.error(f"[STRATEGY] {strategy.name} error on {symbol}: {e}")

        # Esit agirlikli oylama (4 strateji)
        equal_weights = {
            "RSI": 0.25,
            "MOMENTUM": 0.25,
            "VWAP": 0.25,
            "EDGE_DISCOVERY": 0.25,
        }
        combined = combine_signals(signals, regime, equal_weights)

        if combined.action == "NONE":
            return

        # Saat filtresi: 00:00-06:00 UTC trade acma
        current_hour = datetime.utcnow().hour
        if 0 <= current_hour < 6:
            logger.info(f"[SAAT-FILTRE] {symbol}: Gece saati ({current_hour}:00 UTC) — trade acilmaz")
            return

        # Korelasyon filtresi
        correlated_pairs = [
            {"BTCUSDT", "ETHUSDT"},
            {"ADAUSDT", "NEARUSDT"},
            {"SOLUSDT", "AVAXUSDT"},
        ]
        for pair in correlated_pairs:
            if symbol in pair:
                other = (pair - {symbol}).pop()
                if other in self.state.positions:
                    logger.info(f"[KORELASYON] {symbol}: {other} zaten acik — atlanir")
                    return

        # Risk kontrolu
        approved, reason, params = self.risk.check(combined, self.state, regime)

        if not approved:
            return

        # Emri gerceklestir
        result = self.executor.open_order(params)

        if result["status"] == "FILLED":
            pos = result["position"]
            self.db.save_position(symbol, {
                "side": pos.side, "entry_price": pos.entry_price,
                "size": pos.size, "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "entry_time": pos.entry_time.isoformat(),
                "strategy": combined.strategy,
                "trailing_active": pos.trailing_active,
                "trailing_peak": pos.trailing_peak,
            })

            self.db.log_event("OPEN", f"{pos.side} {symbol} @ ${pos.entry_price:.4f}")

            # Trade Journal
            from strategies.indicators import calc_rsi, calc_ema
            from data.sentiment import fear_greed
            indicators = {}
            if df is not None:
                rsi_s = calc_rsi(df["close"])
                indicators = {
                    "rsi": float(rsi_s.iloc[-1]) if not rsi_s.empty else 0,
                    "ema9": float(calc_ema(df["close"], 9).iloc[-1]),
                    "ema21": float(calc_ema(df["close"], 21).iloc[-1]),
                    "atr": float(current_atr),
                    "fear_greed": fear_greed.get_score(),
                }
            pos._journal_id = journal_entry(
                symbol, pos.side, pos.entry_price,
                regime, combined.strategy, combined.confidence,
                indicators, pos.stop_loss, pos.take_profit,
                0.02, combined.reason,
            )

    def _on_trade_closed(self, trade, reason: str):
        """Handle trade completion - record, notify, track"""
        self.performance.record_trade(trade.net_pnl)
        self.risk.record_trade_result(trade.net_pnl, trade.symbol)

        # Adaptive learning
        df = self.candles.get_dataframe(trade.symbol, 100)
        trade_regime = detect_regime(df) if df is not None else "RANGING"
        self.adaptive.record_outcome(trade.strategy, trade_regime, trade.net_pnl > 0)
        self.sizer.record_trade(trade.net_pnl)

        # Trade Journal - cikis kaydi
        duration = (trade.exit_time - trade.entry_time).total_seconds()
        journal_id = getattr(trade, '_journal_id', -1)
        journal_exit(journal_id, trade.exit_price, reason, trade.net_pnl, duration)

        # Database kaydi
        self.db.save_trade({
            "symbol": trade.symbol, "side": trade.side,
            "entry_price": trade.entry_price, "exit_price": trade.exit_price,
            "size": trade.size, "gross_pnl": trade.gross_pnl,
            "commission": trade.commission, "net_pnl": trade.net_pnl,
            "strategy": trade.strategy, "reason": reason,
            "duration_seconds": duration,
        })

        self.db.log_event("CLOSE", f"{trade.side} {trade.symbol} PnL=${trade.net_pnl:.4f}")

        logger.info(f"[TRADE] {trade.side} {trade.symbol} PnL=${trade.net_pnl:.2f}")

        # Telegram bildirimi - SL/TP ile profesyonel format
        risk_pct = config.RISK_PER_TRADE_PCT * 100  # Risk per trade %
        asyncio.create_task(
            telegram.trade_alert(
                trade.symbol, trade.side,
                trade.entry_price, trade.exit_price,
                trade.net_pnl,
                stop_loss=0.0,  # SL bilgisi kapatılmış pos'da yok, DB'den alınabilir
                take_profit=0.0,  # TP bilgisi kapatılmış pos'da yok
                risk_pct=risk_pct
            )
        )
