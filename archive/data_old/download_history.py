"""
download_history.py - Download Historical Kline Data
=======================================================
Downloads OHLCV data from Binance for backtesting.
Saves to data/klines/{SYMBOL}_{interval}.csv

Usage:
  python -m data.download_history --symbol BTCUSDT --interval 1h --days 90
  python -m data.download_history --all --interval 1h --days 90

Based on: crypto_fund/scripts/download_historical_data.py (simplified)
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import requests
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("download")

KLINE_DIR = Path("data/klines")
BASE_URL = "https://api.binance.com/api/v3/klines"


def download_klines(symbol: str, interval: str = "1h", days: int = 90) -> pd.DataFrame:
    """Download klines from Binance REST API"""
    KLINE_DIR.mkdir(parents=True, exist_ok=True)

    end_ms = int(datetime.now().timestamp() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)

    all_data = []
    current = start_ms
    request_count = 0

    logger.info(f"Downloading {symbol} {interval} ({days} days)...")

    while current < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "limit": 1000,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)
            current = data[-1][0] + 1
            request_count += 1

            if request_count % 10 == 0:
                logger.info(f"  {symbol}: {len(all_data)} candles fetched...")

            time.sleep(0.25)  # Rate limit safety
        except Exception as e:
            logger.error(f"  Error: {e}")
            break

    if not all_data:
        logger.warning(f"  {symbol}: No data received")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades_count",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")

    # Save to CSV
    filepath = KLINE_DIR / f"{symbol}_{interval}.csv"
    df.to_csv(filepath, index=False)
    logger.info(f"  {symbol}: {len(df)} candles saved to {filepath}")

    return df


def main():
    parser = argparse.ArgumentParser(description="Download historical kline data")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol (or ALL for all config symbols)")
    parser.add_argument("--interval", default="1h", help="Candle interval")
    parser.add_argument("--days", type=int, default=90, help="Days of history")
    parser.add_argument("--all", action="store_true", help="Download all config symbols")
    args = parser.parse_args()

    symbols = config.SYMBOLS if args.all or args.symbol == "ALL" else [args.symbol]

    logger.info(f"Downloading {len(symbols)} symbols, {args.interval}, {args.days} days")

    for sym in symbols:
        download_klines(sym, args.interval, args.days)

    logger.info("Done!")


if __name__ == "__main__":
    main()
