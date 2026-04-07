"""
config.py - War Machine Configuration v13.0
=======================================
Single source of truth. All settings here.

Degisiklikler (v13.0):
  [FIX-1] MAX_POSITIONS: 4 -> 2 (deadlock onleme, $10k bakiyede 2 pozisyon yeterli)
  [FIX-2] SYMBOLS: 24 coin -> 9 coin (kanıtlanmis, backtest'te karli olanlar)
  [FIX-3] MAX_NOTIONAL_PCT config'e tasindi (pre_trade.py ile tutarli)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# EXCHANGE
EXCHANGE = "BINANCE"
BASE_CURRENCY = "USDT"

# Coin listesi: VERIFIED kazanan kombinasyonlar SADECE
# Edge Discovery v2.0'dan gelen yeni coinler eklendi
# SHORT KAPALI: 57 trade, %35 WR, -$3,658 zarar kanıtlanmış
# LONG-ONLY: %54 WR, +$2,679 kâr kanıtlanmış
SYMBOLS = [
    # === ÇEKİRDEK (19 coin, backtest'te kanıtlı + Edge keşfedilen) ===
    # STRONG EDGE'LER (WR ≥ 60%)
    "BTCUSDT", "ETHUSDT", "BNBUSDT",              # Top 3 market cap
    "XRPUSDT", "SOLUSDT", "AVAXUSDT",             # Edge proven, strong patterns
    
    # GOOD EDGE'LER (WR 50-60%)
    "ADAUSDT", "LTCUSDT", "DOGEUSDT",             # Trend down/oversold patterns
    "AAVEUSDT", "UNIUSDT", "PEPEUSDT",            # Volatility/momentum patterns
    
    # VOLATIILITE + HACIM OYUNCULAR
    "VETUSDT", "ZECUSDT", "FLOWUSDT",             # Strong momentum patterns
    "LDOUSDT", "CRVUSDT", "OPUSDT",               # High volatility edges
    
    # === UYDU HAVUZU (Edge-based, dinamik) ===
    "ATOMUSDT", "NEARUSDT",                       # Discovered patterns
    "SUIUSDT", "INJUSDT",                         # Squeeze breakout, BB squeeze
    "WIFUSDT", "ARPAUSDT",                        # Low volatility, BB squeeze
    "XLMUSDT", "KAVAUSDT",                        # Legacy support
    
    # === v15.8 YENİ COİNLER (backtest kanıtlı) ===
    "FILUSDT",                                      # %54.8 WR, +$114 (EN İYİ YENİ COİN)
    "DOTUSDT",                                      # %43.5 WR, +$28 (büyük kazançlar)
    "ARBUSDT",                                      # %51.9 WR, +$17 (kârlı)
]

# === EDGE DISCOVERY v3 AYARLARI ===
ALLOW_EDGE_DISCOVERY = True                     # Edge patterns aktif
TOP_3_COINS = [                                 # Backtest v3 kârlı coinler
    "AAVEUSDT",   # %60 WR, +$40
    "AVAXUSDT",   # %51.9 WR, +$32
    "DOGEUSDT",   # %52 WR, +$31
]
EDGE_DISCOVERY_FOCUS_MODE = True               # Sadece top 3'e odaklan
EDGE_MIN_SAMPLE_SIZE = 50                      # N > 50 (istatistiksel güven)
EDGE_MIN_WIN_RATE = 0.65                       # WR > 65% (yüksek kalite)

# === PAPER TRADING v1 (7 günlük deneme) ===
PAPER_TRADING_MODE = True                      # Bağlantı: REAL_TRADING_ENABLED=False
PAPER_TRADING_DURATION_DAYS = 7               # 7 gün
PAPER_TRADING_START_DATE = "2026-04-03"        # Başlangıç tarihi
PAPER_TRADING_LOG_SIGNALS = True               # Telegram'da sinyalleri kaydet

# === LIKIDATION KORUMASI ===
LIQUIDATION_ALERT_ENABLED = True               # Likidation İğnesi uyarısı
LIQUIDATION_RISK_THRESHOLD = 0.05              # 5% mesafe = HIGH risk
LIQUIDATION_CRITICAL_THRESHOLD = 0.02          # 2% mesafe = CRITICAL
LIQUIDATION_VOLUME_SPIKE_PCT = 30.0            # 30% volume spike
LIQUIDATION_CHECK_INTERVAL = 300               # Her 5 dakikada kontrol

# WEBSOCKET
WS_URI = "wss://stream.binance.com:9443/stream"
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20
WS_RECONNECT_DELAY_MIN = 1
WS_RECONNECT_DELAY_MAX = 60
WS_MAX_RECONNECT_ATTEMPTS = 10

# CANDLE
CANDLE_INTERVAL = "4h"  # Trend için daha temiz (gürültü azaltma)
CANDLE_INTERVAL_SHORT = "1h"  # Mean reversion entry (RSI oversold)
CANDLE_HISTORY_COUNT = 100
CANDLE_MAX_STORED = 200
MIN_CANDLES_FOR_STRATEGY = 30

# ACCOUNT
INITIAL_BALANCE = 10000.0
COMMISSION_RATE = 0.001         # 0.1% per trade

# STRATEGY
STRATEGY_MIN_CONFIDENCE = 0.40
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BB_PERIOD = 20
BB_STD = 2.0
VWAP_DEVIATION = 0.010

# REGIME WEIGHTS (voting ağırlıkları - regime'e göre)
REGIME_WEIGHTS = {
    "TREND_UP":   {"RSI": 0.15, "MOMENTUM": 0.45, "VWAP": 0.15, "EDGE_DISCOVERY": 0.25},
    "TREND_DOWN": {"RSI": 0.15, "MOMENTUM": 0.45, "VWAP": 0.15, "EDGE_DISCOVERY": 0.25},
    "RANGING":    {"RSI": 0.30, "MOMENTUM": 0.10, "VWAP": 0.35, "EDGE_DISCOVERY": 0.25},
    "VOLATILE":   {"RSI": 0.20, "MOMENTUM": 0.20, "VWAP": 0.30, "EDGE_DISCOVERY": 0.30},
}

# BEAR GUARD
BEAR_GUARD_ENABLED = False
ALLOW_LONG = True                # LONG AÇIK: Sistem long-only mode'de
ALLOW_SHORT = False  # SHORT KAPALI: genel olarak kapalı
ALLOW_SHORT_CONDITIONAL = True  # Koşullu SHORT: sadece TREND_DOWN + kanıtlanmış edge patterns
VOLATILE_BLOCK_ENABLED = True

# TREND_UP BLOCK — Backtest v3: 88 trade, %30.7 WR, -$842
# Trend zirve girişleri sürekli kaybettiriyor → TREND_UP'ta işlem açma
TREND_UP_BLOCK = True

# DIP-BUY FILTER — DEVRE DIŞI: 48.8% < 49.3%, ters etki
DIP_BUY_FILTER = False

# [v15.9] VOLUME QUALITY FILTER — ML feature importance'tan keşfedildi
# Hacim < 20-mum ortalamasının %70'i → sinyal zayıf → trade açma
# 25 A/B test sonucu: PnL +$471→$567, PF 1.30→1.48, WR 51.3%→52.3%
MIN_VOLUME_RATIO = 0.70

# COIN BLACKLIST — Backtest v3: WR<%30, sürekli zarar eden coinler
# v15.5.0: UNIUSDT %16.7, ATOMUSDT %21.4, SOLUSDT %22.2, OPUSDT %25, NEARUSDT %25, XLMUSDT %25
# v15.5.1: KAVAUSDT %33, INJUSDT %41, PEPEUSDT %44, ARPAUSDT %43 (hepsi net zararda)
COIN_BLACKLIST = [
    "UNIUSDT", "ATOMUSDT", "OPUSDT", "NEARUSDT", "XLMUSDT", "SOLUSDT",  # WR<%30
    "KAVAUSDT", "INJUSDT", "PEPEUSDT", "ARPAUSDT",                       # WR<%45, net zararda
    "SUIUSDT",                                                             # v15.5.2: %30 WR, -$50
    "BNBUSDT", "XRPUSDT", "LDOUSDT",                                      # [v15.7] WR<%45, net zararda
]

# RISK (PRE-TRADE)
MAX_POSITION_SIZE_PCT = 0.10   # Her pozisyon max equity %10 notional
MAX_NOTIONAL_PCT = 0.10        # pre_trade.py ile tutarli
RISK_PER_TRADE_PCT = 0.01      # %1 risk per trade (position size küçültme)
RISK_BASE_PCT = 0.005          # %0.5 base risk (volatility adjusted)
VOLATILITY_MULTIPLIER = True   # Enable volatility adjustment
MIN_EQUITY_THRESHOLD = 1000.0
MAX_POSITIONS = 4              # [FIX-1] 6'ten 4'ye indirildi — deadlock onleme
LEVERAGE = 5                   # Paper trade'de leverage yok
MIN_PROFIT_PCT = 0.003
MIN_TRADE_INTERVAL = 60
MAX_DAILY_TRADES = 10
MAX_DAILY_LOSS = 200.0
EMERGENCY_STOP_LOSS = 0.05
MAX_CONSECUTIVE_LOSSES = 15
MAX_ATR_VOLATILITY = 0.05

# STOP LOSS / TAKE PROFIT - DYNAMIC R:R (regime-based)
SL_ATR_MULTIPLIER = 1.5        # Fallback (kullanılmıyorsa)
TP_ATR_MULTIPLIER = 3.0        # Fallback (kullanılmıyorsa)

# Regime-based Dynamic R:R
# RANGING: Dar SL/TP → hızlı kapanış (4-8h), R:R=1.5:1
# TREND_UP/DOWN: Geniş TP → trend yakala, R:R=2.67:1
DYNAMIC_RR = {
    "TREND_UP":   {"sl": 1.5, "tp": 4.0},   # R:R = 2.67:1 (BLOCKED by TREND_UP_BLOCK)
    "TREND_DOWN": {"sl": 1.5, "tp": 4.0},   # R:R = 2.67:1
    "RANGING":    {"sl": 1.0, "tp": 1.2},   # R:R = 1.2:1 [v15.5] 1.5→1.2
    "VOLATILE":   {"sl": 1.5, "tp": 3.0},   # R:R = 2.0:1 (fallback)
}

# PARTIAL TAKE PROFIT
PARTIAL_TP_ENABLED = True
PARTIAL_TP_RATIO = 0.50       # TP1 = TP mesafesinin %50'si
PARTIAL_TP_CLOSE_PCT = 0.80   # [v15.7] 0.70→0.80 TP1'de %80 kapat (daha fazla kâr kilitle)

# BREAKEVEN STOP
BREAKEVEN_ATR_TRIGGER = 0.7    # [v15.5] 1.0→0.7 (0.5 çok agresif, 0.7 optimal)

# MAX HOLD — v15.5: 3 candle, v15.7: 2 candle
# Analiz: 1 candle WR=49.9% +$518, 2 candle WR=46.5% -$167, 3 candle WR=48.6% -$413
# MAX_HOLD=2 → PnL +$96, PF=1.06, MaxDD=2.8% (baseline'dan +$157 iyileşme)
MAX_HOLD_CANDLES = 2           # [v15.7] 3→2 candle (8h sonra pozisyonu kapat)

# SMART EXIT (Regime Change)
SMART_EXIT_ENABLED = True       # Regime değiştiğinde akıllı çıkış
# Kârdaysa → kapat, Zarardaysa → TP'yi yeni regime'e göre daralt

# FUNDING FEE SİMÜLASYONU
FUNDING_FEE_RATE = 0.0001     # 0.01% per 8 hours (Binance default)
FUNDING_FEE_INTERVAL = 28800  # 8 saat = 28800 saniye

# MTF CONFIRMATION (15m trigger)
MTF_ENABLED = True             # 15m onay gate'i aktif
MTF_MAX_RETRIES = 4            # Max 4×15m = 1 saat bekleme
MTF_MIN_CANDLES = 20           # Minimum 15m candle for analysis

TRAILING_STOP_ACTIVATE = 0.035
TRAILING_STOP_DISTANCE = 0.01

# CORRELATION GROUPS
CORRELATION_GROUPS = [
    ["BTCUSDT", "ETHUSDT"],
    ["XRPUSDT", "ADAUSDT"],
    ["BNBUSDT"],
    ["LTCUSDT"],
    ["UNIUSDT", "AAVEUSDT"],
]

# BINANCE API
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
REAL_TRADING_ENABLED = False    # Paper trading

# TELEGRAM
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
HEALTH_REPORT_INTERVAL_HOURS = 0.25  # 15 dakika

# LOGGING
LOG_LEVEL = "INFO"
LOG_DIR = "logs"

# DATABASE
DB_PATH = "data/war_machine.db"

# TESTING & DEBUG
TEST_MODE = False  # ← DISABLED - NORMAL OPERATION
TEST_MODE_FORCE_REGIME = "TREND_UP"  # Force TREND_UP to auto-open first trade
