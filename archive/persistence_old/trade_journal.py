"""
trade_journal.py - Trade Context Logger
==========================================
Records WHY a trade was opened and HOW it closed.
Stores indicator values, regime, strategy votes, confidence.
This data enables future learning and strategy optimization.

Based on: crypto_fund/src/core/trade_journal.py (adapted, no external deps)
"""

import sqlite3
import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger(__name__)

DB_PATH = config.DB_PATH

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trade_journal (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT NOT NULL,
    side         TEXT NOT NULL,
    entry_price  REAL,
    entry_time   TEXT,
    regime       TEXT,
    strategy     TEXT,
    confidence   REAL,
    rsi_value    REAL,
    ema9         REAL,
    ema21        REAL,
    atr_value    REAL,
    fear_greed   INTEGER,
    sl_price     REAL,
    tp_price     REAL,
    position_pct REAL,
    reason       TEXT,
    exit_price   REAL,
    exit_time    TEXT,
    exit_reason  TEXT,
    net_pnl      REAL,
    duration_s   REAL
);
"""


def _ensure_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute(_CREATE_SQL)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[JOURNAL] Table creation error: {e}")


def record_entry(symbol: str, side: str, entry_price: float,
                 regime: str, strategy: str, confidence: float,
                 indicators: dict, sl: float, tp: float,
                 position_pct: float, reason: str) -> int:
    """
    Record trade entry with full context.
    Returns journal_id for later update.
    """
    _ensure_table()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.execute("""
            INSERT INTO trade_journal
              (symbol, side, entry_price, entry_time, regime, strategy,
               confidence, rsi_value, ema9, ema21, atr_value, fear_greed,
               sl_price, tp_price, position_pct, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            symbol, side, entry_price, datetime.now().isoformat(),
            regime, strategy, confidence,
            indicators.get("rsi", 0.0),
            indicators.get("ema9", 0.0),
            indicators.get("ema21", 0.0),
            indicators.get("atr", 0.0),
            indicators.get("fear_greed", 50),
            sl, tp, position_pct, reason,
        ))
        journal_id = cur.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"[JOURNAL] Entry #{journal_id}: {side} {symbol} @ ${entry_price:.2f} [{regime}]")
        return journal_id
    except Exception as e:
        logger.error(f"[JOURNAL] Write error: {e}")
        return -1


def record_exit(journal_id: int, exit_price: float, exit_reason: str,
                net_pnl: float, duration_s: float):
    """Update journal with exit data."""
    if journal_id < 0:
        return
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("""
            UPDATE trade_journal
            SET exit_price=?, exit_time=?, exit_reason=?, net_pnl=?, duration_s=?
            WHERE id=?
        """, (exit_price, datetime.now().isoformat(), exit_reason, net_pnl, duration_s, journal_id))
        conn.commit()
        conn.close()
        logger.info(f"[JOURNAL] Exit #{journal_id}: PnL=${net_pnl:.2f} ({exit_reason})")
    except Exception as e:
        logger.error(f"[JOURNAL] Update error: {e}")


def get_learning_data(limit: int = 100) -> list:
    """Get completed trades with full context for analysis."""
    _ensure_table()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        rows = conn.execute("""
            SELECT symbol, side, regime, strategy, confidence,
                   rsi_value, ema9, ema21, atr_value, fear_greed,
                   net_pnl, duration_s, exit_reason
            FROM trade_journal
            WHERE net_pnl IS NOT NULL
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()

        cols = ["symbol", "side", "regime", "strategy", "confidence",
                "rsi", "ema9", "ema21", "atr", "fear_greed",
                "net_pnl", "duration_s", "exit_reason"]
        return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        logger.error(f"[JOURNAL] Read error: {e}")
        return []


_ensure_table()
