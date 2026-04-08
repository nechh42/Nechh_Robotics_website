"""
signal_logger.py - HER Sinyal Değerlendirmesini Kaydet
=========================================================
Trade açılsın açılmasın, her 4h candle close'da üretilen TÜM sinyalleri
ve kararları kaydeder. ML eğitimi + analiz + swarm agent'lar için TEMEL veri.

Kaydedilenler:
  - Her strateji'nin bireysel sinyalleri (confidence, action, reason)
  - Voting sonucu (combined signal)
  - Red nedeni (pre-trade block, volume filter, blacklist, vb.)
  - 34 feature (ML-ready)
  - Sonuç (trade açıldı mı, PnL)
"""

import sqlite3
import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

import config
from strategies.indicators import (
    calc_rsi, calc_atr, calc_ema, calc_bollinger, calc_vwap, calc_macd
)

logger = logging.getLogger(__name__)


class SignalLogger:
    """Her sinyal değerlendirmesini DB'ye yazar"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._init_table()

    def _conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _init_table(self):
        try:
            with self._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS signal_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        regime TEXT NOT NULL,
                        price REAL NOT NULL,

                        -- Bireysel strateji sinyalleri
                        rsi_action TEXT DEFAULT 'NONE',
                        rsi_confidence REAL DEFAULT 0,
                        momentum_action TEXT DEFAULT 'NONE',
                        momentum_confidence REAL DEFAULT 0,
                        vwap_action TEXT DEFAULT 'NONE',
                        vwap_confidence REAL DEFAULT 0,
                        edge_action TEXT DEFAULT 'NONE',
                        edge_confidence REAL DEFAULT 0,

                        -- Voting sonucu
                        combined_action TEXT DEFAULT 'NONE',
                        combined_confidence REAL DEFAULT 0,
                        weights_used TEXT DEFAULT '',

                        -- Karar
                        decision TEXT NOT NULL,
                        block_reason TEXT DEFAULT '',

                        -- Feature snapshot (JSON)
                        features TEXT DEFAULT '{}',

                        -- Sonuç (trade açıldıysa sonradan güncellenir)
                        trade_opened INTEGER DEFAULT 0,
                        net_pnl REAL DEFAULT NULL,
                        exit_reason TEXT DEFAULT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Init error: {e}")

    def log_evaluation(
        self,
        symbol: str,
        regime: str,
        price: float,
        signals: list,
        combined,
        weights: dict,
        decision: str,
        block_reason: str = "",
        df=None,
    ) -> int:
        """
        Her 4h candle close'da yapılan değerlendirmeyi kaydet.
        
        decision: TRADE_OPENED, NO_SIGNAL, BLOCKED_RISK, BLOCKED_VOLUME,
                  BLOCKED_BLACKLIST, BLOCKED_TREND_UP, BLOCKED_CORRELATION,
                  BLOCKED_MTF, MTF_PENDING
        """
        try:
            # Strateji sinyallerini ayır
            strat_data = {
                "RSI": ("NONE", 0.0),
                "MOMENTUM": ("NONE", 0.0),
                "VWAP": ("NONE", 0.0),
                "EDGE_DISCOVERY": ("NONE", 0.0),
            }
            for sig in signals:
                if sig.strategy in strat_data:
                    strat_data[sig.strategy] = (sig.action, sig.confidence)

            # Feature extraction
            features = self._extract_features(df, price) if df is not None else {}

            with self._conn() as conn:
                cur = conn.execute("""
                    INSERT INTO signal_log (
                        timestamp, symbol, regime, price,
                        rsi_action, rsi_confidence,
                        momentum_action, momentum_confidence,
                        vwap_action, vwap_confidence,
                        edge_action, edge_confidence,
                        combined_action, combined_confidence,
                        weights_used, decision, block_reason, features
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    datetime.now().isoformat(),
                    symbol, regime, price,
                    strat_data["RSI"][0], strat_data["RSI"][1],
                    strat_data["MOMENTUM"][0], strat_data["MOMENTUM"][1],
                    strat_data["VWAP"][0], strat_data["VWAP"][1],
                    strat_data["EDGE_DISCOVERY"][0], strat_data["EDGE_DISCOVERY"][1],
                    combined.action if combined else "NONE",
                    combined.confidence if combined else 0.0,
                    json.dumps(weights),
                    decision,
                    block_reason,
                    json.dumps(features),
                ))
                return cur.lastrowid
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Write error: {e}")
            return -1

    def log_block(
        self,
        symbol: str,
        regime: str,
        price: float,
        block_reason: str,
        df=None,
    ):
        """Strateji çalıştırılmadan engellenmiş durumları kaydet"""
        try:
            features = self._extract_features(df, price) if df is not None else {}
            with self._conn() as conn:
                conn.execute("""
                    INSERT INTO signal_log (
                        timestamp, symbol, regime, price,
                        combined_action, decision, block_reason, features
                    ) VALUES (?,?,?,?,?,?,?,?)
                """, (
                    datetime.now().isoformat(),
                    symbol, regime, price,
                    "NONE", f"BLOCKED_{block_reason}", block_reason,
                    json.dumps(features),
                ))
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Block write error: {e}")

    def update_outcome(self, signal_id: int, net_pnl: float, exit_reason: str):
        """Trade kapandığında sonucu güncelle"""
        if signal_id < 0:
            return
        try:
            with self._conn() as conn:
                conn.execute("""
                    UPDATE signal_log
                    SET net_pnl = ?, exit_reason = ?
                    WHERE id = ?
                """, (net_pnl, exit_reason, signal_id))
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Update error: {e}")

    def _extract_features(self, df, price: float) -> Dict:
        """ML-ready feature snapshot"""
        try:
            closes = df["close"]
            volumes = df["volume"]
            n = len(df)
            f = {}

            # RSI
            rsi = calc_rsi(closes)
            f["rsi"] = round(rsi.iloc[-1], 2) if not rsi.empty else 50.0

            # ATR
            atr_s = calc_atr(df)
            atr = atr_s.iloc[-1] if not atr_s.empty else 0
            f["atr_pct"] = round(atr / price * 100, 4) if price > 0 else 0

            # Bollinger
            upper, middle, lower, bw = calc_bollinger(closes)
            bb_range = upper.iloc[-1] - lower.iloc[-1]
            f["bb_position"] = round((price - lower.iloc[-1]) / bb_range, 3) if bb_range > 0 else 0.5
            f["bb_width"] = round(bw.iloc[-1], 4) if not bw.empty else 0

            # Volume
            vol_avg = volumes.tail(20).mean()
            vol_cur = volumes.iloc[-1]
            f["volume_ratio"] = round(vol_cur / vol_avg, 3) if vol_avg > 0 else 1.0

            # Returns
            for lb in [1, 3, 5, 10]:
                if n > lb:
                    f[f"ret_{lb}"] = round((closes.iloc[-1] - closes.iloc[-1 - lb]) / closes.iloc[-1 - lb] * 100, 3)

            # EMA positions
            ema9 = calc_ema(closes, 9)
            ema21 = calc_ema(closes, 21)
            f["price_vs_ema9"] = round((price - ema9.iloc[-1]) / price * 100, 3) if ema9.iloc[-1] > 0 else 0
            f["price_vs_ema21"] = round((price - ema21.iloc[-1]) / price * 100, 3) if ema21.iloc[-1] > 0 else 0

            # VWAP
            vwap = calc_vwap(df)
            f["vwap_distance"] = round((price - vwap.iloc[-1]) / price * 100, 3) if vwap.iloc[-1] > 0 else 0

            # MACD
            macd_line, signal_line, hist = calc_macd(closes)
            f["macd_hist_norm"] = round(hist.iloc[-1] / price * 10000, 3) if not hist.empty and price > 0 else 0

            # Candle patterns
            if n >= 5:
                last5 = df.tail(5)
                f["green_ratio_5"] = round((last5["close"] > last5["open"]).sum() / 5, 2)

            return f
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Feature extraction error: {e}")
            return {}

    # ─── ANALİZ METOTLARİ ──────────────────────────────

    def get_stats(self, hours: int = 24) -> Dict:
        """Son N saatteki sinyal istatistikleri"""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT decision, COUNT(*) as cnt
                    FROM signal_log
                    WHERE timestamp > datetime('now', ? || ' hours')
                    GROUP BY decision
                """, (f"-{hours}",)).fetchall()

            stats = {"total": 0, "decisions": {}}
            for decision, cnt in rows:
                stats["decisions"][decision] = cnt
                stats["total"] += cnt
            return stats
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Stats error: {e}")
            return {"total": 0, "decisions": {}}

    def get_strategy_accuracy(self, hours: int = 168) -> Dict:
        """Her stratejinin sinyal doğruluğu (son N saat)"""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT
                        rsi_action, rsi_confidence,
                        momentum_action, momentum_confidence,
                        vwap_action, vwap_confidence,
                        edge_action, edge_confidence,
                        net_pnl
                    FROM signal_log
                    WHERE trade_opened = 1 AND net_pnl IS NOT NULL
                    AND timestamp > datetime('now', ? || ' hours')
                """, (f"-{hours}",)).fetchall()

            accuracy = {}
            for strat_name, action_idx, conf_idx in [
                ("RSI", 0, 1), ("MOMENTUM", 2, 3),
                ("VWAP", 4, 5), ("EDGE_DISCOVERY", 6, 7),
            ]:
                trades = [(r[action_idx], r[conf_idx], r[8]) for r in rows if r[action_idx] != "NONE"]
                if trades:
                    wins = sum(1 for _, _, pnl in trades if pnl > 0)
                    accuracy[strat_name] = {
                        "signals": len(trades),
                        "wins": wins,
                        "win_rate": round(wins / len(trades) * 100, 1),
                        "avg_confidence": round(sum(c for _, c, _ in trades) / len(trades), 3),
                    }
            return accuracy
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Accuracy error: {e}")
            return {}

    def get_regime_performance(self, hours: int = 168) -> Dict:
        """Regime bazlı performans"""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT regime, COUNT(*) as total,
                           SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) as wins,
                           SUM(CASE WHEN net_pnl IS NOT NULL THEN 1 ELSE 0 END) as closed,
                           COALESCE(SUM(net_pnl), 0) as total_pnl
                    FROM signal_log
                    WHERE trade_opened = 1
                    AND timestamp > datetime('now', ? || ' hours')
                    GROUP BY regime
                """, (f"-{hours}",)).fetchall()

            result = {}
            for regime, total, wins, closed, pnl in rows:
                result[regime] = {
                    "signals": total,
                    "closed": closed,
                    "wins": wins or 0,
                    "win_rate": round((wins or 0) / closed * 100, 1) if closed > 0 else 0,
                    "total_pnl": round(pnl, 2),
                }
            return result
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Regime perf error: {e}")
            return {}

    def get_block_stats(self, hours: int = 24) -> Dict:
        """Engelleme nedeni istatistikleri"""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT block_reason, COUNT(*) as cnt
                    FROM signal_log
                    WHERE block_reason != ''
                    AND timestamp > datetime('now', ? || ' hours')
                    GROUP BY block_reason
                    ORDER BY cnt DESC
                """, (f"-{hours}",)).fetchall()
            return {reason: cnt for reason, cnt in rows}
        except Exception as e:
            logger.error(f"[SIGNAL_LOG] Block stats error: {e}")
            return {}
