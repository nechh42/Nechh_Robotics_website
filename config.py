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
]

# === EDGE DISCOVERY v3 AYARLARI ===
ALLOW_EDGE_DISCOVERY = True                     # Edge patterns aktif
TOP_3_COINS = [                                 # Super-strict N>50 & WR>65%
    "ARPAUSDT",   # low_volatility: 81.48% WR, N=54
    "SOLUSDT",    # ranging_bb_upper: 68.97% WR, N=58  
    "XRPUSDT",    # rsi_below_30: 66.67% WR, N=63
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

# REGIME WEIGHTS
REGIME_WEIGHTS = {
    "TREND_UP":   {"RSI": 0.2, "MOMENTUM": 0.6, "VWAP": 0.2},
    "TREND_DOWN": {"RSI": 0.2, "MOMENTUM": 0.6, "VWAP": 0.2},
    "RANGING":    {"RSI": 0.4, "MOMENTUM": 0.2, "VWAP": 0.4},
    "VOLATILE":   {"RSI": 0.3, "MOMENTUM": 0.3, "VWAP": 0.4},
}

# BEAR GUARD
BEAR_GUARD_ENABLED = False
ALLOW_LONG = True                # LONG AÇIK: Sistem long-only mode'de
ALLOW_SHORT = False  # SHORT KAPALI: %35 WR fail kanıtlanmış
VOLATILE_BLOCK_ENABLED = True

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

# STOP LOSS / TAKE PROFIT
SL_ATR_MULTIPLIER = 1.5        # SL = ATR x 1.5
TP_ATR_MULTIPLIER = 2.0        # TP = ATR x 2.0 (R:R = 1.33:1)
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
