"""
sentiment.py - Fear & Greed Index Integration
================================================
Fetches real-time Fear & Greed index from alternative.me API (free, no key).
Used as additional filter: extreme fear = block buys, extreme greed = block sells.

Based on: crypto_fund/src/swarm/swarm_ai.py SentimentAgent
"""

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class FearGreedSentiment:
    """
    Fear & Greed Index from alternative.me API.
    
    Score: 0 (Extreme Fear) to 100 (Extreme Greed)
    Normalized: -1.0 (Extreme Fear) to +1.0 (Extreme Greed)
    
    Trading rules:
      - score < 20 (Extreme Fear): Block new LONG (market panic)
      - score > 80 (Extreme Greed): Block new SHORT (FOMO rally)
      - 20-80: Normal trading
    """

    CACHE_TTL = 300  # Refresh every 5 minutes

    def __init__(self):
        self._cache: Optional[int] = None
        self._cache_time: float = 0.0
        self._fetch_count = 0

    def get_score(self) -> int:
        """Get Fear & Greed score (0-100). Returns 50 on error."""
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        try:
            resp = requests.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()["data"][0]
                score = int(data["value"])
                classification = data.get("value_classification", "")
                self._cache = score
                self._cache_time = now
                self._fetch_count += 1

                if self._fetch_count <= 3 or self._fetch_count % 10 == 0:
                    logger.info(f"[SENTIMENT] Fear & Greed: {score} ({classification})")

                return score
        except Exception as e:
            logger.debug(f"[SENTIMENT] API error: {e}")

        return self._cache if self._cache is not None else 50

    def get_normalized(self) -> float:
        """Get normalized score: -1.0 (fear) to +1.0 (greed)"""
        return (self.get_score() - 50) / 50.0

    def should_block_long(self) -> bool:
        """Block LONG entries during extreme fear (score < 10)"""
        return self.get_score() < 10

    def should_block_short(self) -> bool:
        """Block SHORT entries during extreme greed (score > 90)"""
        return self.get_score() > 90

    def get_label(self) -> str:
        score = self.get_score()
        if score < 20:
            return "EXTREME_FEAR"
        elif score < 40:
            return "FEAR"
        elif score < 60:
            return "NEUTRAL"
        elif score < 80:
            return "GREED"
        else:
            return "EXTREME_GREED"


class FundingRateSentiment:
    """
    Binance Futures Funding Rate - stronger than Fear&Greed for crypto.
    funding > 0.05% → market overlong → bearish
    funding < -0.05% → market overshort → bullish
    """
    CACHE_TTL = 300  # 5 min cache

    def __init__(self):
        self._cache = {}
        self._cache_time: float = 0.0

    def get_funding(self, symbol: str = "BTCUSDT") -> float:
        """Get current funding rate. Returns 0 on error."""
        now = time.time()
        if symbol in self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache[symbol]

        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": symbol},
                timeout=5,
            )
            if resp.status_code == 200:
                rate = float(resp.json().get("lastFundingRate", 0))
                self._cache[symbol] = rate
                self._cache_time = now
                return rate
        except Exception as e:
            logger.debug(f"[FUNDING] API error: {e}")

        return self._cache.get(symbol, 0.0)

    def is_overlong(self, symbol: str = "BTCUSDT") -> bool:
        """Market is overlong (funding > 0.05%) - bearish signal"""
        return self.get_funding(symbol) > 0.0005

    def is_overshort(self, symbol: str = "BTCUSDT") -> bool:
        """Market is overshort (funding < -0.05%) - bullish signal"""
        return self.get_funding(symbol) < -0.0005


# Global singletons
fear_greed = FearGreedSentiment()
funding_rate = FundingRateSentiment()
