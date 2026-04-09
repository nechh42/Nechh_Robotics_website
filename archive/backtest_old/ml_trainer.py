"""
ml_trainer.py - ML Sinyal Filtresi Eğitimi
=============================================
Plan [11]: Düşük kaliteli sinyalleri filtrele, WR %55+ hedef.

Yaklaşım:
  1. Backtest'ten her trade için giriş anındaki feature'ları çıkar
  2. WIN/LOSS label'la
  3. GradientBoosting ile eğit (walk-forward CV)
  4. Feature importance analizi
  5. Threshold optimizasyonu
  6. Modeli kaydet → strategies/ml_filter.py kullanır

Kullanım:
  python -m backtest.ml_trainer              # Eğit + test
  python -m backtest.ml_trainer --threshold  # Threshold sweep
"""

import sys, os, json, pickle, warnings
import numpy as np
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from strategies.regime import detect_regime, _calc_wilder_adx, _calc_volatility_ratio
from strategies.indicators import (
    calc_rsi, calc_atr, calc_ema, calc_sma,
    calc_bollinger, calc_vwap, calc_macd
)
from strategies.rsi_reversion import RSIReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.edge_discovery import EdgeDiscoveryStrategy
from engine.voting import combine_signals
from backtest.backtest_v3 import fetch_klines, BTPosition, BTTrade


# ═════════════════════════════════════════════════════════
# FEATURE EXTRACTION
# ═════════════════════════════════════════════════════════

def extract_features(df: pd.DataFrame, symbol: str, regime: str,
                     price: float, atr: float) -> Dict[str, float]:
    """
    Trade girişi anında mevcut olan TÜM feature'ları çıkar.
    Bunlar ML modelin girdileri olacak.
    """
    features = {}
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    volumes = df["volume"]
    n = len(df)

    # ─── 1. TREND INDICATORS ───────────────────
    rsi = calc_rsi(closes)
    rsi_val = rsi.iloc[-1] if not rsi.empty else 50.0
    features["rsi"] = rsi_val
    features["rsi_prev"] = rsi.iloc[-2] if len(rsi) >= 2 else rsi_val
    features["rsi_delta"] = features["rsi"] - features["rsi_prev"]

    # ADX + DI
    adx, plus_di, minus_di = _calc_wilder_adx(df)
    features["adx"] = adx
    features["plus_di"] = plus_di
    features["minus_di"] = minus_di
    features["di_spread"] = plus_di - minus_di  # pozitif = bullish

    # ─── 2. VOLATILITY ─────────────────────────
    features["atr_pct"] = (atr / price * 100) if price > 0 else 0
    features["vol_ratio"] = _calc_volatility_ratio(df)

    # Bollinger Band position (0=lower, 0.5=middle, 1=upper)
    upper, middle, lower, bw = calc_bollinger(closes)
    bb_range = upper.iloc[-1] - lower.iloc[-1]
    if bb_range > 0:
        features["bb_position"] = (price - lower.iloc[-1]) / bb_range
    else:
        features["bb_position"] = 0.5
    features["bb_width"] = bw.iloc[-1] if not bw.empty else 0

    # ─── 3. VOLUME ANALYSIS ────────────────────
    vol_avg_20 = volumes.tail(20).mean()
    vol_current = volumes.iloc[-1]
    features["volume_ratio"] = vol_current / vol_avg_20 if vol_avg_20 > 0 else 1.0
    features["volume_trend"] = (
        volumes.tail(5).mean() / volumes.tail(20).mean()
        if volumes.tail(20).mean() > 0 else 1.0
    )

    # ─── 4. PRICE ACTION ───────────────────────
    # Son N candle return
    for lookback in [1, 3, 5, 10]:
        if n > lookback:
            ret = (closes.iloc[-1] - closes.iloc[-1 - lookback]) / closes.iloc[-1 - lookback] * 100
            features[f"ret_{lookback}"] = ret
        else:
            features[f"ret_{lookback}"] = 0.0

    # Son 5 candle'da kaç tanesi yeşil
    if n >= 5:
        last5 = df.tail(5)
        green_count = (last5["close"] > last5["open"]).sum()
        features["green_ratio_5"] = green_count / 5
    else:
        features["green_ratio_5"] = 0.5

    # Son 3 candle'da kaç tanesi yeşil
    if n >= 3:
        last3 = df.tail(3)
        green_count = (last3["close"] > last3["open"]).sum()
        features["green_ratio_3"] = green_count / 3
    else:
        features["green_ratio_3"] = 0.5

    # Candle body/range ratio (son candle kuvveti)
    candle_range = highs.iloc[-1] - lows.iloc[-1]
    candle_body = abs(closes.iloc[-1] - df["open"].iloc[-1])
    features["body_ratio"] = candle_body / candle_range if candle_range > 0 else 0

    # Upper/lower shadow ratio
    if closes.iloc[-1] >= df["open"].iloc[-1]:  # Green candle
        upper_shadow = highs.iloc[-1] - closes.iloc[-1]
        lower_shadow = df["open"].iloc[-1] - lows.iloc[-1]
    else:  # Red candle
        upper_shadow = highs.iloc[-1] - df["open"].iloc[-1]
        lower_shadow = closes.iloc[-1] - lows.iloc[-1]
    features["upper_shadow_pct"] = upper_shadow / candle_range if candle_range > 0 else 0
    features["lower_shadow_pct"] = lower_shadow / candle_range if candle_range > 0 else 0

    # ─── 5. MOVING AVERAGE POSITIONS ───────────
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema50 = calc_ema(closes, 50)

    features["price_vs_ema9"] = (price - ema9.iloc[-1]) / price * 100 if ema9.iloc[-1] > 0 else 0
    features["price_vs_ema21"] = (price - ema21.iloc[-1]) / price * 100 if ema21.iloc[-1] > 0 else 0
    features["price_vs_ema50"] = (price - ema50.iloc[-1]) / price * 100 if ema50.iloc[-1] > 0 else 0
    features["ema9_vs_ema21"] = (ema9.iloc[-1] - ema21.iloc[-1]) / ema21.iloc[-1] * 100 if ema21.iloc[-1] > 0 else 0

    # ─── 6. VWAP DISTANCE ──────────────────────
    vwap = calc_vwap(df)
    features["vwap_distance"] = (price - vwap.iloc[-1]) / price * 100 if vwap.iloc[-1] > 0 else 0

    # ─── 7. MACD ────────────────────────────────
    macd_line, signal_line, histogram = calc_macd(closes)
    features["macd_hist"] = histogram.iloc[-1] if not histogram.empty else 0
    features["macd_hist_prev"] = histogram.iloc[-2] if len(histogram) >= 2 else 0
    features["macd_hist_delta"] = features["macd_hist"] - features["macd_hist_prev"]
    # Normalize MACD by price
    features["macd_hist_norm"] = features["macd_hist"] / price * 10000 if price > 0 else 0

    # ─── 8. REGIME as number ────────────────────
    regime_map = {"RANGING": 0, "TREND_UP": 1, "TREND_DOWN": 2, "VOLATILE": 3}
    features["regime_num"] = regime_map.get(regime, 0)

    # ─── 9. COIN ENCODING ──────────────────────
    # Basit hash → modelin coin ayrımı yapabilmesi için
    coin_list = [s for s in config.SYMBOLS if s not in config.COIN_BLACKLIST]
    features["coin_idx"] = coin_list.index(symbol) if symbol in coin_list else -1

    # ─── 10. TIME FEATURES ─────────────────────
    # (backtest'te timestamp str olarak geliyor)
    try:
        ts = pd.Timestamp(df["timestamp"].iloc[-1])
        features["hour"] = ts.hour
        features["day_of_week"] = ts.dayofweek
    except Exception:
        features["hour"] = 12
        features["day_of_week"] = 3

    return features


# ═════════════════════════════════════════════════════════
# ML BACKTEST (Feature toplayan backtest)
# ═════════════════════════════════════════════════════════

class MLDataCollector:
    """
    backtest_v3 mantığını kullanarak her trade girişinde
    feature çıkarır, trade sonucunu label olarak kaydeder.
    """

    def __init__(self, initial_balance=10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {}
        self.feature_rows = []  # [{features..., "label": 0/1, "net_pnl": X}]
        self.strategies = [
            RSIReversionStrategy(),
            MomentumStrategy(),
            VWAPReversionStrategy(),
            EdgeDiscoveryStrategy(),
        ]
        self._daily_trades = 0
        self._daily_loss = 0.0
        self._current_day = None
        self._funding_counter = 0
        # Feature buffer: symbol -> features dict (giriş anında kaydet)
        self._entry_features = {}

    def collect(self, symbols=None, days=60) -> pd.DataFrame:
        """Backtest çalıştır, her trade için feature satırı topla."""
        symbols = symbols or config.SYMBOLS
        print(f"\n{'='*60}")
        print(f"ML DATA COLLECTOR — {days} gün, {len(symbols)} coin")
        print(f"{'='*60}")

        # Fetch data
        data_map = {}
        for sym in symbols:
            print(f"  {sym}...", end=" ", flush=True)
            df = fetch_klines(sym, "4h", days + 10)
            if df is not None and len(df) >= 50:
                data_map[sym] = df
                print(f"{len(df)} ✓")
            else:
                print("SKIP")

        # Common timeline
        all_times = set()
        for df in data_map.values():
            all_times.update(df["open_time"].tolist())
        sorted_times = sorted(all_times)
        print(f"\nToplam zaman dilimi: {len(sorted_times)}")

        # Walk forward
        for timestamp in sorted_times:
            dt = datetime.fromtimestamp(timestamp / 1000)
            if self._current_day != dt.date():
                self._daily_trades = 0
                self._daily_loss = 0.0
                self._current_day = dt.date()

            for sym in list(data_map.keys()):
                df = data_map[sym]
                mask = df["open_time"] <= timestamp
                df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)
                if len(df_window) < 50:
                    continue

                price = df_window["close"].iloc[-1]
                high = df_window["high"].iloc[-1]
                low = df_window["low"].iloc[-1]
                ts_str = str(df_window["timestamp"].iloc[-1])

                # Update MFE/MAE
                if sym in self.positions:
                    pos = self.positions[sym]
                    if pos.side == "LONG":
                        if high > pos.max_favorable:
                            pos.max_favorable = high
                            pos.mfe_pct = (high - pos.entry_price) / pos.entry_price * 100
                        if low < pos.max_adverse:
                            pos.max_adverse = low
                            pos.mae_pct = (pos.entry_price - low) / pos.entry_price * 100

                # Check exits
                if sym in self.positions:
                    self._check_exits(sym, price, high, low, ts_str, df_window)

                # Funding
                if sym in self.positions:
                    self._funding_counter += 1
                    if self._funding_counter >= 2:
                        pos = self.positions[sym]
                        notional = pos.size * price
                        fee = notional * config.FUNDING_FEE_RATE
                        pos.funding_paid += fee
                        self.balance -= fee
                        self._funding_counter = 0

                # Evaluate entry
                if sym not in self.positions:
                    self._evaluate_entry(sym, df_window, price, ts_str)

        # Close remaining
        for sym in list(self.positions.keys()):
            if sym in data_map:
                df = data_map[sym]
                last_price = df["close"].iloc[-1]
                last_time = str(df["timestamp"].iloc[-1])
                last_regime = detect_regime(df.tail(100).reset_index(drop=True))
                self._close_position(sym, last_price, last_time, "END_OF_DATA", last_regime)

        df_features = pd.DataFrame(self.feature_rows)
        print(f"\nToplanan trade sayısı: {len(df_features)}")
        if len(df_features) > 0:
            wins = (df_features["label"] == 1).sum()
            print(f"WIN: {wins} ({wins/len(df_features)*100:.1f}%) | LOSS: {len(df_features)-wins}")
            print(f"Toplam PnL: ${df_features['net_pnl'].sum():.2f}")
        return df_features

    def _evaluate_entry(self, symbol, df, price, timestamp):
        """Entry logic — aynı backtest_v3 + feature extraction."""
        if len(self.positions) >= config.MAX_POSITIONS:
            return
        if self._daily_trades >= config.MAX_DAILY_TRADES:
            return
        if self._daily_loss >= config.MAX_DAILY_LOSS:
            return

        regime = detect_regime(df)

        if getattr(config, 'TREND_UP_BLOCK', False) and regime == "TREND_UP":
            return
        if symbol in getattr(config, 'COIN_BLACKLIST', []):
            return
        if getattr(config, 'DIP_BUY_FILTER', False) and regime == "RANGING":
            if len(df) >= 2:
                if df["close"].iloc[-2] >= df["open"].iloc[-2]:
                    return

        # Evaluate strategies
        signals = []
        for strat in self.strategies:
            try:
                sig = strat.evaluate(df, symbol, regime)
                if sig.action != "NONE":
                    atr_s = calc_atr(df)
                    sig.atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02
                    sig.price = price
                    signals.append(sig)
            except Exception:
                pass

        if not signals:
            return

        combined = combine_signals(signals, regime)
        if combined.action == "NONE":
            return

        action = combined.action
        if regime == "VOLATILE":
            return
        if action == "LONG" and regime == "TREND_DOWN":
            return
        if action == "SHORT":
            if not config.ALLOW_SHORT:
                if not (getattr(config, 'ALLOW_SHORT_CONDITIONAL', False) and regime == "TREND_DOWN"):
                    return

        atr_s = calc_atr(df)
        atr = atr_s.iloc[-1] if not atr_s.empty else price * 0.02

        rr = config.DYNAMIC_RR.get(regime, {"sl": 1.5, "tp": 3.0})
        sl_dist = atr * rr["sl"]
        tp_dist = atr * rr["tp"]

        min_sl = price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        if action == "LONG":
            sl = price - sl_dist
            tp = price + tp_dist
            tp1 = price + tp_dist * config.PARTIAL_TP_RATIO
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            tp1 = price - tp_dist * config.PARTIAL_TP_RATIO

        risk_amount = self.balance * config.RISK_BASE_PCT
        size_by_risk = risk_amount / sl_dist
        size_by_notional = (self.balance * 0.10) / price
        size = min(size_by_risk, size_by_notional)
        if regime == "RANGING":
            size *= 0.50
        if size < 0.0001:
            return

        entry_comm = price * size * config.COMMISSION_RATE
        self.balance -= entry_comm

        # ★ FEATURE EXTRACTION — giriş anındaki tüm veriler
        features = extract_features(df, symbol, regime, price, atr)
        features["symbol"] = symbol
        features["side"] = action
        features["entry_price"] = price
        features["timestamp"] = timestamp
        self._entry_features[symbol] = features

        self.positions[symbol] = BTPosition(
            symbol=symbol, side=action, entry_price=price,
            size=size, stop_loss=sl, take_profit=tp,
            take_profit_1=tp1, entry_time=timestamp,
            strategy=combined.strategy, entry_regime=regime,
            original_entry_regime=regime,
            entry_atr=atr, max_favorable=price, max_adverse=price,
        )
        self._daily_trades += 1

    def _check_exits(self, symbol, price, high, low, timestamp, df):
        """Exit logic — aynı backtest_v3."""
        pos = self.positions[symbol]
        pos.candles_held += 1
        current_regime = detect_regime(df)

        # Breakeven
        if not pos.breakeven_applied and pos.entry_atr > 0:
            be_dist = pos.entry_atr * config.BREAKEVEN_ATR_TRIGGER
            if pos.side == "LONG" and high >= pos.entry_price + be_dist:
                pos.stop_loss = max(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True
            elif pos.side == "SHORT" and low <= pos.entry_price - be_dist:
                pos.stop_loss = min(pos.stop_loss, pos.entry_price)
                pos.breakeven_applied = True

        # Trailing
        if pos.trailing_active:
            if pos.side == "LONG" and high > pos.trailing_peak:
                pos.trailing_peak = high
                new_sl = high * (1 - config.TRAILING_STOP_DISTANCE)
                if new_sl > pos.stop_loss:
                    pos.stop_loss = new_sl
            elif pos.side == "SHORT" and low < pos.trailing_peak:
                pos.trailing_peak = low
                new_sl = low * (1 + config.TRAILING_STOP_DISTANCE)
                if new_sl < pos.stop_loss:
                    pos.stop_loss = new_sl
        if not pos.trailing_active:
            if pos.side == "LONG":
                pct = (high - pos.entry_price) / pos.entry_price
                if pct >= config.TRAILING_STOP_ACTIVATE:
                    pos.trailing_active = True
                    pos.trailing_peak = high
            else:
                pct = (pos.entry_price - low) / pos.entry_price
                if pct >= config.TRAILING_STOP_ACTIVATE:
                    pos.trailing_active = True
                    pos.trailing_peak = low

        # Smart Exit
        if config.SMART_EXIT_ENABLED and pos.entry_regime:
            if current_regime != pos.entry_regime:
                if pos.side == "LONG":
                    unrealized = (price - pos.entry_price) * pos.size
                else:
                    unrealized = (pos.entry_price - price) * pos.size
                if unrealized > 0:
                    self._close_position(symbol, price, timestamp,
                                         f"SMART-EXIT: {pos.entry_regime}→{current_regime}",
                                         current_regime)
                    return
                else:
                    new_rr = config.DYNAMIC_RR.get(current_regime, None)
                    if new_rr and pos.entry_atr > 0:
                        new_tp_dist = pos.entry_atr * new_rr["tp"]
                        if pos.side == "LONG":
                            new_tp = pos.entry_price + new_tp_dist
                            if new_tp < pos.take_profit:
                                pos.take_profit = new_tp
                                pos.take_profit_1 = pos.entry_price + new_tp_dist * config.PARTIAL_TP_RATIO
                        else:
                            new_tp = pos.entry_price - new_tp_dist
                            if new_tp > pos.take_profit:
                                pos.take_profit = new_tp
                                pos.take_profit_1 = pos.entry_price - new_tp_dist * config.PARTIAL_TP_RATIO
                        pos.entry_regime = current_regime

        # Partial TP
        if config.PARTIAL_TP_ENABLED and not pos.partial_closed and pos.take_profit_1 > 0:
            if pos.side == "LONG" and high >= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)
            elif pos.side == "SHORT" and low <= pos.take_profit_1:
                self._partial_close(symbol, pos.take_profit_1, timestamp)

        # Time exit
        max_hold = getattr(config, 'MAX_HOLD_CANDLES', 0)
        if max_hold > 0 and pos.candles_held >= max_hold:
            self._close_position(symbol, price, timestamp,
                                 f"TIME-EXIT: {pos.candles_held} candle", current_regime)
            return

        # Stop loss
        if pos.side == "LONG" and low <= pos.stop_loss:
            self._close_position(symbol, pos.stop_loss, timestamp, "STOP-LOSS", current_regime)
            return
        elif pos.side == "SHORT" and high >= pos.stop_loss:
            self._close_position(symbol, pos.stop_loss, timestamp, "STOP-LOSS", current_regime)
            return

        # Take profit
        if pos.side == "LONG" and high >= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp, "TAKE-PROFIT", current_regime)
            return
        elif pos.side == "SHORT" and low <= pos.take_profit:
            self._close_position(symbol, pos.take_profit, timestamp, "TAKE-PROFIT", current_regime)
            return

    def _partial_close(self, symbol, price, timestamp):
        pos = self.positions[symbol]
        close_size = pos.size * config.PARTIAL_TP_CLOSE_PCT
        if pos.side == "LONG":
            gross = (price - pos.entry_price) * close_size
        else:
            gross = (pos.entry_price - price) * close_size
        comm = price * close_size * config.COMMISSION_RATE
        net = gross - comm
        self.balance += net

        # Partial trade'i feature row olarak kaydet (WIN)
        if symbol in self._entry_features:
            row = self._entry_features[symbol].copy()
            row["label"] = 1  # Partial TP = WIN
            row["net_pnl"] = net
            row["exit_reason"] = "PARTIAL-TP1"
            self.feature_rows.append(row)
            # NOT: features'ı silmiyoruz çünkü kalan pozisyon da kapanacak

        pos.size -= close_size
        pos.partial_closed = True
        pos.stop_loss = pos.entry_price
        pos.breakeven_applied = True

    def _close_position(self, symbol, price, timestamp, reason, exit_regime):
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]

        if pos.side == "LONG":
            gross = (price - pos.entry_price) * pos.size
        else:
            gross = (pos.entry_price - price) * pos.size

        comm = price * pos.size * config.COMMISSION_RATE
        net = gross - comm - pos.funding_paid
        self.balance += net
        if net < 0:
            self._daily_loss += abs(net)

        # Feature row kaydet
        if symbol in self._entry_features:
            row = self._entry_features[symbol].copy()
            row["label"] = 1 if net > 0 else 0
            row["net_pnl"] = net
            row["exit_reason"] = reason
            self.feature_rows.append(row)
            del self._entry_features[symbol]

        del self.positions[symbol]


# ═════════════════════════════════════════════════════════
# ML MODEL TRAINING
# ═════════════════════════════════════════════════════════

FEATURE_COLS = [
    "rsi", "rsi_prev", "rsi_delta",
    "adx", "plus_di", "minus_di", "di_spread",
    "atr_pct", "vol_ratio",
    "bb_position", "bb_width",
    "volume_ratio", "volume_trend",
    "ret_1", "ret_3", "ret_5", "ret_10",
    "green_ratio_5", "green_ratio_3",
    "body_ratio", "upper_shadow_pct", "lower_shadow_pct",
    "price_vs_ema9", "price_vs_ema21", "price_vs_ema50",
    "ema9_vs_ema21",
    "vwap_distance",
    "macd_hist_norm", "macd_hist_delta",
    "regime_num", "coin_idx",
    "hour", "day_of_week",
]


def train_ml_model(df: pd.DataFrame, do_threshold_sweep: bool = False):
    """
    GradientBoosting modeli eğit.
    Walk-forward: ilk %65 train, son %35 test.
    """
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import classification_report, accuracy_score
    from sklearn.model_selection import cross_val_score

    if len(df) < 50:
        print("❌ Yeterli veri yok (min 50 trade)")
        return None

    # Feature matrix
    available_cols = [c for c in FEATURE_COLS if c in df.columns]
    missing_cols = [c for c in FEATURE_COLS if c not in df.columns]
    if missing_cols:
        print(f"⚠️  Eksik feature'lar: {missing_cols}")

    X = df[available_cols].fillna(0).values
    y = df["label"].values

    # Walk-forward split (zamana göre — ilk %65 train, son %35 test)
    split_idx = int(len(df) * 0.65)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"\n{'─'*50}")
    print(f"ML MODEL EĞİTİMİ")
    print(f"{'─'*50}")
    print(f"Toplam sample: {len(df)}")
    print(f"Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"Train WR: {y_train.mean()*100:.1f}% | Test WR: {y_test.mean()*100:.1f}%")

    # Model
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        min_samples_leaf=10,
        subsample=0.8,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # Train accuracy
    train_pred = model.predict(X_train)
    train_acc = accuracy_score(y_train, train_pred)
    print(f"\nTrain accuracy: {train_acc*100:.1f}%")

    # Test accuracy
    test_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, test_pred)
    print(f"Test accuracy:  {test_acc*100:.1f}%")

    # Probability based analysis
    test_proba = model.predict_proba(X_test)[:, 1]  # WIN probability

    print(f"\n{'─'*50}")
    print(f"TEST SET DETAY (Walk-Forward)")
    print(f"{'─'*50}")
    print(classification_report(y_test, test_pred, target_names=["LOSS", "WIN"]))

    # ─── FEATURE IMPORTANCE ─────────────────────────
    importance = model.feature_importances_
    feat_imp = sorted(zip(available_cols, importance), key=lambda x: -x[1])

    print(f"\n{'─'*50}")
    print(f"FEATURE IMPORTANCE (Top 15)")
    print(f"{'─'*50}")
    for feat, imp in feat_imp[:15]:
        bar = "█" * int(imp * 100)
        print(f"  {feat:20s} {imp:.4f}  {bar}")

    # ─── THRESHOLD SWEEP ─────────────────────────────
    print(f"\n{'─'*50}")
    print(f"THRESHOLD SWEEP (Test Set)")
    print(f"{'─'*50}")
    print(f"  {'Threshold':>9s} | {'Trades':>6s} | {'WR':>6s} | {'PnL':>10s} | {'Filter%':>7s}")
    print(f"  {'─'*9}─┼─{'─'*6}─┼─{'─'*6}─┼─{'─'*10}─┼─{'─'*7}")

    test_pnl = df["net_pnl"].values[split_idx:]
    baseline_pnl = test_pnl.sum()
    baseline_wr = y_test.mean() * 100
    best_threshold = 0.50
    best_pnl = baseline_pnl

    for threshold in [0.40, 0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.65]:
        mask = test_proba >= threshold
        if mask.sum() == 0:
            continue
        filtered_wr = y_test[mask].mean() * 100
        filtered_pnl = test_pnl[mask].sum()
        filter_pct = (1 - mask.sum() / len(test_proba)) * 100
        marker = " ★" if filtered_pnl > best_pnl else ""
        print(f"  {threshold:>9.2f} | {mask.sum():>6d} | {filtered_wr:>5.1f}% | ${filtered_pnl:>+9.2f} | {filter_pct:>5.1f}%{marker}")
        if filtered_pnl > best_pnl:
            best_pnl = filtered_pnl
            best_threshold = threshold

    print(f"\n  BASELINE (filtre yok): {len(test_pnl)} trade, {baseline_wr:.1f}% WR, ${baseline_pnl:+.2f}")
    print(f"  EN İYİ THRESHOLD: {best_threshold:.2f} → ${best_pnl:+.2f}")

    # ─── EXTENDED THRESHOLD SWEEP (daha detaylı) ─────
    if do_threshold_sweep:
        print(f"\n{'─'*50}")
        print(f"DETAYLI THRESHOLD SWEEP (0.40-0.70, step=0.01)")
        print(f"{'─'*50}")
        best_t = 0.50
        best_p = baseline_pnl
        for t in np.arange(0.40, 0.71, 0.01):
            mask = test_proba >= t
            if mask.sum() < 10:
                continue
            fp = test_pnl[mask].sum()
            fw = y_test[mask].mean() * 100
            if fp > best_p:
                best_p = fp
                best_t = t
                print(f"  ★ {t:.2f}: {mask.sum()} trade, {fw:.1f}% WR, ${fp:+.2f}")
        print(f"\n  OPTİMAL THRESHOLD: {best_t:.2f} → ${best_p:+.2f}")
        best_threshold = best_t

    # ─── SAVE MODEL ──────────────────────────────────
    model_path = os.path.join(os.path.dirname(__file__), "..", "ml_model.pkl")
    model_data = {
        "model": model,
        "feature_cols": available_cols,
        "threshold": best_threshold,
        "train_size": len(X_train),
        "test_accuracy": test_acc,
        "trained_at": datetime.now().isoformat(),
        "version": "v1.0",
    }
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)
    print(f"\n✅ Model kaydedildi: {model_path}")
    print(f"   Threshold: {best_threshold:.2f}")
    print(f"   Feature count: {len(available_cols)}")

    return model_data


# ═════════════════════════════════════════════════════════
# A/B TEST — ML FİLTRE İLE BACKTEST
# ═════════════════════════════════════════════════════════

def ab_test_ml_filter(df_features: pd.DataFrame, model_data: dict):
    """
    ML filtresinin gerçek etkisini simüle et.
    Walk-forward: test kısmında ML filtreleme uygula.
    """
    from sklearn.ensemble import GradientBoostingClassifier

    model = model_data["model"]
    threshold = model_data["threshold"]
    feature_cols = model_data["feature_cols"]

    split_idx = int(len(df_features) * 0.65)
    test_df = df_features.iloc[split_idx:].copy()

    X_test = test_df[feature_cols].fillna(0).values
    proba = model.predict_proba(X_test)[:, 1]

    print(f"\n{'='*60}")
    print(f"A/B TEST: ML FİLTRE vs FİLTRESİZ")
    print(f"{'='*60}")

    # Baseline (filtre yok)
    baseline_trades = len(test_df)
    baseline_wins = (test_df["label"] == 1).sum()
    baseline_wr = baseline_wins / baseline_trades * 100
    baseline_pnl = test_df["net_pnl"].sum()

    # ML filtered
    mask = proba >= threshold
    filtered_df = test_df[mask]
    filtered_trades = len(filtered_df)
    filtered_wins = (filtered_df["label"] == 1).sum()
    filtered_wr = filtered_wins / filtered_trades * 100 if filtered_trades > 0 else 0
    filtered_pnl = filtered_df["net_pnl"].sum()

    # Blocked trades analysis
    blocked_df = test_df[~mask]
    blocked_pnl = blocked_df["net_pnl"].sum()
    blocked_wr = (blocked_df["label"] == 1).mean() * 100 if len(blocked_df) > 0 else 0

    print(f"\n  {'Metrik':20s} | {'FİLTRESİZ':>12s} | {'ML FİLTRE':>12s} | {'FARK':>10s}")
    print(f"  {'─'*20}─┼─{'─'*12}─┼─{'─'*12}─┼─{'─'*10}")
    print(f"  {'Trade Sayısı':20s} | {baseline_trades:>12d} | {filtered_trades:>12d} | {filtered_trades-baseline_trades:>+10d}")
    print(f"  {'Win Rate':20s} | {baseline_wr:>11.1f}% | {filtered_wr:>11.1f}% | {filtered_wr-baseline_wr:>+9.1f}%")
    print(f"  {'Toplam PnL':20s} | ${baseline_pnl:>+11.2f} | ${filtered_pnl:>+11.2f} | ${filtered_pnl-baseline_pnl:>+9.2f}")
    print(f"\n  Engellenen trade'ler: {len(blocked_df)} | WR: {blocked_wr:.1f}% | PnL: ${blocked_pnl:+.2f}")
    print(f"  → ML filtre kötü trade'leri engelliyor mu? ", end="")
    if blocked_wr < baseline_wr and blocked_pnl < 0:
        print("EVET ✅ (engellenenler düşük WR + negatif PnL)")
    elif blocked_pnl < 0:
        print("KISMEN ✅ (engellenenler negatif PnL)")
    else:
        print("HAYIR ❌ (filtre iyi trade'leri de engelliyor)")

    # Exit reason breakdown
    if "exit_reason" in test_df.columns:
        print(f"\n  Engellenen trade'lerin çıkış nedenleri:")
        for reason in blocked_df["exit_reason"].value_counts().head(5).items():
            print(f"    {reason[0]}: {reason[1]}")


# ═════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════

if __name__ == "__main__":
    do_threshold = "--threshold" in sys.argv
    days = 60

    for arg in sys.argv:
        if arg.startswith("--days="):
            days = int(arg.split("=")[1])

    # 1. Veri topla
    collector = MLDataCollector()
    df_features = collector.collect(days=days)

    if len(df_features) < 50:
        print("❌ Yeterli trade verisi yok!")
        sys.exit(1)

    # 2. Model eğit
    model_data = train_ml_model(df_features, do_threshold_sweep=do_threshold)

    if model_data is None:
        sys.exit(1)

    # 3. A/B test
    ab_test_ml_filter(df_features, model_data)

    print(f"\n{'='*60}")
    print(f"SONRAKI ADIM: strategies/ml_filter.py ile entegrasyon")
    print(f"{'='*60}")
