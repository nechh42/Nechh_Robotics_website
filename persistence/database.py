"""
database.py - SQLite Trade Persistence
========================================
Stores trades, positions, performance metrics, and system events.
Based on: crypto_fund/core_v2/database.py (cleaned)
"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

import config

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for all persistence needs"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()
        logger.info(f"[DB] Initialized: {self.db_path}")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        with self._conn() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    size REAL NOT NULL,
                    gross_pnl REAL NOT NULL,
                    commission REAL NOT NULL,
                    net_pnl REAL NOT NULL,
                    strategy TEXT,
                    reason TEXT,
                    duration_seconds REAL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    strategy TEXT,
                    trailing_active INTEGER DEFAULT 0,
                    trailing_peak REAL DEFAULT 0
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            """)
            conn.commit()

    # ─── TRADES ─────────────────────────────────────────
    def save_trade(self, trade: Dict):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO trades (timestamp, symbol, side, entry_price, exit_price,
                    size, gross_pnl, commission, net_pnl, strategy, reason, duration_seconds)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trade.get("timestamp", datetime.now().isoformat()),
                trade["symbol"], trade["side"],
                trade["entry_price"], trade["exit_price"],
                trade["size"], trade["gross_pnl"],
                trade["commission"], trade["net_pnl"],
                trade.get("strategy", ""), trade.get("reason", ""),
                trade.get("duration_seconds", 0),
            ))
        logger.info(f"[DB] Trade saved: {trade['symbol']} {trade['side']} pnl=${trade['net_pnl']:.2f}")

    def get_trades(self, limit: int = 100) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        cols = ["id","timestamp","symbol","side","entry_price","exit_price",
                "size","gross_pnl","commission","net_pnl","strategy","reason","duration_seconds"]
        return [dict(zip(cols, r)) for r in rows]

    def get_stats(self) -> Dict:
        with self._conn() as conn:
            c = conn.cursor()
            total = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            wins = c.execute("SELECT COUNT(*) FROM trades WHERE net_pnl > 0").fetchone()[0]
            losses = c.execute("SELECT COUNT(*) FROM trades WHERE net_pnl <= 0").fetchone()[0]
            pnl = c.execute("SELECT COALESCE(SUM(net_pnl),0) FROM trades").fetchone()[0]
            comm = c.execute("SELECT COALESCE(SUM(commission),0) FROM trades").fetchone()[0]
        return {
            "total_trades": total, "wins": wins, "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0.0,
            "total_pnl": pnl, "total_commission": comm,
        }

    # ─── POSITIONS (persistence across restarts) ────────
    def save_position(self, symbol: str, pos: Dict):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO positions
                    (symbol, side, entry_price, size, stop_loss, take_profit,
                     entry_time, strategy, trailing_active, trailing_peak)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                symbol, pos["side"], pos["entry_price"], pos["size"],
                pos["stop_loss"], pos["take_profit"],
                pos.get("entry_time", datetime.now().isoformat()),
                pos.get("strategy", ""),
                1 if pos.get("trailing_active", False) else 0,
                pos.get("trailing_peak", 0.0),
            ))

    def delete_position(self, symbol: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    def load_positions(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM positions").fetchall()
        result = {}
        for r in rows:
            result[r[0]] = {
                "side": r[1], "entry_price": r[2], "size": r[3],
                "stop_loss": r[4], "take_profit": r[5],
                "entry_time": r[6], "strategy": r[7],
                "trailing_active": bool(r[8]), "trailing_peak": r[9],
            }
        return result

    # ─── EVENTS ─────────────────────────────────────────
    def log_event(self, event_type: str, message: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (timestamp, event_type, message) VALUES (?,?,?)",
                (datetime.now().isoformat(), event_type, message),
            )
