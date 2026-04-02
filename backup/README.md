# WAR MACHINE v2.1 - Crypto Trading Engine

## Akis

```
Binance WS → Tick → CandleManager → 1m Candle kapanir →
Regime detect (4 mod) → 3 Strateji evaluate (candle OHLCV) →
Smart Conflict Vote (adaptive weights) →
Pre-Trade Risk (15 check + sentiment + bear guard) →
Dynamic Kelly Sizing → Execute → DB + Telegram
```

## Dosya Yapisi (37 dosya)

```
war_machine/
├── config.py                   # Tek config dosyasi
├── main.py                     # Giris noktasi
├── supervisor.py               # Auto-restart + Telegram crash alert
├── query_status.py             # Hizli durum sorgusu
├── data/
│   ├── candle_manager.py       # REST kline + tick-to-candle aggregator
│   ├── datafeed.py             # Binance WebSocket
│   └── sentiment.py            # Fear & Greed API (ucretsiz)
├── strategies/
│   ├── base.py                 # Strateji arayuzu
│   ├── indicators.py           # RSI, BB, ATR, VWAP, EMA, MACD
│   ├── regime.py               # 4-rejim: TREND_UP/DOWN, RANGING, VOLATILE
│   ├── rsi_reversion.py        # RSI + MACD dual konfirmasyon
│   ├── momentum.py             # BB Breakout + Volume zorunlu
│   └── vwap_reversion.py       # VWAP Mean Reversion
├── engine/
│   ├── signal.py               # Signal dataclass
│   ├── state.py                # Pozisyon + bakiye (tek dogru kaynak)
│   ├── voting.py               # Smart conflict detection + adaptive weights
│   ├── adaptive_weights.py     # Self-learning (trade sonuclarindan ogrenme)
│   └── orchestrator.py         # Ana akis
├── risk/
│   ├── pre_trade.py            # 15 kontrol (fren sistemi)
│   ├── stop_manager.py         # SL/TP/Trailing stop
│   └── position_sizer.py       # Dynamic Kelly Criterion
├── execution/
│   ├── paper.py                # Paper trading
│   └── binance.py              # Gercek Binance Spot API
├── monitoring/
│   ├── telegram.py             # Trade + sistem bildirimleri
│   ├── performance.py          # PnL, Sharpe, drawdown
│   └── health.py               # 30dk periyodik saglik raporu
├── persistence/
│   └── database.py             # SQLite (trade + pozisyon persistence)
├── backtest/
│   └── engine.py               # Tarihsel veri ile backtest
└── tests/
```

## Calistirma

```bash
python main.py              # Paper trading
python supervisor.py         # Production (auto-restart)
python query_status.py       # Anlik durum sorgusu
python -m backtest.engine --symbol BTCUSDT --days 30  # Backtest
```

## Farkliliklar (Piyasadaki botlardan ne farki var?)

| Ozellik | Siradan Bot | War Machine |
|---------|-------------|-------------|
| Veri | Tick (gurultu) | Candle OHLCV (temiz) |
| Strateji | Tek gosterge | 3 strateji + MACD konfirmasyon |
| Rejim | Yok | 4 mod (ADX + volatilite) |
| Risk | Stop-loss (kaza sonrasi) | 15 kontrol (kaza oncesi fren) |
| Sentiment | Yok | Fear & Greed API (canli) |
| Bear Guard | Yok | Dusus trendinde LONG bloklama |
| Volatile Block | Yok | Kaos modunda trade yok |
| Pozisyon boyutu | Sabit %5 | Dynamic Kelly (ogrenme bazli) |
| Agirliklar | Sabit | Adaptive (trade sonuclarindan ogrenme) |
| Catisma | Yok | Zit sinyaller iptal |
| Persistence | Yok | Restart sonrasi pozisyonlar korunur |
| Monitoring | Yok | 30dk Telegram saglik raporu |
| Crash | Olur bilinmez | Supervisor auto-restart + alert |

## Pre-Trade Risk (15 Kontrol - Fren Sistemi)

1. Bear Guard (dusus trendinde LONG blok)
2. Volatile Block (kaos modunda trade yok)
3. Sentiment filtresi (Extreme Fear = LONG blok)
4. Equity minimum esik
5. Gunluk zarar limiti
6. Gunluk trade limiti
7. Max pozisyon sayisi
8. Sembol basina tek pozisyon
9. Korelasyon filtresi (BTC+ETH ayni anda yok)
10. Trade cooldown (60s)
11. Ardisik kayip limiti
12. Gecersiz fiyat kontrolu
13. Min kar vs komisyon
14. Risk bazli pozisyon boyutu (Kelly)
15. ATR volatilite kilidi

## Backtest Sonuclari (30 gun, 1h mumlar)

```
BTCUSDT: 19 trade, %36.8 WR, -$10.67, MaxDD %0.5, Sharpe -0.04
ETHUSDT: 21 trade, %38.1 WR, +$4.53,  MaxDD %0.6, Sharpe +0.02
SOLUSDT: 18 trade, %33.3 WR, -$22.09, MaxDD %0.4, Sharpe -0.09
```

Risk yonetimi calisiyor: MaxDD %0.4-0.6 (cok dusuk)
