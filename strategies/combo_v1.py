"""
combo_v1.py — War Machine Combo v1: Kazanan 5 Strateji Birleşik
=================================================================
Backtest'te kanıtlanmış 5 mean-reversion stratejisi:

  1. VWAP Reversion    — RANGING'de VWAP altı + RSI<35 → LONG (PF=7.52, WR=73.9%)
  2. EMA Pullback      — Uptrend'de EMA21'e pullback → LONG (PF=1.34, WR=50%, 98 trade)
  3. Bollinger Bounce   — Alt band'a dokunma + RSI<40 → LONG (PF=2.51, WR=67.7%)
  4. Mean Reversion    — 3-bar %3+ düşüş + RSI<35 + hacim → LONG (PF=∞, 12/12 kazanç)
  5. Keltner Bounce    — EMA20-2×ATR altı + RSI<45 → LONG (OOS: PF=1.90-2.30, WR=62-66%)

Her biri bağımsız sinyal üretir. En yüksek confidence'lı sinyal alınır.
Hepsi LONG-only.
"""

import pandas as pd
import logging
from strategies.base import BaseStrategy
from strategies.indicators import calc_ema, calc_rsi, calc_atr, calc_macd, calc_bollinger, calc_vwap
from engine.signal import Signal
import config

logger = logging.getLogger(__name__)


class ComboV1Strategy(BaseStrategy):
    name = "COMBO_V1"

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        none = Signal(symbol=symbol, action="NONE", confidence=0.0,
                      reason="", strategy=self.name)

        if len(df) < 30:
            none.reason = "yetersiz veri"
            return none

        close = df["close"]
        volume = df["volume"]
        price = close.iloc[-1]

        # --- Ortak indikatörler ---
        rsi = calc_rsi(close, 14)
        atr = calc_atr(df, 14)
        ema9 = calc_ema(close, 9)
        ema21 = calc_ema(close, 21)

        rsi_now = rsi.iloc[-1]
        atr_now = atr.iloc[-1]
        e9 = ema9.iloc[-1]
        e21 = ema21.iloc[-1]

        if pd.isna(rsi_now) or pd.isna(atr_now) or atr_now <= 0:
            none.reason = "NaN indikatör"
            return none

        # Her stratejiyi dene — en iyi sinyali seç
        best_signal = none
        best_conf = 0.0

        # ─── 1. VWAP REVERSION ──────────────────────────
        if regime == "RANGING":
            vwap = calc_vwap(df).iloc[-1]
            if not pd.isna(vwap) and vwap > 0:
                dev = (price - vwap) / vwap
                if dev < -0.01 and rsi_now < 40:
                    severity = abs(dev) / 0.01
                    conf = min(0.85, 0.60 + severity * 0.08)
                    if conf > best_conf:
                        best_conf = conf
                        best_signal = Signal(
                            symbol=symbol, action="LONG", confidence=conf,
                            reason=f"VWAP_REV: dev={dev*100:.1f}% RSI={rsi_now:.0f}",
                            strategy=self.name, price=price, atr=atr_now,
                        )

        # ─── 2. EMA PULLBACK ────────────────────────────
        ema50 = calc_ema(close, 50).iloc[-1]
        if not pd.isna(ema50) and e9 > e21 > ema50:
            dist = (price - e21) / e21
            if -0.005 <= dist <= 0.01:
                candle_green = close.iloc[-1] > df["open"].iloc[-1]
                if candle_green and 40 <= rsi_now <= 60:
                    conf = 0.65
                    # MACD bonus
                    macd, sig, _ = calc_macd(close)
                    if not pd.isna(macd.iloc[-1]) and macd.iloc[-1] > sig.iloc[-1]:
                        conf += 0.10
                    if conf > best_conf:
                        best_conf = conf
                        best_signal = Signal(
                            symbol=symbol, action="LONG", confidence=conf,
                            reason=f"EMA_PB: dist={dist*100:.2f}% RSI={rsi_now:.0f}",
                            strategy=self.name, price=price, atr=atr_now,
                        )

        # ─── 3. BOLLINGER BOUNCE ─────────────────────────
        upper, middle, lower, bw = calc_bollinger(close, 20, 2.0)
        if not pd.isna(lower.iloc[-1]) and price <= lower.iloc[-1] and rsi_now < 40:
            depth = (lower.iloc[-1] - price) / lower.iloc[-1]
            conf = min(0.80, 0.62 + depth * 5)
            if conf > best_conf:
                best_conf = conf
                best_signal = Signal(
                    symbol=symbol, action="LONG", confidence=conf,
                    reason=f"BB_BOUNCE: price≤lower RSI={rsi_now:.0f}",
                    strategy=self.name, price=price, atr=atr_now,
                )

        # ─── 4. MEAN REVERSION (DIP BUY) ────────────────
        if len(close) >= 4:
            price_3ago = close.iloc[-4]
            drop_pct = (price - price_3ago) / price_3ago
            if drop_pct <= -0.03 and rsi_now < 35:
                vol_now = volume.iloc[-1]
                vol_avg = volume.rolling(20).mean().iloc[-1]
                if not pd.isna(vol_avg) and vol_avg > 0 and vol_now >= vol_avg:
                    conf = min(0.85, 0.70 + abs(drop_pct) * 2)
                    if conf > best_conf:
                        best_conf = conf
                        best_signal = Signal(
                            symbol=symbol, action="LONG", confidence=conf,
                            reason=f"MEAN_REV: drop={drop_pct*100:.1f}% RSI={rsi_now:.0f}",
                            strategy=self.name, price=price, atr=atr_now,
                        )

        # ─── 5. KELTNER CHANNEL BOUNCE ──────────────────
        ema20 = calc_ema(close, 20).iloc[-1]
        if not pd.isna(ema20):
            keltner_lower = ema20 - 2 * atr_now
            if price <= keltner_lower and rsi_now < 45:
                depth = (keltner_lower - price) / keltner_lower
                conf = min(0.80, 0.65 + depth * 5)
                if conf > best_conf:
                    best_conf = conf
                    best_signal = Signal(
                        symbol=symbol, action="LONG", confidence=conf,
                        reason=f"KELTNER: price≤lower RSI={rsi_now:.0f}",
                        strategy=self.name, price=price, atr=atr_now,
                    )

        # Diagnostic log — live debugging
        if best_signal.action == "NONE":
            ema50 = calc_ema(close, 50).iloc[-1]
            dist_e21 = (price - e21) / e21 * 100
            logger.info(
                f"[STRAT] {symbol} NO-SIGNAL | RSI={rsi_now:.1f} "
                f"dist_EMA21={dist_e21:+.2f}% regime={regime} "
                f"trend={'Y' if e9 > e21 > ema50 else 'N'}"
            )

        return best_signal
