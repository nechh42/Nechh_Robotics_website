"""orchestrator.py - Central Coordinator v11.0
========================================
The brain. Connects all modules in a single event loop.

Flow:
  Tick -> CandleManager -> Candle closes -> Regime detect ->
  Strategies evaluate -> Voting -> Pre-trade risk ->
  MTF Confirmation (15m) -> Execute -> Database + Telegram

Degisiklikler (v11.0):
  [MTF] 15m candle manager eklendi (multi-timeframe confirmation)
  [MTF] 4h sinyal → 15m onay gate'i (3/4 kriter gerekli)
  [MTF] Pending signal kuyruğu + max 4 retry (1 saat)
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
from engine.mtf_confirmation import MTFConfirmation, MTF_ENABLED
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
        self.mtf = MTFConfirmation()  # 15m confirmation gate

        # Triple Candle managers: 4h (trend) + 1h (mean reversion) + 15m (trigger)
        self.candles_4h = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=self._on_candle_close,
            interval=config.CANDLE_INTERVAL,
            max_candles=config.CANDLE_MAX_STORED,
        )
        self.candles_1h = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=self._on_candle_close_1h,  # 1h sinyal üretimi aktif
            interval=config.CANDLE_INTERVAL_SHORT,
            max_candles=config.CANDLE_MAX_STORED,
        )
        self.candles_15m = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=self._on_candle_close_15m,  # 15m MTF confirmation
            interval="15m",
            max_candles=config.CANDLE_MAX_STORED,
        )

        # Datafeed feeds all managers
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
        logger.info(f"Timeframes: 4h (trend) + 1h (mean reversion) + 15m (MTF trigger)")
        logger.info("=" * 60)

        self._start_time = datetime.now()

        # Initialize candle histories from REST API (4h, 1h, and 15m)
        await self.candles_4h.initialize()
        await self.candles_1h.initialize()
        await self.candles_15m.initialize()

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
        from monitoring.health import health_loop, summary_loop
        asyncio.create_task(health_loop(self))
        asyncio.create_task(summary_loop(self))

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
                "take_profit_1": pos.take_profit_1,
                "entry_time": pos.entry_time.isoformat(),
                "strategy": pos.strategy,
                "trailing_active": pos.trailing_active,
                "trailing_peak": pos.trailing_peak,
                "entry_atr": pos._entry_atr,
                "breakeven_applied": pos._breakeven_applied,
                "partial_closed": pos._partial_closed,
                "entry_regime": pos._entry_regime,
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

    def _on_tick_sync(self, symbol: str, price: float, volume: float = 0.0):
        """Sync wrapper for async tick handler"""
        try:
            asyncio.create_task(self._on_tick(symbol, price, volume))
        except RuntimeError as e:
            logger.error(f"[TICK] Task creation failed: {e}")

    async def _on_tick(self, symbol: str, price: float, volume: float = 0.0):
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
            self.candles_4h.on_tick(symbol, price, volume)
            self.candles_1h.on_tick(symbol, price, volume)
            self.candles_15m.on_tick(symbol, price, volume)

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
                    if exit_reason.startswith("PARTIAL-TP1"):
                        # Kısmi kapama: %50 kapat, SL → breakeven
                        logger.warning(f"[PARTIAL] {symbol} {pos.side}: {exit_reason}")
                        trade = self.state.partial_close_position(
                            symbol, price, config.PARTIAL_TP_CLOSE_PCT, exit_reason
                        )
                        if trade:
                            # SL → entry (breakeven) after partial TP
                            pos.stop_loss = pos.entry_price
                            pos._breakeven_applied = True
                            self._on_trade_closed(trade, exit_reason)
                            # DB güncelle (kalan pozisyon)
                            self.db.save_position(symbol, {
                                "side": pos.side, "entry_price": pos.entry_price,
                                "size": pos.size, "stop_loss": pos.stop_loss,
                                "take_profit": pos.take_profit,
                                "entry_time": pos.entry_time.isoformat(),
                                "strategy": pos.strategy,
                                "trailing_active": pos.trailing_active,
                                "trailing_peak": pos.trailing_peak,
                                "entry_atr": pos._entry_atr,
                                "breakeven_applied": pos._breakeven_applied,
                                "partial_closed": True,
                                "entry_regime": pos._entry_regime,
                            })
                    else:
                        # Tam kapama (SL, TP2, Trailing)
                        logger.warning(f"[EXIT] {symbol} {pos.side}: {exit_reason}")
                        trade = self.executor.close_order(symbol, price, exit_reason)
                        if trade:
                            self._on_trade_closed(trade, exit_reason)
                            self.db.delete_position(symbol)

            # Funding fee simülasyonu (her 8 saatte bir)
            if symbol in self.state.positions:
                self._apply_funding_fee(symbol, price)

        except Exception as e:
            logger.error(f"[TICK] Error processing {symbol} @ {price}: {e}")
            self._send_error_alert(f"TICK HATASI: {symbol} @ ${price}\n{e}")

    def _on_candle_close(self, symbol: str, candle: Candle):
        """Called when a 4h candle closes - run all strategies + smart exit check + time exit"""
        try:
            asyncio.create_task(self._evaluate_strategies(symbol))
            # Smart Exit: regime change kontrolü (mevcut pozisyonlar için)
            if config.SMART_EXIT_ENABLED and symbol in self.state.positions:
                asyncio.create_task(self._check_smart_exit(symbol))
            # Time Exit: max hold candle kontrolü
            max_hold = getattr(config, 'MAX_HOLD_CANDLES', 0)
            if max_hold > 0 and symbol in self.state.positions:
                asyncio.create_task(self._check_time_exit(symbol, max_hold))
        except RuntimeError as e:
            logger.error(f"[CANDLE] Strategy task creation failed: {e}")

    async def _check_smart_exit(self, symbol: str):
        """
        Smart Exit: Regime değiştiğinde akıllı çıkış.
        - Kârdaysa → pozisyonu kapat (regime change exit)
        - Zarardaysa → TP'yi yeni regime'e göre daralt, SL'yi değiştirme
        """
        if symbol not in self.state.positions:
            return

        pos = self.state.positions[symbol]
        entry_regime = getattr(pos, '_entry_regime', '')

        if not entry_regime:
            return  # Eski pozisyon, regime bilgisi yok

        # Mevcut regime'i tespit et
        df = self.candles_4h.get_dataframe(symbol, 100)
        if df is None:
            return
        current_regime = detect_regime(df)

        # Regime değişmemişse → hiçbir şey yapma
        if current_regime == entry_regime:
            return

        price = df["close"].iloc[-1]
        pos.update_pnl(price)

        logger.info(
            f"[SMART-EXIT] {symbol}: regime {entry_regime} → {current_regime} | "
            f"PnL=${pos.unrealized_pnl:.2f}"
        )

        if pos.unrealized_pnl > 0:
            # KÂRDA → pozisyonu kapat
            logger.warning(
                f"[SMART-EXIT] {symbol} KÂRDA KAPATILIYOR: "
                f"regime {entry_regime}→{current_regime}, PnL=${pos.unrealized_pnl:.2f}"
            )
            reason = f"SMART-EXIT: regime {entry_regime}→{current_regime} (kârda)"
            trade = self.executor.close_order(symbol, price, reason)
            if trade:
                self._on_trade_closed(trade, reason)
                self.db.delete_position(symbol)
        else:
            # ZARARDA → TP'yi yeni regime'e göre daralt (SL değişmez)
            new_rr = config.DYNAMIC_RR.get(current_regime, None)
            if new_rr and pos._entry_atr > 0:
                new_tp_dist = pos._entry_atr * new_rr["tp"]
                if pos.side == "LONG":
                    new_tp = pos.entry_price + new_tp_dist
                    if new_tp < pos.take_profit:
                        old_tp = pos.take_profit
                        pos.take_profit = new_tp
                        # TP1'i de güncelle
                        pos.take_profit_1 = pos.entry_price + new_tp_dist * config.PARTIAL_TP_RATIO
                        logger.info(
                            f"[SMART-EXIT] {symbol} TP DARALTILDI: "
                            f"${old_tp:.2f} → ${new_tp:.2f} (regime→{current_regime})"
                        )
                else:  # SHORT
                    new_tp = pos.entry_price - new_tp_dist
                    if new_tp > pos.take_profit:
                        old_tp = pos.take_profit
                        pos.take_profit = new_tp
                        pos.take_profit_1 = pos.entry_price - new_tp_dist * config.PARTIAL_TP_RATIO
                        logger.info(
                            f"[SMART-EXIT] {symbol} TP DARALTILDI: "
                            f"${old_tp:.2f} → ${new_tp:.2f} (regime→{current_regime})"
                        )

                # entry_regime'i güncelle (tekrar tekrar tetiklenmesin)
                pos._entry_regime = current_regime

                # DB güncelle
                self.db.save_position(symbol, {
                    "side": pos.side, "entry_price": pos.entry_price,
                    "size": pos.size, "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "take_profit_1": pos.take_profit_1,
                    "entry_time": pos.entry_time.isoformat(),
                    "strategy": pos.strategy,
                    "trailing_active": pos.trailing_active,
                    "trailing_peak": pos.trailing_peak,
                    "entry_atr": pos._entry_atr,
                    "breakeven_applied": pos._breakeven_applied,
                    "partial_closed": pos._partial_closed,
                    "entry_regime": pos._entry_regime,
                })

    async def _check_time_exit(self, symbol: str, max_hold: int):
        """Time Exit: MAX_HOLD_CANDLES'ı aşan pozisyonları kapat"""
        if symbol not in self.state.positions:
            return
        pos = self.state.positions[symbol]
        # Candle sayacını artır
        candles_held = getattr(pos, '_candles_held', 0) + 1
        pos._candles_held = candles_held

        if candles_held >= max_hold:
            price = pos.entry_price  # Fallback
            df = self.candles_4h.get_dataframe(symbol, 5)
            if df is not None and len(df) > 0:
                price = df["close"].iloc[-1]

            logger.warning(
                f"[TIME-EXIT] {symbol} {pos.side}: {candles_held} candle holding → market close"
            )
            trade = self.executor.close_order(symbol, price,
                                              f"TIME-EXIT: {candles_held} candle")
            if trade:
                self._on_trade_closed(trade, f"TIME-EXIT: {candles_held} candle")
                self.db.delete_position(symbol)

    def _on_candle_close_1h(self, symbol: str, candle: Candle):
        """Called when a 1h candle closes - run mean reversion strategies (RANGING only)"""
        try:
            asyncio.create_task(self._evaluate_strategies_1h(symbol))
        except RuntimeError as e:
            logger.error(f"[1H-CANDLE] Strategy task creation failed: {e}")

    async def _evaluate_strategies_1h(self, symbol: str):
        """Run RSI + VWAP on 1h candle close — ONLY in RANGING regime"""
        # 4h data for regime detection
        if not self.candles_4h.has_enough_data(symbol):
            return

        df_4h = self.candles_4h.get_dataframe(symbol, 100)
        if df_4h is None:
            return

        regime = detect_regime(df_4h)

        # 1h sinyaller SADECE RANGING'de (mean reversion territory)
        if regime != "RANGING":
            return

        # Zaten pozisyon varsa skip
        if symbol in self.state.positions:
            return

        # 1h data
        df_1h = self.candles_1h.get_dataframe(symbol, 100)
        if df_1h is None or len(df_1h) < 30:
            return

        # [v15.9] Volume quality filter — 1h de aynı kural
        min_vol_ratio = getattr(config, 'MIN_VOLUME_RATIO', 0)
        if min_vol_ratio > 0 and len(df_1h) >= 20:
            vol_avg = df_1h["volume"].tail(20).mean()
            vol_current = df_1h["volume"].iloc[-1]
            if vol_avg <= 0 or (vol_current / vol_avg) < min_vol_ratio:
                return

        price = df_1h["close"].iloc[-1]
        logger.info(f"[1H-CANDLE] {symbol} closed @ ${price:.4f} | regime={regime}")

        # ATR from 1h
        atr_series = calc_atr(df_1h)
        current_atr = atr_series.iloc[-1] if not atr_series.empty else 0.0

        # Sadece RSI + VWAP çalıştır (mean reversion stratejileri)
        signals = []
        for strategy in self.strategies:
            if strategy.name not in ("RSI", "VWAP"):
                continue
            try:
                sig = strategy.evaluate(df_1h, symbol, regime)
                if sig.atr == 0.0:
                    sig.atr = current_atr
                signals.append(sig)
            except Exception as e:
                logger.error(f"[1H-STRATEGY] {strategy.name} error on {symbol}: {e}")

        # 1h voting — sadece VWAP aktif (RSI, RANGING'de sinyal üretmez)
        weights_1h = {"RSI": 0.0, "VWAP": 1.0}
        combined = combine_signals(signals, regime, weights_1h)

        if combined.action == "NONE":
            return

        # Korelasyon filtresi — config'den oku (1h)
        for group in getattr(config, 'CORRELATION_GROUPS', []):
            if symbol in group:
                for other in group:
                    if other != symbol and other in self.state.positions:
                        logger.info(f"[1H-KORELASYON] {symbol}: {other} zaten acik (grup: {group}) — atlanir")
                        return

        # Risk kontrolu
        approved, reason, params = self.risk.check(combined, self.state, regime)
        if not approved:
            return

        # 1h trades: %50 daha küçük pozisyon (daha kısa holding süresi)
        params["size"] *= 0.50

        # Emri gerçekleştir
        result = self.executor.open_order(params)

        if result["status"] == "FILLED":
            pos = result["position"]
            self.db.save_position(symbol, {
                "side": pos.side, "entry_price": pos.entry_price,
                "size": pos.size, "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "take_profit_1": pos.take_profit_1,
                "entry_time": pos.entry_time.isoformat(),
                "strategy": f"1H_{combined.strategy}",
                "trailing_active": pos.trailing_active,
                "trailing_peak": pos.trailing_peak,
                "entry_atr": pos._entry_atr,
                "breakeven_applied": pos._breakeven_applied,
                "partial_closed": pos._partial_closed,
                "entry_regime": pos._entry_regime,
            })

            self.db.log_event("OPEN_1H", f"{pos.side} {symbol} @ ${pos.entry_price:.4f} (1h signal)")

            logger.info(
                f"[1H-TRADE] OPENED {pos.side} {symbol} @ ${pos.entry_price:.4f} "
                f"SL=${pos.stop_loss:.4f} TP=${pos.take_profit:.4f} "
                f"size={pos.size:.6f} (1h mean reversion)"
            )

            # Telegram bildirimi
            asyncio.create_task(
                telegram.trade_alert(
                    symbol, pos.side,
                    pos.entry_price, 0.0,
                    0.0,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                    risk_pct=config.RISK_PER_TRADE_PCT * 100,
                )
            )

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

        # TREND_UP block — backtest v3: %30.7 WR, -$842
        if getattr(config, 'TREND_UP_BLOCK', False) and regime == "TREND_UP":
            logger.info(f"[BLOCK] {symbol}: TREND_UP girişi engellendi (TREND_UP_BLOCK=True)")
            return

        # Coin blacklist — backtest v3: WR<%30 coinler
        if symbol in getattr(config, 'COIN_BLACKLIST', []):
            logger.info(f"[BLOCK] {symbol}: Blacklist'te — atlandı")
            return

        # [v15.9] Volume quality filter — düşük hacimde trade açma
        min_vol_ratio = getattr(config, 'MIN_VOLUME_RATIO', 0)
        if min_vol_ratio > 0 and len(df) >= 20:
            vol_avg = df["volume"].tail(20).mean()
            vol_current = df["volume"].iloc[-1]
            if vol_avg <= 0 or (vol_current / vol_avg) < min_vol_ratio:
                logger.info(f"[BLOCK] {symbol}: Düşük hacim (avg={vol_avg:.2f}, cur={vol_current:.2f}, ratio={vol_current/vol_avg if vol_avg > 0 else 0:.2f} < {min_vol_ratio}) — atlandı")
                return

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
                self._send_error_alert(f"STRATEJİ HATASI: {strategy.name} / {symbol}\n{e}")

        # Regime-based agirlikli oylama (config'den)
        weights = config.REGIME_WEIGHTS.get(regime, {
            "RSI": 0.25,
            "MOMENTUM": 0.25,
            "VWAP": 0.25,
            "EDGE_DISCOVERY": 0.25,
        })
        combined = combine_signals(signals, regime, weights)

        if combined.action == "NONE":
            return

        # Korelasyon filtresi — config'den oku
        for group in getattr(config, 'CORRELATION_GROUPS', []):
            if symbol in group:
                for other in group:
                    if other != symbol and other in self.state.positions:
                        logger.info(f"[KORELASYON] {symbol}: {other} zaten acik (grup: {group}) — atlanir")
                        return

        # Risk kontrolu
        approved, reason, params = self.risk.check(combined, self.state, regime)

        if not approved:
            return

        # MTF Confirmation Gate: 15m onay bekleniyor
        if MTF_ENABLED:
            # Sinyal kuyruğa eklenir, 15m candle close'da kontrol edilir
            self.mtf.add_pending(
                symbol, combined.action, combined.confidence,
                combined.strategy, regime, params,
            )
            # İlk kontrol: mevcut 15m verisiyle hemen dene
            df_15m = self.candles_15m.get_dataframe(symbol, 50)
            if df_15m is not None and len(df_15m) >= 20:
                confirmed, mtf_reason = self.mtf.check_confirmation(symbol, df_15m)
                if confirmed:
                    logger.info(f"[MTF] {symbol}: Immediate confirmation! {mtf_reason}")
                    await self._execute_trade(symbol, params, combined.strategy)
                else:
                    logger.info(f"[MTF] {symbol}: Waiting for 15m confirmation... {mtf_reason}")
            return

        # MTF disabled → direkt execute
        await self._execute_trade(symbol, params, combined.strategy)

    async def _execute_trade(self, symbol: str, params: dict, strategy_name: str):
        """Execute a trade (called after MTF confirmation or directly)"""
        result = self.executor.open_order(params)

        if result["status"] == "FILLED":
            pos = result["position"]
            self.db.save_position(symbol, {
                "side": pos.side, "entry_price": pos.entry_price,
                "size": pos.size, "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "take_profit_1": pos.take_profit_1,
                "entry_time": pos.entry_time.isoformat(),
                "strategy": strategy_name,
                "trailing_active": pos.trailing_active,
                "trailing_peak": pos.trailing_peak,
                "entry_atr": pos._entry_atr,
                "breakeven_applied": pos._breakeven_applied,
                "partial_closed": pos._partial_closed,
                "entry_regime": pos._entry_regime,
            })

            self.db.log_event("OPEN", f"{pos.side} {symbol} @ ${pos.entry_price:.4f}")

            # Trade Journal
            from strategies.indicators import calc_rsi, calc_ema
            from data.sentiment import fear_greed
            df = self.candles_4h.get_dataframe(symbol, 100)
            atr_s = calc_atr(df) if df is not None else pd.Series()
            current_atr = atr_s.iloc[-1] if not atr_s.empty else 0.0
            regime = params.get("entry_regime", "RANGING")
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
                regime, strategy_name, 0.0,
                indicators, pos.stop_loss, pos.take_profit,
                0.02, f"MTF confirmed" if MTF_ENABLED else "Direct entry",
            )

            logger.info(
                f"[TRADE] OPENED {pos.side} {symbol} @ ${pos.entry_price:.4f} "
                f"SL=${pos.stop_loss:.4f} TP=${pos.take_profit:.4f} "
                f"size={pos.size:.6f} strategy={strategy_name}"
            )

            # Telegram bildirimi
            asyncio.create_task(
                telegram.trade_alert(
                    symbol, pos.side,
                    pos.entry_price, 0.0,
                    0.0,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                    risk_pct=config.RISK_PER_TRADE_PCT * 100,
                )
            )

    def _on_candle_close_15m(self, symbol: str, candle: Candle):
        """Called when a 15m candle closes — check MTF pending signals"""
        if not MTF_ENABLED:
            return
        if not self.mtf.has_pending(symbol):
            return
        try:
            asyncio.create_task(self._check_mtf_confirmation(symbol))
        except RuntimeError as e:
            logger.error(f"[15M-CANDLE] MTF task creation failed: {e}")

    async def _check_mtf_confirmation(self, symbol: str):
        """Check 15m confirmation for pending signal"""
        if symbol in self.state.positions:
            # Pozisyon zaten açılmış (başka timeframe)
            if self.mtf.has_pending(symbol):
                del self.mtf.pending[symbol]
            return

        df_15m = self.candles_15m.get_dataframe(symbol, 50)
        if df_15m is None or len(df_15m) < 20:
            return

        # Get params BEFORE check (check might delete pending)
        params = self.mtf.get_pending_params(symbol)
        strategy = self.mtf.pending[symbol].strategy if symbol in self.mtf.pending else "VOTE"

        confirmed, mtf_reason = self.mtf.check_confirmation(symbol, df_15m)

        if confirmed and params:
            # Fiyat güncellemesi (15m mum kapanış fiyatı kullanılacak)
            current_price = df_15m["close"].iloc[-1]
            # SL/TP'yi yeni fiyata göre yeniden hesapla
            atr = params.get("atr", current_price * 0.02)
            regime = params.get("entry_regime", "RANGING")
            rr = config.DYNAMIC_RR.get(regime, {"sl": 1.5, "tp": 3.0})
            sl_dist = atr * rr["sl"]
            tp_dist = atr * rr["tp"]
            min_sl = current_price * 0.005
            if sl_dist < min_sl:
                scale = min_sl / sl_dist
                sl_dist = min_sl
                tp_dist *= scale

            if params["action"] == "LONG":
                params["price"] = current_price
                params["stop_loss"] = current_price - sl_dist
                params["take_profit"] = current_price + tp_dist
                params["take_profit_1"] = current_price + tp_dist * config.PARTIAL_TP_RATIO
            else:
                params["price"] = current_price
                params["stop_loss"] = current_price + sl_dist
                params["take_profit"] = current_price - tp_dist
                params["take_profit_1"] = current_price - tp_dist * config.PARTIAL_TP_RATIO

            await self._execute_trade(symbol, params, f"MTF_{strategy}")

    def _apply_funding_fee(self, symbol: str, price: float):
        """Simulate 8-hourly funding fee deduction (Binance futures reality)"""
        if symbol not in self.state.positions:
            return
        pos = self.state.positions[symbol]
        now = datetime.now()

        # İlk funding zamanı: pozisyon açılışından itibaren
        if pos._last_funding_time is None:
            pos._last_funding_time = pos.entry_time

        elapsed = (now - pos._last_funding_time).total_seconds()
        if elapsed >= config.FUNDING_FEE_INTERVAL:
            notional = pos.size * price
            fee = notional * config.FUNDING_FEE_RATE
            self.state.balance -= fee
            pos._total_funding_paid += fee
            pos._last_funding_time = now
            logger.info(
                f"[FUNDING] {symbol}: -${fee:.4f} (toplam: ${pos._total_funding_paid:.4f}) | "
                f"notional=${notional:.2f}"
            )

    def _send_error_alert(self, error_msg: str):
        """Kritik hata → Telegram uyarısı (flood korumalı)"""
        import time
        now = time.time()
        if not hasattr(self, '_last_error_alert'):
            self._last_error_alert = 0
            self._error_count = 0
        self._error_count += 1
        # 5 dakikada 1'den fazla uyarı gönderme (flood koruması)
        if now - self._last_error_alert < 300:
            return
        self._last_error_alert = now
        try:
            asyncio.create_task(
                telegram.system_alert(
                    "KRİTİK HATA",
                    f"{error_msg}\n\nToplam hata: {self._error_count}\nZaman: {datetime.now().strftime('%H:%M:%S')}"
                )
            )
        except Exception:
            pass

    def _on_trade_closed(self, trade, reason: str):
        """Handle trade completion - record, notify, track"""
        self.performance.record_trade(trade.net_pnl)
        self.risk.record_trade_result(trade.net_pnl, trade.symbol)

        # Adaptive learning
        df = self.candles_4h.get_dataframe(trade.symbol, 100)
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
