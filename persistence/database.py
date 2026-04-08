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
                    trailing_peak REAL DEFAULT 0,
                    entry_atr REAL DEFAULT 0,
                    breakeven_applied INTEGER DEFAULT 0,
                    partial_closed INTEGER DEFAULT 0,
                    entry_regime TEXT DEFAULT '',
                    take_profit_1 REAL DEFAULT 0
                )
            """)
            # Migrate: add missing columns to existing positions table
            for col, typ, default in [
                ("entry_atr", "REAL", "0"),
                ("breakeven_applied", "INTEGER", "0"),
                ("partial_closed", "INTEGER", "0"),
                ("entry_regime", "TEXT", "''"),
                ("take_profit_1", "REAL", "0"),
            ]:
                try:
                    c.execute(f"ALTER TABLE positions ADD COLUMN {col} {typ} DEFAULT {default}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
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
                     entry_time, strategy, trailing_active, trailing_peak,
                     entry_atr, breakeven_applied, partial_closed,
                     entry_regime, take_profit_1)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                symbol, pos["side"], pos["entry_price"], pos["size"],
                pos["stop_loss"], pos["take_profit"],
                pos.get("entry_time", datetime.now().isoformat()),
                pos.get("strategy", ""),
                1 if pos.get("trailing_active", False) else 0,
                pos.get("trailing_peak", 0.0),
                pos.get("entry_atr", 0.0),
                1 if pos.get("breakeven_applied", False) else 0,
                1 if pos.get("partial_closed", False) else 0,
                pos.get("entry_regime", ""),
                pos.get("take_profit_1", 0.0),
            ))

    def delete_position(self, symbol: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    def load_positions(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM positions")
            cols = [d[0] for d in c.description]
            rows = c.fetchall()
        result = {}
        for r in rows:
            row = dict(zip(cols, r))
            result[row["symbol"]] = {
                "side": row["side"],
                "entry_price": row["entry_price"],
                "size": row["size"],
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "entry_time": row["entry_time"],
                "strategy": row.get("strategy", ""),
                "trailing_active": bool(row.get("trailing_active", 0)),
                "trailing_peak": row.get("trailing_peak", 0.0),
                "entry_atr": row.get("entry_atr", 0.0),
                "breakeven_applied": bool(row.get("breakeven_applied", 0)),
                "partial_closed": bool(row.get("partial_closed", 0)),
                "entry_regime": row.get("entry_regime", ""),
                "take_profit_1": row.get("take_profit_1", 0.0),
            }
        return result

    # ─── EVENTS ─────────────────────────────────────────
    def log_event(self, event_type: str, message: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (timestamp, event_type, message) VALUES (?,?,?)",
                (datetime.now().isoformat(), event_type, message),
            )
