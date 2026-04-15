"""
config.py - War Machine v0 (COMBO V1)
=======================================
Single source of truth. 5 mean-reversion strateji.

8 Nisan 2026: Combo V1 Paper Trading başlangıcı
  - Strateji: ComboV1 (VWAP + EMA PB + Bollinger + Mean Rev + Keltner)
  - Dinamik coin keşfi aktif
  - MAX_HOLD=1 candle (4h)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# EXCHANGE
EXCHANGE = "BINANCE"
BASE_CURRENCY = "USDT"

# Coin listesi: Combo V1 backtest'te kârlı olan coinler
# ADAUSDT ve LTCUSDT çıkarıldı (sürekli zararlı: -$27 ve -$44)
# Dinamik coin keşfi ile liste otomatik güncellenecek
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "AVAXUSDT", "DOGEUSDT", "DOTUSDT",
]

# Dinamik Coin Keşfi
DYNAMIC_COIN_ENABLED = True
DYNAMIC_COIN_INTERVAL = 21600    # 6 saat (saniye)
DYNAMIC_COIN_MAX = 15            # Maksimum coin sayısı
DYNAMIC_COIN_MIN_VOLUME = 50_000_000  # Min $50M günlük hacim
DYNAMIC_COIN_BASE = [            # Her zaman listede kalacak coinler
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
]

# === PAPER TRADING v1 (7 günlük deneme) ===
PAPER_TRADING_MODE = True                      # Bağlantı: REAL_TRADING_ENABLED=False
PAPER_TRADING_DURATION_DAYS = 7               # 7 gün
PAPER_TRADING_START_DATE = "2026-04-08"        # Combo V1 temiz başlangıç
PAPER_TRADING_LOG_SIGNALS = True               # Telegram'da sinyalleri kaydet

# === LIKIDATION KORUMASI ===
LIQUIDATION_ALERT_ENABLED = True               # Likidation İğnesi uyarısı
LIQUIDATION_RISK_THRESHOLD = 0.05              # 5% mesafe = HIGH risk
LIQUIDATION_CRITICAL_THRESHOLD = 0.02          # 2% mesafe = CRITICAL
LIQUIDATION_VOLUME_SPIKE_PCT = 30.0            # 30% volume spike
LIQUIDATION_CHECK_INTERVAL = 300               # Her 5 dakikada kontrol

# WEBSOCKET
WS_URI = "wss://stream.binance.com:9443/stream"
WS_PING_INTERVAL = 30   # [8 Nisan] 20→30: 29 coin stream için 20s çok sıkı
WS_PING_TIMEOUT = 30    # [8 Nisan] 20→30: keepalive ping timeout önleme
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
STRATEGY_MIN_CONFIDENCE = 0.55  # v0: biraz daha seçici
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BB_PERIOD = 20
BB_STD = 2.0
VWAP_DEVIATION = 0.010

# REGIME WEIGHTS (voting ağırlıkları - regime'e göre)
# [v17] Basitleştirildi — uniform'a yakın → overfitting azaltma
REGIME_WEIGHTS = {
    "TREND_UP":   {"RSI": 0.20, "MOMENTUM": 0.35, "VWAP": 0.20, "EDGE_DISCOVERY": 0.25},
    "TREND_DOWN": {"RSI": 0.20, "MOMENTUM": 0.35, "VWAP": 0.20, "EDGE_DISCOVERY": 0.25},
    "RANGING":    {"RSI": 0.25, "MOMENTUM": 0.15, "VWAP": 0.30, "EDGE_DISCOVERY": 0.30},
    "VOLATILE":   {"RSI": 0.25, "MOMENTUM": 0.25, "VWAP": 0.25, "EDGE_DISCOVERY": 0.25},
}

# BEAR GUARD
BEAR_GUARD_ENABLED = False
ALLOW_LONG = True                # LONG AÇIK: Sistem long-only mode'de
ALLOW_SHORT = False  # SHORT KAPALI: genel olarak kapalı
ALLOW_SHORT_CONDITIONAL = False  # [v16.1] KAPALI — backtest'te test edilmedi, temiz LONG-ONLY
VOLATILE_BLOCK_ENABLED = False  # v0: kapalı

# v0: Tüm rejim blokları kapalı — strateji kendi filtrelerini uygular
TREND_UP_BLOCK = False

# DIP-BUY FILTER — DEVRE DIŞI: 48.8% < 49.3%, ters etki
DIP_BUY_FILTER = False

# [v15.9] VOLUME QUALITY FILTER — ML feature importance'tan keşfedildi
# Hacim < 20-mum ortalamasının %70'i → sinyal zayıf → trade açma
# 25 A/B test sonucu: PnL +$471→$567, PF 1.30→1.48, WR 51.3%→52.3%
MIN_VOLUME_RATIO = 0.70  # [v17.1] Volume filtresi (WebSocket volume fix ile çalışıyor)

# ML FILTER — Eğitilmiş model ile düşük kaliteli sinyalleri engelle
# ml_model.pkl yoksa otomatik devre dışı kalır
# [8 Nisan] KAPALI: 6 trade ile model anlamsız, 50+ trade birikince aç
ML_FILTER_ENABLED = False

# [ADIM 9] DOT blacklist: 60g -$35.6, 90g -$47.4 sürekli zarar
COIN_BLACKLIST = ["DOTUSDT"]

# RISK (PRE-TRADE)
MAX_POSITION_SIZE_PCT = 0.10   # Her pozisyon max equity %10 notional
MAX_NOTIONAL_PCT = 0.10        # pre_trade.py ile tutarli
RISK_PER_TRADE_PCT = 0.01      # %1 risk per trade (position size küçültme)
RISK_BASE_PCT = 0.005          # %0.5 base risk (volatility adjusted)
VOLATILITY_MULTIPLIER = True   # Enable volatility adjustment
MIN_EQUITY_THRESHOLD = 1000.0
MAX_POSITIONS = 4              # [FIX-1] 6'ten 4'ye indirildi — deadlock onleme
LEVERAGE = 3                   # [v16.1] 3x optimal: PnL 2x, 0 likidasyon, PF=1.71
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

# v0: Tüm rejimlerde aynı SL/TP — basit, eşit
DYNAMIC_RR = {
    "TREND_UP":   {"sl": 1.0, "tp": 1.0},
    "TREND_DOWN": {"sl": 1.0, "tp": 1.0},
    "RANGING":    {"sl": 1.0, "tp": 1.0},
    "VOLATILE":   {"sl": 1.0, "tp": 1.0},
}

# v0: Partial TP kapalı — sadece SL veya TP
PARTIAL_TP_ENABLED = False
PARTIAL_TP_RATIO = 0.50
PARTIAL_TP_CLOSE_PCT = 0.50

# [ADIM 9] Breakeven: fiyat +0.5×ATR kâra geçince SL → entry
# Backtest: PF 1.46→2.15, PnL $172→$420 (60g)
BREAKEVEN_ATR_TRIGGER = 0.5

# [ADIM 9] 2 candle = 8 saat — trailing stop ile kazımı uzat
# Backtest: trail + hold=2 en iyi combo
MAX_HOLD_CANDLES = 2

# SMART EXIT (Regime Change)
SMART_EXIT_ENABLED = True       # Regime değiştiğinde akıllı çıkış
# Kârdaysa → kapat, Zarardaysa → TP'yi yeni regime'e göre daralt

# FUNDING FEE SİMÜLASYONU
FUNDING_FEE_RATE = 0.0001     # 0.01% per 8 hours (Binance default)
FUNDING_FEE_INTERVAL = 28800  # 8 saat = 28800 saniye

# v0: MTF kapalı — basitlik
MTF_ENABLED = False
MTF_MAX_RETRIES = 4            # Max 4×15m = 1 saat bekleme
MTF_MIN_CANDLES = 20           # Minimum 15m candle for analysis

# [ADIM 9] Trailing stop: 0.7×ATR tetik, 0.3×ATR mesafe
# Backtest (60g): PF 2.15, PnL +$420 | (90g): PF 1.81, PnL +$396
TRAILING_STOP_ACTIVATE = 0.007   # 0.7% → orchestrator ATR bazlı kullanacak
TRAILING_STOP_DISTANCE = 0.003   # 0.3% → orchestrator ATR bazlı kullanacak

# [ADIM 9] ATR bazlı trailing (stop_manager.py tarafından kullanılır)
TRAIL_ACTIVATE_ATR = 0.7   # Fiyat +0.7×ATR kâra geçince trail başlasın
TRAIL_DISTANCE_ATR = 0.3   # Trail mesafesi: 0.3×ATR

# CORRELATION GROUPS — [v16.1] Aktif 14 coin'e göre güncellendi
CORRELATION_GROUPS = [
    ["ETHUSDT", "ADAUSDT"],           # L1 grubu
    ["AVAXUSDT", "DOTUSDT"],          # L1-alt grubu
    ["LTCUSDT", "ZECUSDT"],           # PoW grubu
    ["DOGEUSDT", "WIFUSDT"],          # Meme grubu
    ["AAVEUSDT", "CRVUSDT"],          # DeFi grubu
    ["FILUSDT", "ARBUSDT"],           # Infra/L2 grubu
    ["FLOWUSDT"],                     # Tek
    ["VETUSDT"],                      # Tek
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
SUMMARY_REPORT_INTERVAL_HOURS = 6    # 6 saatte bir genel özet raporu

# TELEGRAM — NECHH ROBOTICS (Abonelik + Kanal sistemi)
TELEGRAM_SUB_BOT_TOKEN = os.getenv("TELEGRAM_SUB_BOT_TOKEN", "")
TELEGRAM_PRO_CHANNEL_ID = os.getenv("TELEGRAM_PRO_CHANNEL_ID", "")
TELEGRAM_VIP_CHANNEL_ID = os.getenv("TELEGRAM_VIP_CHANNEL_ID", "")
TELEGRAM_ADMIN_IDS = os.getenv("TELEGRAM_ADMIN_IDS", "")

# EXTERNAL APIs (Telegram modülleri için)
CRYPTOPANIC_TOKEN = os.getenv("CRYPTOPANIC_TOKEN", "")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OLLAMA_MODEL = "deepseek-r1:1.5b"

# LOGGING
LOG_LEVEL = "INFO"
LOG_DIR = "logs"

# DATABASE
DB_PATH = "data/war_machine.db"

# TESTING & DEBUG
TEST_MODE = False  # ← DISABLED - NORMAL OPERATION
TEST_MODE_FORCE_REGIME = "TREND_UP"  # Force TREND_UP to auto-open first trade
