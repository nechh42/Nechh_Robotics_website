"""
binance.py - Binance Spot API Execution
==========================================
Real order execution for live trading.
Based on: crypto_fund/core_v2/binance_api.py (cleaned)

WARNING: This module sends REAL orders with REAL money.
Only enabled when config.REAL_TRADING_ENABLED = True
"""

import logging
import hmac
import hashlib
import time
import requests
from typing import Optional, Dict

import config

logger = logging.getLogger(__name__)


class BinanceExecutor:
    """Binance Spot API for real trading"""

    def __init__(self):
        self.api_key = config.BINANCE_API_KEY
        self.api_secret = config.BINANCE_API_SECRET
        self.base_url = "https://api.binance.com"
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

        if not self.api_key or not self.api_secret:
            logger.warning("[BINANCE] API keys not configured")

    def _sign(self, params: dict) -> str:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return hmac.new(
            self.api_secret.encode(), qs.encode(), hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        if signed:
            kwargs["timestamp"] = int(time.time() * 1000)
            kwargs["signature"] = self._sign(kwargs)
        try:
            if method == "GET":
                resp = self.session.get(url, params=kwargs, timeout=10)
            elif method == "POST":
                resp = self.session.post(url, params=kwargs, timeout=10)
            elif method == "DELETE":
                resp = self.session.delete(url, params=kwargs, timeout=10)
            else:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[BINANCE] API error: {e}")
            return None

    def get_balance(self, asset: str = "USDT") -> float:
        account = self._request("GET", "/api/v3/account", signed=True)
        if not account:
            return 0.0
        for b in account.get("balances", []):
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0

    def market_buy(self, symbol: str, quantity: float) -> Optional[Dict]:
        logger.info(f"[BINANCE] Market BUY {symbol}: {quantity}")
        return self._request("POST", "/api/v3/order", signed=True,
                             symbol=symbol, side="BUY", type="MARKET", quantity=quantity)

    def market_sell(self, symbol: str, quantity: float) -> Optional[Dict]:
        logger.info(f"[BINANCE] Market SELL {symbol}: {quantity}")
        return self._request("POST", "/api/v3/order", signed=True,
                             symbol=symbol, side="SELL", type="MARKET", quantity=quantity)

    def get_lot_size(self, symbol: str) -> tuple:
        info = self._request("GET", "/api/v3/exchangeInfo")
        if not info:
            return (0.001, 1000.0, 0.001)
        for s in info.get("symbols", []):
            if s["symbol"] == symbol:
                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        return (float(f["minQty"]), float(f["maxQty"]), float(f["stepSize"]))
        return (0.001, 1000.0, 0.001)

    def round_quantity(self, symbol: str, quantity: float) -> float:
        min_qty, max_qty, step = self.get_lot_size(symbol)
        quantity = round(quantity / step) * step
        return max(min_qty, min(max_qty, quantity))
