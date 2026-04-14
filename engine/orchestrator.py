"""orchestrator.py - War Machine v0 (COMBO V1)
========================================
Sadeleştirilmiş orchestrator. Combo V1 (5 mean-reversion strateji).

Flow:
  Tick -> CandleManager -> 4h Candle closes -> Regime detect ->
  ComboV1 evaluate -> Pre-trade risk -> Execute -> Database + Telegram

Dinamik Coin:
  Her 6 saatte top volume coinleri tarar, listeyi günceller.
"""

import asyncio
import logging
from datetime import datetime

import requests
import config
from data.candle_manager import CandleManager, Candle
from data.datafeed import DataFeed
from engine.state import TradingState
from engine.signal import Signal
from strategies.regime import detect_regime
from strategies.combo_v1 import ComboV1Strategy
from strategies.indicators import calc_atr
from risk.pre_trade import PreTradeRisk
from risk.stop_manager import check_exit
from risk.position_sizer import DynamicPositionSizer
from execution.paper import PaperExecutor
from persistence.database import Database
from monitoring.telegram import telegram
from monitoring.performance import PerformanceTracker

logger = logging.getLogger(__name__)


class Orchestrator:
    """v0: Minimal orchestrator — tek strateji, temiz akış"""

    def __init__(self):
        self._running = False
        self._tick_count = 0

        # Core state
        self.state = TradingState()
        self.db = Database()
        self.performance = PerformanceTracker(config.INITIAL_BALANCE)
        self.risk = PreTradeRisk()
        self.executor = PaperExecutor(self.state)
        self.sizer = DynamicPositionSizer()

        # Tek candle manager: 4h
        self.candles_4h = CandleManager(
            symbols=config.SYMBOLS,
            on_candle_close=self._on_candle_close,
            interval=config.CANDLE_INTERVAL,
            max_candles=config.CANDLE_MAX_STORED,
        )

        # Datafeed
        self.feed = DataFeed(
            symbols=config.SYMBOLS,
            on_tick=self._on_tick_sync,
        )
        self.feed._telegram_alert = lambda msg: telegram.send(msg)

        # TEK strateji: Combo V1 (5 mean-reversion)
        self.strategy = ComboV1Strategy()

        # Restore positions from database
        self._restore_positions()
        self._restore_performance()

    def _restore_positions(self):
        """Load saved positions from database"""
        saved = self.db.load_positions()
        for symbol, pos_data in saved.items():
            self.state.restore_position(symbol, pos_data)
            pos = self.state.positions.get(symbol)
            if pos and pos.entry_time:
                elapsed = (datetime.now() - pos.entry_time).total_seconds()
                candle_secs = 4 * 3600
                pos._candles_held = int(elapsed / candle_secs)
                logger.info(f"[RESTORE] {symbol} {pos_data['side']} (candles_held={pos._candles_held})")
        if saved:
            logger.info(f"[RESTORE] {len(saved)} positions restored from DB")

    def _restore_performance(self):
        """Reload past trade PnLs into PerformanceTracker"""
        trades = self.db.get_trades(limit=500)
        if not trades:
            return
        for t in reversed(trades):
            self.performance.record_trade(t["net_pnl"])
        self.state._reload_from_db(self.db)
        logger.info(
            f"[RESTORE] Performance: {self.performance.total_trades} trades, "
            f"PnL=${self.performance.total_pnl:.2f}, WR={self.performance.win_rate:.1f}%"
        )

    async def start(self):
        """Start the war machine v0"""
        self._running = True

        logger.info("=" * 60)
        logger.info("WAR MACHINE v0 — COMBO V1 MODE")
        logger.info(f"Mode: {'LIVE' if config.REAL_TRADING_ENABLED else 'PAPER'}")
        logger.info(f"Balance: ${config.INITIAL_BALANCE:,.2f}")
        logger.info(f"Symbols: {len(config.SYMBOLS)} coins")
        logger.info(f"Strategy: {self.strategy.name} (5 sub-strategies)")
        logger.info(f"MAX_HOLD: {config.MAX_HOLD_CANDLES} candle (4h)")
        logger.info(f"SL/TP: 1.0 ATR each")
        logger.info(f"Dynamic coins: {'ON' if config.DYNAMIC_COIN_ENABLED else 'OFF'}")
        logger.info("=" * 60)

        self._start_time = datetime.now()

        # Initialize 4h candle histories
        await self.candles_4h.initialize()

        # Telegram startup alert
        asyncio.create_task(telegram.startup_alert())

        # Start health report (only basic)
        from monitoring.health import health_loop, summary_loop
        asyncio.create_task(health_loop(self))
        asyncio.create_task(summary_loop(self))

        # Dinamik coin keşfi
        if config.DYNAMIC_COIN_ENABLED:
            asyncio.create_task(self._dynamic_coin_loop())

        # Start WebSocket feed
        await self.feed.start()

        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the war machine"""
        logger.info("[ENGINE] Shutting down...")
        self._running = False
        await self.feed.stop()

        # Save all open positions
        for symbol, pos in self.state.positions.items():
            self._save_position(symbol, pos)
        logger.info(f"[ENGINE] {len(self.state.positions)} positions saved to DB")

        status = self.state.get_status()
        logger.info("=" * 60)
        logger.info("FINAL STATS")
        logger.info(f"Balance: ${status['balance']:,.2f}")
        logger.info(f"PnL: ${status['total_pnl']:,.2f}")
        logger.info(f"Trades: {status['total_trades']} (W:{status['wins']} L:{status['losses']})")
        logger.info(f"Win Rate: {status['win_rate']:.1f}%")
        logger.info("=" * 60)

    def _on_tick_sync(self, symbol: str, price: float, volume: float = 0.0):
        """Sync wrapper for async tick handler"""
        try:
            asyncio.create_task(self._on_tick(symbol, price, volume))
        except RuntimeError:
            pass

    async def _on_tick(self, symbol: str, price: float, volume: float = 0.0):
        """Handle every tick — update candles + check exits"""
        try:
            self._tick_count += 1
            self.state.update_price(symbol, price)
            self.candles_4h.on_tick(symbol, price, volume)
            self.performance.update_equity(self.state.equity)

            # Log performance every 500 ticks
            if self._tick_count % 500 == 0:
                self.performance.log_summary(self._tick_count)

            # SL/TP check
            if symbol in self.state.positions:
                pos = self.state.positions[symbol]
                exit_reason = check_exit(pos, price)

                if exit_reason:
                    logger.warning(f"[EXIT] {symbol} {pos.side}: {exit_reason}")
                    trade = self.executor.close_order(symbol, price, exit_reason)
                    if trade:
                        self._on_trade_closed(trade, exit_reason)
                        self.db.delete_position(symbol)

            # Funding fee
            if symbol in self.state.positions:
                self._apply_funding_fee(symbol, price)

        except Exception as e:
            logger.error(f"[TICK] Error {symbol} @ {price}: {e}")

    def _on_candle_close(self, symbol: str, candle: Candle):
        """Called when a 4h candle closes"""
        try:
            asyncio.create_task(self._evaluate(symbol))
            # Time exit check
            max_hold = getattr(config, 'MAX_HOLD_CANDLES', 0)
            if max_hold > 0 and symbol in self.state.positions:
                asyncio.create_task(self._check_time_exit(symbol, max_hold))
        except RuntimeError:
            pass

    async def _evaluate(self, symbol: str):
        """Run ScalpV0 strategy on 4h candle close"""
        if not self.candles_4h.has_enough_data(symbol):
            return

        df = self.candles_4h.get_dataframe(symbol, 100)
        if df is None:
            return

        regime = detect_regime(df)
        price = df["close"].iloc[-1]
        logger.info(f"[CANDLE] {symbol} @ ${price:.4f} | regime={regime}")

        # Skip if already in position
        if symbol in self.state.positions:
            return

        # Run strategy
        signal = self.strategy.evaluate(df, symbol, regime)

        if signal.action == "NONE":
            return

        # Min confidence
        if signal.confidence < config.STRATEGY_MIN_CONFIDENCE:
            logger.info(f"[SKIP] {symbol}: conf={signal.confidence:.2f} < {config.STRATEGY_MIN_CONFIDENCE}")
            return

        # Risk check
        approved, reason, params = self.risk.check(signal, self.state, regime)
        if not approved:
            logger.info(f"[RISK] {symbol}: {reason}")
            return

        # Execute
        await self._execute_trade(symbol, params, signal.strategy)

    async def _execute_trade(self, symbol: str, params: dict, strategy_name: str):
        """Execute a trade"""
        result = self.executor.open_order(params)

        if result["status"] == "FILLED":
            pos = result["position"]
            self._save_position(symbol, pos)
            self.db.log_event("OPEN", f"{pos.side} {symbol} @ ${pos.entry_price:.4f}")

            logger.info(
                f"[TRADE] OPENED {pos.side} {symbol} @ ${pos.entry_price:.4f} "
                f"SL=${pos.stop_loss:.4f} TP=${pos.take_profit:.4f} "
                f"size={pos.size:.6f}"
            )

            asyncio.create_task(
                telegram.trade_alert(
                    symbol, pos.side,
                    pos.entry_price, 0.0, 0.0,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                    risk_pct=config.RISK_PER_TRADE_PCT * 100,
                )
            )

    async def _check_time_exit(self, symbol: str, max_hold: int):
        """Close position if held too long"""
        if symbol not in self.state.positions:
            return
        pos = self.state.positions[symbol]
        candles_held = getattr(pos, '_candles_held', 0) + 1
        pos._candles_held = candles_held

        if candles_held >= max_hold:
            price = pos.entry_price
            df = self.candles_4h.get_dataframe(symbol, 5)
            if df is not None and len(df) > 0:
                price = df["close"].iloc[-1]

            logger.warning(f"[TIME-EXIT] {symbol} {pos.side}: {candles_held} candle → close")
            trade = self.executor.close_order(symbol, price, f"TIME-EXIT: {candles_held}c")
            if trade:
                self._on_trade_closed(trade, f"TIME-EXIT: {candles_held}c")
                self.db.delete_position(symbol)

    def _on_trade_closed(self, trade, reason: str):
        """Handle trade completion"""
        self.performance.record_trade(trade.net_pnl)
        self.risk.record_trade_result(trade.net_pnl, trade.symbol)
        self.sizer.record_trade(trade.net_pnl)

        duration = (trade.exit_time - trade.entry_time).total_seconds()

        self.db.save_trade({
            "symbol": trade.symbol, "side": trade.side,
            "entry_price": trade.entry_price, "exit_price": trade.exit_price,
            "size": trade.size, "gross_pnl": trade.gross_pnl,
            "commission": trade.commission, "net_pnl": trade.net_pnl,
            "strategy": trade.strategy, "reason": reason,
            "duration_seconds": duration,
        })

        self.db.log_event("CLOSE", f"{trade.side} {trade.symbol} PnL=${trade.net_pnl:.4f}")

        logger.info(
            f"[TRADE] CLOSED {trade.side} {trade.symbol} "
            f"PnL=${trade.net_pnl:.2f} ({reason})"
        )

        asyncio.create_task(
            telegram.trade_alert(
                trade.symbol, trade.side,
                trade.entry_price, trade.exit_price,
                trade.net_pnl,
                stop_loss=0.0, take_profit=0.0,
                risk_pct=config.RISK_PER_TRADE_PCT * 100,
            )
        )

    def _save_position(self, symbol: str, pos):
        """Save position to DB"""
        self.db.save_position(symbol, {
            "side": pos.side, "entry_price": pos.entry_price,
            "size": pos.size, "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "take_profit_1": getattr(pos, 'take_profit_1', pos.take_profit),
            "entry_time": pos.entry_time.isoformat(),
            "strategy": pos.strategy,
            "trailing_active": pos.trailing_active,
            "trailing_peak": pos.trailing_peak,
            "entry_atr": pos._entry_atr,
            "breakeven_applied": pos._breakeven_applied,
            "partial_closed": pos._partial_closed,
            "entry_regime": pos._entry_regime,
        })

    def _apply_funding_fee(self, symbol: str, price: float):
        """Simulate 8-hourly funding fee"""
        if symbol not in self.state.positions:
            return
        pos = self.state.positions[symbol]
        now = datetime.now()

        if pos._last_funding_time is None:
            pos._last_funding_time = pos.entry_time

        elapsed = (now - pos._last_funding_time).total_seconds()
        if elapsed >= config.FUNDING_FEE_INTERVAL:
            notional = pos.size * price
            fee = notional * config.FUNDING_FEE_RATE
            self.state.balance -= fee
            pos._total_funding_paid += fee
            pos._last_funding_time = now
            logger.info(f"[FUNDING] {symbol}: -${fee:.4f}")

    async def _dynamic_coin_loop(self):
        """Her 6 saatte Binance top volume USDT futures coinlerini tarar"""
        await asyncio.sleep(300)  # İlk 5 dk bekle (candle init)
        interval = config.DYNAMIC_COIN_INTERVAL

        while self._running:
            try:
                new_coins = self._discover_top_coins()
                if new_coins:
                    added = [c for c in new_coins if c not in config.SYMBOLS]
                    removed = [c for c in config.SYMBOLS if c not in new_coins
                               and c not in self.state.positions]  # Açık pozisyon varsa çıkarma

                    if added or removed:
                        # Pozisyonu açık olanları koru
                        for sym in list(self.state.positions.keys()):
                            if sym not in new_coins:
                                new_coins.append(sym)

                        old_count = len(config.SYMBOLS)
                        config.SYMBOLS = new_coins
                        logger.info(
                            f"[DYNAMIC] Coin listesi güncellendi: {old_count}→{len(new_coins)} | "
                            f"+{added} -{removed}"
                        )

                        # Telegram bildirim
                        from monitoring.telegram import telegram
                        await telegram.send(
                            f"🔄 <b>Coin Listesi Güncellendi</b>\n"
                            f"Toplam: {len(new_coins)} coin\n"
                            f"Eklenen: {', '.join(added) if added else 'yok'}\n"
                            f"Çıkan: {', '.join(removed) if removed else 'yok'}"
                        )

                        # Yeni coinler için WebSocket + CandleManager güncelle
                        if added:
                            for sym in added:
                                self.candles_4h.add_symbol(sym)
                            # Feed'i yeniden başlat (yeni sembolleri eklemek için)
                            await self.feed.stop()
                            self.feed.symbols = [s.lower() for s in config.SYMBOLS]
                            asyncio.create_task(self.feed.start())

            except Exception as e:
                logger.error(f"[DYNAMIC] Coin discovery hatası: {e}")

            await asyncio.sleep(interval)

    def _discover_top_coins(self):
        """Binance'ten en yüksek hacimli USDT futures coinlerini al"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            tickers = resp.json()

            # USDT çiftleri, >$50M günlük hacim
            usdt_pairs = []
            for t in tickers:
                sym = t["symbol"]
                if not sym.endswith("USDT"):
                    continue
                vol_usd = float(t["quoteVolume"])
                if vol_usd < config.DYNAMIC_COIN_MIN_VOLUME:
                    continue
                # Stablecoin ve leveraged token hariç
                base = sym.replace("USDT", "")
                # ASCII olmayan semboller filtrele (bozuk Unicode coinler)
                if not sym.isascii() or not base.isalpha():
                    continue
                if base in ("USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDD",
                            "USD1", "USDP", "AEUR", "EURI", "EUR", "PAXG"):
                    continue
                if any(x in base for x in ("UP", "DOWN", "BULL", "BEAR")):
                    continue
                usdt_pairs.append((sym, vol_usd))

            # Hacme göre sırala, top N al
            usdt_pairs.sort(key=lambda x: x[1], reverse=True)
            top = [sym for sym, _ in usdt_pairs[:config.DYNAMIC_COIN_MAX]]

            # Base coinler her zaman kalır
            for base in config.DYNAMIC_COIN_BASE:
                if base not in top:
                    top.append(base)

            logger.info(f"[DYNAMIC] Tarama: {len(usdt_pairs)} USDT coin, top {len(top)} seçildi")
            return top

        except Exception as e:
            logger.error(f"[DYNAMIC] API hatası: {e}")
            return None
