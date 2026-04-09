"""
scalp_v0.py — War Machine v0: Tek Basit Strateji
=====================================================
3 koşul, SL/TP eşit, 4h max süre. Hiçbir karmaşıklık yok.

Giriş (hepsi True olmalı):
  1. EMA_9 > EMA_21 (trend yönü yukarı)
  2. RSI 35-65 arası (aşırı uçlarda değil)
  3. Hacim > 20-bar ortalaması (gerçek hareket)

Çıkış:
  • TP = 1.0 × ATR
  • SL = 1.0 × ATR
  • MAX = 1 candle (4h)
"""

import pandas as pd
from strategies.base import BaseStrategy
from strategies.indicators import calc_ema, calc_rsi, calc_atr, calc_macd
from engine.signal import Signal
import config


class ScalpV0Strategy(BaseStrategy):
    name = "SCALP_V0"

    def evaluate(self, df: pd.DataFrame, symbol: str, regime: str) -> Signal:
        none = Signal(symbol=symbol, action="NONE", confidence=0.0,
                      reason="", strategy=self.name)

        if len(df) < 30:
            none.reason = "yetersiz veri"
            return none

        close = df["close"]
        volume = df["volume"]
        price = close.iloc[-1]

        # --- İndikatörler ---
        ema9 = calc_ema(close, 9)
        ema21 = calc_ema(close, 21)
        rsi = calc_rsi(close, config.RSI_PERIOD)
        atr = calc_atr(df, 14)
        macd_line, signal_line, _ = calc_macd(close)

        ema9_now = ema9.iloc[-1]
        ema21_now = ema21.iloc[-1]
        rsi_now = rsi.iloc[-1]
        atr_now = atr.iloc[-1]
        vol_now = volume.iloc[-1]
        vol_avg = volume.rolling(20).mean().iloc[-1]

        # --- NaN kontrolü ---
        if pd.isna(ema9_now) or pd.isna(ema21_now) or pd.isna(rsi_now) or pd.isna(atr_now):
            none.reason = "NaN indikatör"
            return none

        if atr_now <= 0:
            none.reason = "ATR=0"
            return none

        # --- KOŞUL 1: Trend yönü ---
        if ema9_now <= ema21_now:
            none.reason = f"EMA9({ema9_now:.2f}) <= EMA21({ema21_now:.2f})"
            return none

        # --- KOŞUL 2: RSI aşırı uçlarda değil ---
        if rsi_now < 35 or rsi_now > 65:
            none.reason = f"RSI={rsi_now:.1f} aralık dışı (35-65)"
            return none

        # --- KOŞUL 3: Hacim ortalamanın üstünde ---
        if vol_avg > 0 and vol_now < vol_avg:
            none.reason = f"Hacim({vol_now:.0f}) < Ort({vol_avg:.0f})"
            return none

        # --- Tüm koşullar geçti → LONG sinyali ---
        conf = 0.60

        # Bonus: MACD momentum teyidi
        if not pd.isna(macd_line.iloc[-1]) and not pd.isna(signal_line.iloc[-1]):
            if macd_line.iloc[-1] > signal_line.iloc[-1]:
                conf += 0.10

        # Bonus: Güçlü hacim (1.5x)
        if vol_avg > 0 and vol_now > vol_avg * 1.5:
            conf += 0.10

        # Bonus: Düşük volatilite (daha güvenli)
        atr_pct = atr_now / price
        if atr_pct < 0.03:
            conf += 0.05

        conf = min(conf, 0.85)

        reason = (f"EMA9>{ema21_now:.1f} RSI={rsi_now:.1f} "
                  f"Vol={vol_now/vol_avg:.1f}x ATR={atr_pct*100:.1f}%")

        return Signal(
            symbol=symbol,
            action="LONG",
            confidence=conf,
            reason=reason,
            strategy=self.name,
            price=price,
            atr=atr_now,
        )
