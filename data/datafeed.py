"""
datafeed.py - Binance WebSocket Price Feed
=============================================
Real-time price feed with auto-reconnect.
Calls on_tick(symbol, price) for every price update.

Based on: crypto_fund/core_v2/datafeed.py (cleaned)
"""

import asyncio
import json
import logging
from typing import Callable

import config

logger = logging.getLogger(__name__)


class DataFeed:
    """
    Multi-symbol Binance WebSocket feed.
    Connects to combined stream, calls on_tick for each price update.
    Auto-reconnects with exponential backoff.
    """

    def __init__(self, symbols: list, on_tick: Callable):
        self.symbols = [s.lower() for s in symbols]
        self.on_tick = on_tick
        self._running = False
        self._ws = None
        self._reconnect_count = 0

    async def start(self):
        self._running = True
        self._reconnect_count = 0
        await self._connect()

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("[DATAFEED] Stopped")

    async def _connect(self):
        import websockets

        streams = "/".join(f"{s}@ticker" for s in self.symbols)
        uri = f"{config.WS_URI}?streams={streams}"
        delay = config.WS_RECONNECT_DELAY_MIN

        while self._running:
            try:
                logger.info(f"[DATAFEED] Connecting: {len(self.symbols)} symbols")
                async with websockets.connect(
                    uri,
                    ping_interval=config.WS_PING_INTERVAL,
                    ping_timeout=config.WS_PING_TIMEOUT,
                ) as ws:
                    self._ws = ws
                    self._reconnect_count = 0
                    delay = config.WS_RECONNECT_DELAY_MIN
                    logger.info("[DATAFEED] Connected")

                    async for msg in ws:
                        if not self._running:
                            break
                        try:
                            self._parse(msg)
                        except Exception as e:
                            logger.error(f"[DATAFEED] Parse error: {e}")

            except Exception as e:
                self._reconnect_count += 1
                logger.warning(
                    f"[DATAFEED] Disconnected (#{self._reconnect_count}): {e}. "
                    f"Retry in {delay}s"
                )

            if not self._running:
                break

            # Never give up — keep retrying with max 60s delay
            if self._reconnect_count >= config.WS_MAX_RECONNECT_ATTEMPTS:
                logger.warning(
                    f"[DATAFEED] {self._reconnect_count} failed attempts. "
                    f"Continuing with {config.WS_RECONNECT_DELAY_MAX}s interval..."
                )
                delay = config.WS_RECONNECT_DELAY_MAX
            
            await asyncio.sleep(delay)
            delay = min(delay * 2, config.WS_RECONNECT_DELAY_MAX)

    def _parse(self, raw: str):
        try:
            data = json.loads(raw)
            if "stream" in data and "data" in data:
                payload = data["data"]
                if "@ticker" in data["stream"]:
                    symbol = payload["s"].upper()
                    price = float(payload["c"])
                    volume = float(payload.get("q", 0))  # quote asset volume
                    self.on_tick(symbol, price, volume)
        except Exception as e:
            logger.error(f"[DATAFEED] Parse/callback error: {e}")
