"""
candle_manager.py - OHLCV Candle Manager
==========================================
Fetches historical klines from Binance REST API on startup.
Aggregates incoming ticks into real-time candles.
Provides candle DataFrames to strategies.

This is the FOUNDATION - without proper candle data, strategies produce noise.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

import requests
import pandas as pd

import config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Single OHLCV candle"""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = False


class CandleManager:
    """
    Manages OHLCV candle data for all symbols.

    Startup:
      - Fetches historical klines via Binance REST API
      - Builds candle history (100+ candles per symbol)

    Runtime:
      - Aggregates ticks into current candle
      - When candle closes, appends to history and fires callback
    """

    INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}

    def __init__(
        self,
        symbols: List[str],
        on_candle_close: Optional[Callable] = None,
        interval: str = "1m",
        max_candles: int = 200,
    ):
        self.symbols = symbols
        self.on_candle_close = on_candle_close
        self.interval = interval
        self.interval_ms = self.INTERVAL_SECONDS.get(interval, 60) * 1000
        self.max_candles = max_candles

        self.candles: Dict[str, List[Candle]] = {s: [] for s in symbols}
        self.current: Dict[str, Optional[Candle]] = {s: None for s in symbols}
        self._initialized = False

    async def initialize(self):
        """Fetch historical klines for all symbols from Binance REST API"""
        logger.info(f"[CANDLES] Loading {config.CANDLE_HISTORY_COUNT} historical {self.interval} candles for {len(self.symbols)} symbols...")

        for symbol in self.symbols:
            try:
                klines = self._fetch_klines(symbol)
                if klines:
                    for k in klines:
                        self.candles[symbol].append(Candle(
                            timestamp=k[0],
                            open=float(k[1]),
                            high=float(k[2]),
                            low=float(k[3]),
                            close=float(k[4]),
                            volume=float(k[5]),
                            closed=True,
                        ))
                    logger.info(f"[CANDLES] {symbol}: {len(self.candles[symbol])} candles loaded")
                else:
                    logger.warning(f"[CANDLES] {symbol}: no data from REST API")
            except Exception as e:
                logger.error(f"[CANDLES] {symbol}: fetch failed: {e}")

            await asyncio.sleep(0.2)

        total = sum(len(v) for v in self.candles.values())
        logger.info(f"[CANDLES] Init complete: {total} total candles")
        self._initialized = True

    def _fetch_klines(self, symbol: str) -> list:
        """Fetch klines from Binance public REST API"""
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": self.interval, "limit": config.CANDLE_HISTORY_COUNT + 1}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Exclude last (current/incomplete) candle
        return data[:-1] if len(data) > 1 else data

    def on_tick(self, symbol: str, price: float):
        """Aggregate tick into current candle. Called by datafeed."""
        if symbol not in self.candles:
            return

        now_ms = time.time() * 1000
        candle_start = (int(now_ms) // self.interval_ms) * self.interval_ms
        cur = self.current.get(symbol)
        
        # DEBUG: Log every 100th tick to understand timing
        import random
        if random.random() < 0.01:  # ~1% of ticks
            logger.debug(f"[TICK-DBG] {symbol}: now_ms={int(now_ms)}, candle_start={int(candle_start)}, cur.timestamp={int(cur.timestamp) if cur else 'None'}")

        if cur is None or cur.timestamp != candle_start:
            # Close previous candle
            if cur is not None and not cur.closed:
                cur.closed = True
                self.candles[symbol].append(cur)

                # Trim history
                if len(self.candles[symbol]) > self.max_candles:
                    self.candles[symbol] = self.candles[symbol][-self.max_candles:]

                # Fire callback
                logger.info(f"[CANDLE] {symbol} closed @ ${cur.close:.4f} | candles stored={len(self.candles[symbol])}")
                if self.on_candle_close:
                    try:
                        self.on_candle_close(symbol, cur)
                    except Exception as e:
                        logger.error(f"[CANDLES] Callback error: {e}")

            # Start new candle
            self.current[symbol] = Candle(
                timestamp=candle_start,
                open=price, high=price, low=price, close=price,
                volume=0.0, closed=False,
            )
        else:
            # Update current candle
            cur.high = max(cur.high, price)
            cur.low = min(cur.low, price)
            cur.close = price

    def get_dataframe(self, symbol: str, count: int = 50) -> Optional[pd.DataFrame]:
        """
        Get closed candle data as DataFrame.
        Returns None if insufficient data.
        """
        candles = self.candles.get(symbol, [])
        subset = candles[-count:] if len(candles) >= count else candles

        if len(subset) < 10:
            return None

        return pd.DataFrame([{
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        } for c in subset])

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get latest price (from current candle or last closed)"""
        cur = self.current.get(symbol)
        if cur:
            return cur.close
        candles = self.candles.get(symbol, [])
        return candles[-1].close if candles else None

    def has_enough_data(self, symbol: str) -> bool:
        """Check if enough candle data for strategies"""
        return len(self.candles.get(symbol, [])) >= config.MIN_CANDLES_FOR_STRATEGY