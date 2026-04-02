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

# Coin listesi: backtest'te karli olan 9 coin
# XLMUSDT, OPUSDT, CRVUSDT, ATOMUSDT kaldirildi (zarar veriyor)
# KAVAUSDT kaldirildi (tutarsiz)
SYMBOLS = [
    "ZECUSDT",   # +$272 - en iyi SHORT performansi
    "PEPEUSDT",  # +$ - mean reversion SHORT
    "UNIUSDT",   # trending + aggressive
    "ADAUSDT",   # trending
    "AAVEUSDT",  # +$490 - en iyi 2 trade %100 WR
    "LDOUSDT",   # izleniyor
    "BNBUSDT",   # buyuk hacim
    "BTCUSDT",   # +$223 - guvenilir
    "LTCUSDT",   # dengeli
]

# WEBSOCKET
WS_URI = "wss://stream.binance.com:9443/stream"
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20
WS_RECONNECT_DELAY_MIN = 1
WS_RECONNECT_DELAY_MAX = 60
WS_MAX_RECONNECT_ATTEMPTS = 10

# CANDLE
CANDLE_INTERVAL = "1m"  # TEMPORARY: changed from "1h" to test candle closing
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
ALLOW_SHORT = True
VOLATILE_BLOCK_ENABLED = True

# RISK (PRE-TRADE)
MAX_POSITION_SIZE_PCT = 0.10   # Her pozisyon max equity %10 notional
MAX_NOTIONAL_PCT = 0.10        # pre_trade.py ile tutarli
RISK_PER_TRADE_PCT = 0.02      # %2 risk per trade
MIN_EQUITY_THRESHOLD = 1000.0
MAX_POSITIONS = 2              # [FIX-1] 4'ten 2'ye indirildi — deadlock onleme
LEVERAGE = 1                   # Paper trade'de leverage yok
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

# SUPERVISOR
SUPERVISOR_MAX_RESTARTS = 50
SUPERVISOR_RESTART_DELAY = 10
SUPERVISOR_CRASH_COOLDOWN = 300
