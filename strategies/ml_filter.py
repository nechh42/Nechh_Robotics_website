"""
ml_filter.py - ML Sinyal Kalite Filtresi (LIVE)
==================================================
Eğitilmiş GradientBoosting modeli kullanarak düşük
kaliteli sinyalleri trade açılmadan ÖNCE filtreler.

Kullanım:
  - orchestrator.py'de pre-trade risk check'ten SONRA çalışır
  - Model yoksa veya yüklenemezse → filtre devre dışı (trade açılır)
  - ML skoru threshold'un altındaysa → sinyal engellenir

Model eğitimi: python -m backtest.ml_trainer
"""

import os
import pickle
import logging
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Tuple

import config
from strategies.regime import detect_regime, _calc_wilder_adx, _calc_volatility_ratio
from strategies.indicators import (
    calc_rsi, calc_atr, calc_ema, calc_bollinger, calc_vwap, calc_macd
)

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml_model.pkl")


class MLFilter:
    """ML-based sinyal kalite filtresi"""

    def __init__(self):
        self.model = None
        self.feature_cols = []
        self.threshold = 0.50
        self.enabled = False
        self._load_model()

    def _load_model(self):
        """Model dosyasını yükle"""
        if not getattr(config, 'ML_FILTER_ENABLED', False):
            logger.info("[ML] ML_FILTER_ENABLED=False — filtre devre dışı")
            return

        if not os.path.exists(MODEL_PATH):
            logger.info("[ML] Model dosyası bulunamadı — filtre devre dışı")
            return

        try:
            with open(MODEL_PATH, "rb") as f:
                data = pickle.load(f)

            self.model = data["model"]
            self.feature_cols = data["feature_cols"]
            self.threshold = data.get("threshold", 0.50)
            self.enabled = True

            logger.info(
                f"[ML] Model yüklendi: v{data.get('version', '?')}, "
                f"{len(self.feature_cols)} feature, threshold={self.threshold:.2f}, "
                f"eğitim={data.get('trained_at', '?')}"
            )
        except Exception as e:
            logger.error(f"[ML] Model yükleme hatası: {e}")
            self.enabled = False

    def predict(self, df, symbol: str, regime: str, price: float) -> Tuple[bool, float, str]:
        """
        Sinyalin kalitesini değerlendir.
        
        Returns:
            (approved, score, reason)
            approved: True → trade açılabilir, False → engelle
            score: 0.0-1.0 ML confidence
            reason: açıklama
        """
        if not self.enabled or self.model is None:
            return True, 0.5, "ML filtre devre dışı"

        try:
            features = self._extract_features(df, symbol, regime, price)
            if not features:
                return True, 0.5, "Feature extraction başarısız"

            # Feature vektörü oluştur
            X = np.array([[features.get(col, 0.0) for col in self.feature_cols]])
            
            # Tahmin
            proba = self.model.predict_proba(X)[0]
            win_prob = proba[1] if len(proba) > 1 else proba[0]

            approved = win_prob >= self.threshold
            reason = f"ML score={win_prob:.3f} (threshold={self.threshold:.2f})"

            if not approved:
                logger.info(f"[ML] {symbol}: ENGEL — {reason}")
            else:
                logger.info(f"[ML] {symbol}: ONAY — {reason}")

            return approved, win_prob, reason

        except Exception as e:
            logger.error(f"[ML] Prediction error: {e}")
            return True, 0.5, f"ML hata: {e}"

    def _extract_features(self, df, symbol: str, regime: str, price: float) -> Dict:
        """Feature extraction (ml_trainer.py ile aynı mantık)"""
        try:
            closes = df["close"]
            highs = df["high"]
            lows = df["low"]
            volumes = df["volume"]
            n = len(df)
            f = {}

            # RSI
            rsi = calc_rsi(closes)
            rsi_val = rsi.iloc[-1] if not rsi.empty else 50.0
            f["rsi"] = rsi_val
            f["rsi_prev"] = rsi.iloc[-2] if len(rsi) >= 2 else rsi_val
            f["rsi_delta"] = f["rsi"] - f["rsi_prev"]

            # ADX
            adx, plus_di, minus_di = _calc_wilder_adx(df)
            f["adx"] = adx
            f["plus_di"] = plus_di
            f["minus_di"] = minus_di
            f["di_spread"] = plus_di - minus_di

            # Volatility
            atr_s = calc_atr(df)
            atr = atr_s.iloc[-1] if not atr_s.empty else 0
            f["atr_pct"] = (atr / price * 100) if price > 0 else 0
            f["vol_ratio"] = _calc_volatility_ratio(df)

            # Bollinger
            upper, middle, lower, bw = calc_bollinger(closes)
            bb_range = upper.iloc[-1] - lower.iloc[-1]
            f["bb_position"] = (price - lower.iloc[-1]) / bb_range if bb_range > 0 else 0.5
            f["bb_width"] = bw.iloc[-1] if not bw.empty else 0

            # Volume
            vol_avg = volumes.tail(20).mean()
            vol_cur = volumes.iloc[-1]
            f["volume_ratio"] = vol_cur / vol_avg if vol_avg > 0 else 1.0
            f["volume_trend"] = volumes.tail(5).mean() / volumes.tail(20).mean() if volumes.tail(20).mean() > 0 else 1.0

            # Returns
            for lb in [1, 3, 5, 10]:
                if n > lb:
                    f[f"ret_{lb}"] = (closes.iloc[-1] - closes.iloc[-1 - lb]) / closes.iloc[-1 - lb] * 100
                else:
                    f[f"ret_{lb}"] = 0.0

            # Candle patterns
            if n >= 5:
                last5 = df.tail(5)
                f["green_ratio_5"] = (last5["close"] > last5["open"]).sum() / 5
            else:
                f["green_ratio_5"] = 0.5

            if n >= 3:
                last3 = df.tail(3)
                f["green_ratio_3"] = (last3["close"] > last3["open"]).sum() / 3
            else:
                f["green_ratio_3"] = 0.5

            candle_range = highs.iloc[-1] - lows.iloc[-1]
            candle_body = abs(closes.iloc[-1] - df["open"].iloc[-1])
            f["body_ratio"] = candle_body / candle_range if candle_range > 0 else 0

            if closes.iloc[-1] >= df["open"].iloc[-1]:
                upper_shadow = highs.iloc[-1] - closes.iloc[-1]
                lower_shadow = df["open"].iloc[-1] - lows.iloc[-1]
            else:
                upper_shadow = highs.iloc[-1] - df["open"].iloc[-1]
                lower_shadow = closes.iloc[-1] - lows.iloc[-1]
            f["upper_shadow_pct"] = upper_shadow / candle_range if candle_range > 0 else 0
            f["lower_shadow_pct"] = lower_shadow / candle_range if candle_range > 0 else 0

            # EMA positions
            ema9 = calc_ema(closes, 9)
            ema21 = calc_ema(closes, 21)
            ema50 = calc_ema(closes, 50)
            f["price_vs_ema9"] = (price - ema9.iloc[-1]) / price * 100 if ema9.iloc[-1] > 0 else 0
            f["price_vs_ema21"] = (price - ema21.iloc[-1]) / price * 100 if ema21.iloc[-1] > 0 else 0
            f["price_vs_ema50"] = (price - ema50.iloc[-1]) / price * 100 if ema50.iloc[-1] > 0 else 0
            f["ema9_vs_ema21"] = (ema9.iloc[-1] - ema21.iloc[-1]) / ema21.iloc[-1] * 100 if ema21.iloc[-1] > 0 else 0

            # VWAP
            vwap = calc_vwap(df)
            f["vwap_distance"] = (price - vwap.iloc[-1]) / price * 100 if vwap.iloc[-1] > 0 else 0

            # MACD
            macd_line, signal_line, histogram = calc_macd(closes)
            f["macd_hist"] = histogram.iloc[-1] if not histogram.empty else 0
            f["macd_hist_prev"] = histogram.iloc[-2] if len(histogram) >= 2 else 0
            f["macd_hist_delta"] = f["macd_hist"] - f["macd_hist_prev"]
            f["macd_hist_norm"] = f["macd_hist"] / price * 10000 if price > 0 else 0

            # Regime
            regime_map = {"RANGING": 0, "TREND_UP": 1, "TREND_DOWN": 2, "VOLATILE": 3}
            f["regime_num"] = regime_map.get(regime, 0)

            # Coin index
            coin_list = [s for s in config.SYMBOLS if s not in getattr(config, 'COIN_BLACKLIST', [])]
            f["coin_idx"] = coin_list.index(symbol) if symbol in coin_list else -1

            # Time
            f["hour"] = datetime.now().hour
            f["day_of_week"] = datetime.now().weekday()

            return f

        except Exception as e:
            logger.error(f"[ML] Feature extraction error: {e}")
            return {}
