"""
opportunity_scanner.py - Opportunity Scanner (Fırsat Avcısı)
=============================================================
Scans coins OUTSIDE the main 33 list for opportunities.
If a better opportunity is found and max positions are full,
closes the least profitable open position to make room.

Runs every 5 minutes as a background task.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

import requests
import pandas as pd

import config
from engine.signal import Signal
from strategies.regime import detect_regime
from strategies.indicators import calc_rsi, calc_ema, calc_bollinger, calc_atr

logger = logging.getLogger(__name__)

# Extra coins to scan (not in main SYMBOLS list)
SCAN_COINS = [
    "RUNEUSDT", "SUIUSDT", "SEIUSDT", "TIAUSDT", "JUPUSDT",
    "WLDUSDT", "STXUSDT", "IMXUSDT", "KASUSDT", "PENDLEUSDT",
    "ENAUSDT", "WIFUSDT", "BONKUSDT", "FLOKIUSDT", "ORDIUSDT",
]

SCAN_INTERVAL = 300  # 5 minutes


def fetch_klines_quick(symbol: str, limit: int = 50) -> Optional[pd.DataFrame]:
    """Fetch klines for quick analysis"""
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": "1m", "limit": limit},
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or len(data) < 30:
            return None
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qv", "trades", "tbb", "tbq", "ignore",
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df
    except Exception:
        return None


def score_opportunity(df: pd.DataFrame) -> Dict:
    """Score a coin for opportunity quality (0-100)"""
    if df is None or len(df) < 30:
        return {"score": 0, "direction": "NONE", "reason": "insufficient data"}

    closes = df["close"]
    price = closes.iloc[-1]

    # RSI
    rsi = calc_rsi(closes).iloc[-1]
    if pd.isna(rsi):
        rsi = 50.0

    # EMA momentum
    ema9 = calc_ema(closes, 9).iloc[-1]
    ema21 = calc_ema(closes, 21).iloc[-1]

    # Regime
    regime = detect_regime(df)

    # BB position
    upper, middle, lower, bw = calc_bollinger(closes)
    bb_upper = upper.iloc[-1]
    bb_lower = lower.iloc[-1]

    # Volume spike
    vol_avg = df["volume"].iloc[-21:-1].mean()
    vol_curr = df["volume"].iloc[-1]
    vol_ratio = vol_curr / (vol_avg + 1e-10)

    score = 0
    direction = "NONE"
    reasons = []

    # SHORT opportunity: overbought + downtrend + volume
    if rsi > 70 and regime in ("TREND_DOWN", "RANGING"):
        score += 30
        direction = "SHORT"
        reasons.append(f"RSI={rsi:.0f}")
    if price < ema9 < ema21:
        score += 20
        if direction == "NONE":
            direction = "SHORT"
        reasons.append("EMA bearish")
    if price < bb_lower and direction in ("SHORT", "NONE"):
        score += 15
        reasons.append("below BB")

    # LONG opportunity: oversold + uptrend + volume
    if rsi < 30 and regime in ("TREND_UP", "RANGING"):
        score += 30
        direction = "LONG"
        reasons.append(f"RSI={rsi:.0f}")
    if price > ema9 > ema21:
        score += 20
        if direction == "NONE":
            direction = "LONG"
        reasons.append("EMA bullish")
    if price > bb_upper and direction in ("LONG", "NONE"):
        score += 15
        reasons.append("above BB")

    # Volume confirmation
    if vol_ratio > 1.5:
        score += 15
        reasons.append(f"vol={vol_ratio:.1f}x")

    # Regime bonus
    if regime == "TREND_DOWN" and direction == "SHORT":
        score += 10
    elif regime == "TREND_UP" and direction == "LONG":
        score += 10

    return {
        "score": min(score, 100),
        "direction": direction,
        "price": price,
        "rsi": rsi,
        "regime": regime,
        "reason": " + ".join(reasons) if reasons else "no signal",
    }


async def scan_opportunities(orchestrator) -> Optional[Dict]:
    """
    Scan extra coins for opportunities.
    Returns best opportunity if score > 50.
    """
    best = None
    best_score = 50  # Minimum score to consider

    for symbol in SCAN_COINS:
        try:
            df = fetch_klines_quick(symbol)
            if df is None:
                continue

            result = score_opportunity(df)
            result["symbol"] = symbol

            if result["score"] > best_score and result["direction"] != "NONE":
                best_score = result["score"]
                best = result

            await asyncio.sleep(0.3)  # Rate limit
        except Exception as e:
            logger.debug(f"[SCAN] {symbol} error: {e}")

    return best


def find_worst_losing_position(state) -> Optional[str]:
    """
    Find the worst LOSING position (negative PnL only).
    Never closes a winning position - prevents 'winner cut' error.
    """
    if not state.positions:
        return None

    worst_symbol = None
    worst_pnl = 0.0  # Only consider negative PnL

    for symbol, pos in state.positions.items():
        if pos.unrealized_pnl < worst_pnl:
            worst_pnl = pos.unrealized_pnl
            worst_symbol = symbol

    return worst_symbol  # None if all positions are profitable


async def opportunity_loop(orchestrator):
    """Background loop: scan for opportunities every 5 minutes"""
    await asyncio.sleep(120)  # Wait 2 min after startup

    while True:
        try:
            opp = await scan_opportunities(orchestrator)

            if opp and opp["score"] > 50:
                state = orchestrator.state
                logger.info(
                    f"[SCAN] Opportunity: {opp['symbol']} {opp['direction']} "
                    f"score={opp['score']} ({opp['reason']})"
                )

                # If max positions reached, only swap a LOSING position (never cut winners)
                if len(state.positions) >= config.MAX_POSITIONS:
                    worst = find_worst_losing_position(state)
                    if worst and state.positions[worst].unrealized_pnl < -2.0:
                        logger.info(
                            f"[SCAN] Would close {worst} (PnL=${state.positions[worst].unrealized_pnl:.2f}) "
                            f"for {opp['symbol']} opportunity"
                        )
                        # Close worst position
                        price = state.positions[worst].unrealized_pnl  # Current price from state
                        current_price = orchestrator.candles.get_current_price(worst)
                        if current_price:
                            trade = orchestrator.executor.close_order(
                                worst, current_price,
                                f"SWAP for {opp['symbol']} opportunity (score={opp['score']})"
                            )
                            if trade:
                                orchestrator._on_trade_closed(trade, f"SWAP for {opp['symbol']}")
                                orchestrator.db.delete_position(worst)

        except Exception as e:
            logger.error(f"[SCAN] Error: {e}")

        await asyncio.sleep(SCAN_INTERVAL)
