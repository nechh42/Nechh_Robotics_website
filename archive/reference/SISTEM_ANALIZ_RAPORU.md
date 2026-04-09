# WAR MACHINE — TAM SİSTEM ADLİ ANALİZ RAPORU

**Tarih:** 2026-04-23  
**Analiz süresi:** 20 günlük paper trading periyodu (sıfır trade)  
**Sonuç:** Sistem yapısal olarak çalışamaz durumda. Temel tasarım hataları var.

---

## YÖNETICI ÖZETİ

War Machine 20 gündür paper trade modunda çalışıyor. **Sıfır (0) trade açmış.** Sistem teknik olarak stabil — WebSocket bağlı, Telegram çalışıyor, crash yok. Ama bir trade bile üretmiyor.

Bu rapor, sistemin neden trade yapamadığını en ince ayrıntısına kadar analiz eder. Bulgular acımasız ama gerçek.

**Ana Teşhis: Sistem yalnızca eşzamanlı olarak 6 kapının tümü açık olduğunda trade açabilir. Bu 6 kapının aynı anda açılma olasılığı, mevcut piyasa koşullarında fiilen SIFIR.**

---

## BÖLÜM 1: BLOKLAMA ZİNCİRİ (Trade Akışı Analizi)

Bir trade'in açılabilmesi için aşağıdaki 6 kapının **hepsinin** aynı anda açık olması gerekir:

```
Tick → 4h Mum Kapanışı → detect_regime()
  │
  ├─ KAPI 1: Sentiment ≥ 20 (Fear & Greed)    ❌ KAPALI (20 gündür = 12)
  │
  ├─ KAPI 2: Regime = TREND_UP                 ❌ KAPALI (0/26 coin TREND_UP)
  │
  ├─ KAPI 3: Strateji sinyal üretsin           ⚠️ KOŞULLU (VWAP+Edge sinyal üretebilir ama...)
  │
  ├─ KAPI 4: pre_trade: LONG sadece TREND_UP   ❌ KAPALI (RANGING/TREND_DOWN'da LONG yasak)
  │
  ├─ KAPI 5: Saat filtresi (00-06 UTC değil)   ✅ AÇIK (günün 18/24 saati)
  │
  └─ KAPI 6: Korelasyon filtresi               ✅ AÇIK (pozisyon yok)
```

**Sonuç: 6 kapıdan 3'ü kapalı. Trade imkansız.**

---

## BÖLÜM 2: BLOKERLARIN DETAYLI ANALİZİ

### BLOKER #1: Sentiment Filtresi (ASIL KATİL)

**Dosya:** `strategies/regime.py` satır 57-63  
**Mantık:** Fear & Greed < 20 → regime = VOLATILE → tüm trade'ler engellenir

```python
fg_score = fear_greed.get_score()
if fg_score is not None and fg_score < 20:
    return "VOLATILE"  # → pre_trade.py'de "işlem açılmaz"
```

**Durum:** Fear & Greed endeksi 20+ gündür 10-18 aralığında. Şu an: **12 (Extreme Fear)**.

**Sonuç:** Sentiment filtresi tek başına **TÜM 26 coin için TÜM trade'leri engelliyor.** Bu filtre binary bir on/off switch — gradual degradation yok, kademeli risk azaltma yok. Sentiment 19 olsa da 1 olsa da aynı sonuç: **SIFIR TRADE.**

**Etki:** %100 bloklama. Sistemin en büyük tek sorunu.

---

### BLOKER #2: TREND_UP Zorunluluğu (SAKLI KATİL)

**Dosya:** `risk/pre_trade.py` satır 82-83  
**Mantık:** LONG sadece TREND_UP'ta açılır.

```python
if action == "LONG" and regime != "TREND_UP":
    return self._reject(symbol, action, "LONG sadece TREND_UP'ta açılır")
```

**Canlı Test Sonuçları (23 Nisan 2026):**

| Coin       | Fiyat      | Regime (Raw) | ADX  | 20-bar Değişim | TREND_UP? |
|-----------|-----------|-------------|------|---------------|----------|
| BTCUSDT   | $67,361   | RANGING     | 7.6  | +0.76%        | ❌       |
| ETHUSDT   | $2,062    | RANGING     | 4.3  | +0.13%        | ❌       |
| SOLUSDT   | $79.83    | RANGING     | 3.0  | +1.01%        | ❌       |
| XRPUSDT   | $1.30     | RANGING     | 9.6  | +0.04%        | ❌       |
| ARPAUSDT  | $0.01     | TREND_DOWN  | 8.7  | -3.32%        | ❌       |
| BNBUSDT   | $592.53   | RANGING     | 6.7  | +3.20%        | ❌       |
| ADAUSDT   | $0.24     | RANGING     | 5.4  | +1.67%        | ❌       |
| DOGEUSDT  | $0.09     | RANGING     | 9.9  | +0.21%        | ❌       |
| AVAXUSDT  | $8.85     | RANGING     | 11.2 | +1.37%        | ❌       |

**26 coinden 0 tanesi TREND_UP!** Sentiment filtresi olmasa bile **yine sıfır trade olurdu.**

Bu, BLOKER #1'den bile daha derin bir sorun. Çünkü piyasa RANGING'de ve RANGING'de LONG izin verilmiyor.

---

### BLOKER #3: Strateji-Regime Uyumsuzluğu (TASARIM HATASI)

Stratejilerin hangi režimde çalıştığı ve pre_trade'in neye izin verdiği arasında **temel bir çelişki** var:

| Strateji        | Hangi Regime'de Sinyal Üretir | Pre-trade İzin Veriyor mu? | Sonuç          |
|----------------|------------------------------|---------------------------|---------------|
| RSI Reversion  | TREND_UP (RSI<30)            | ✅ TREND_UP'ta LONG izinli | ✅ Ama 0 coin TREND_UP |
| Momentum       | HEPSİ (Donchian breakout)    | ❌ TREND_UP dışında yasak  | ❌ Sinyal üretir ama reddedilir |
| VWAP           | RANGING (VWAP sapması)       | ❌ RANGING'de LONG yasak   | ❌ **TASARIM HATASI** |
| Edge Discovery | HEPSİ (pattern matching)     | ❌ TREND_UP dışında yasak  | ❌ Sinyal üretir ama reddedilir |

**Kritik çelişki:** VWAP stratejisi **yalnızca RANGING'de** sinyal üretecek şekilde tasarlanmış, ama pre_trade RANGING'de LONG'u engelliyor. Bu strateji **hiçbir koşulda trade açamaz.**

Edge Discovery 18 farklı pattern algılıyor, tüm režimlerde çalışabiliyor. Ama pre_trade hepsini reddediyor çünkü TREND_UP değil.

---

### BLOKER #4: SHORT Tamamen Kapalı

**Dosya:** `config.py` satır 104  
**Dosya:** `risk/pre_trade.py` satır 85

```python
ALLOW_SHORT = False  # SHORT KAPALI: %35 WR fail kanıtlanmış
```

**Etki:** 
- TREND_DOWN'da kar etme imkanı sıfır
- EXTREME_FEAR piyasasında aslında SHORT fırsatları en yüksek olduğu halde kullanamazsınız
- ARPAUSDT'nin edge'lerinin %80+'ı SHORT pattern'ler: `squeeze_breakout_down` (84.1% WR), `strong_momentum_down` (VET: 87.1% WR)
- Edge Discovery'nin keşfettiği en güçlü edge'ler SHORT pattern'ler — ama hepsi devre dışı

**Neden kapatıldı:** Backtest'te 57 SHORT trade, %35 WR, -$3,658. Ama bu sonuçlar **rejim filtresi olmadan** alınmış. Doğru filtrelerle SHORT performansı test edilmedi.

---

## BÖLÜM 3: REGIME TESPİTİNİN SORUNLARI

### 3.1 ADX Hesaplaması Yanlış

**Dosya:** `strategies/regime.py` satır 14-20

```python
def _calc_adx_approx(df, period=14):
    trend_move = abs(df["close"].iloc[-1] - df["close"].iloc[-period])
    return min(float(trend_move / price_range) * 100, 100.0)
```

Bu **gerçek ADX değil.** Gerçek ADX, DI+ ve DI- hesabı gerektirir. Bu sadece fiyat değişiminin range'e oranı. Sonuçlar yanlış:

- Gerçek ADX 25+ olan bir piyasada bu fonksiyon 7-12 arası değerler veriyor
- 9 coinin hiçbirinde ADX 25'i geçmiyor → TREND_UP tespiti neredeyse imkansız
- EMA fallback'i de çalışmıyor çünkü `price_change_20 > 0` koşulu çok geniş

### 3.2 Regime Tespiti Çok Katı

TREND_UP koşulları:
1. ADX > 25 **VE** 20-bar değişim > %2 → Şu an 0/9 coin karşılıyor
2. VEYA price > EMA20 > EMA50 **VE** price_change_20 > 0 → EMA dizilimine bağlı

Problem: Mevcut piyasada coinler %0-3 arasında hareket ediyor. Bu, RANGING tanımı. Ama RANGING'de trade yasak. Sistem **yatay piyasada tamamen kör.**

### 3.3 Volatility Ratio Yanıltıcı

```python
if vol_ratio > 1.5 and atr > price * 0.02:
    return "VOLATILE"
```

Bu iki koşul AND ile bağlı. Şu an volatilite düşük (vol_ratio 0.35-0.83) yani bu check tetiklenmiyor. Ama sentiment filtresi zaten VOLATILE döndürdüğü için bu check'in hiçbir anlamı yok.

---

## BÖLÜM 4: STRATEJİ DETAY ANALİZİ

### 4.1 RSI Reversion
- **Teknik olarak sağlam.** 1h timeframe kullanıyor, MACD confirmation var.
- **Problem:** Sadece TREND_UP'ta çalışıyor. 0 coin TREND_UP → sıfır sinyal.
- **RSI değerleri:** BTC=52.6, ETH=51.2, SOL=43.3, XRP=37.8 — hiçbiri <30 değil.
- Çift bloklama: hem TREND_UP yok, hem RSI oversold yok.

### 4.2 Momentum (Donchian Breakout)
- Donchian 20-period breakout. TREND_UP/DOWN'da 10-period (daha hassas).
- **BB expansion, volume, EMA** konfirmasyonları iyi.
- **Problem:** Pre-trade TREND_UP dışında LONG reddediyor. RANGING'de breakout sinyali üretse bile reddedilecek.

### 4.3 VWAP Reversion
- VWAP deviation + RSI confirmation.
- **FAT ALBUS HATA:** Yalnızca RANGING'de çalışıyor ama pre_trade RANGING'de LONG'u engelliyor.
- Bu strateji **tasarım gereği hiçbir zaman trade açamaz.**
- %25 oylama ağırlığı boşa gidiyor. Ölü koltuk.

### 4.4 Edge Discovery
- 18 farklı pattern algılıyor. Coin-spesifik ağırlıklar var.
- **En güçlü edge'ler SHORT pattern'ler** (ARPA squeeze_breakout_down %84.1, VET strong_momentum_down %87.1)
- SHORT kapalı → en güçlü keşifler kullanılamıyor.
- LONG pattern'ler de pre_trade tarafından engelleniyor (TREND_UP dışında).

---

## BÖLÜM 5: R:R VE EXIT STRATEJİSİ

### 5.1 Risk:Reward Oranı

```
SL = ATR × 1.5
TP = ATR × 2.0
R:R = 2.0 / 1.5 = 1.33:1
```

**Başabaş Win Rate:** 1 / (1 + 1.33) = **%43.0**

Bu mediocre bir R:R. Profesyonel sistemler minimum 2:1, ideal 3:1 hedefler. 1.33:1 ile %43 WR gerekiyor — ilk 6 trade'de %33 WR ile zaten zarar edilmişti.

### 5.2 Trailing Stop

```
Aktivasyon: %3.5 kârda
Mesafe: %1
```

%3.5'lik bir hareket 4h mum için makul ama agresif. Çoğu trade %1-2 hareket edip geri döner.

### 5.3 Minimum SL/TP Mesafesi

```python
sl_dist = max(sl_dist, signal.price * 0.015)  # min %1.5
tp_dist = max(tp_dist, signal.price * 0.030)  # min %3.0
```

Bu minimum değerler ATR bazlı hesabı override edebilir ve R:R'yi 2:1'e çıkarabilir. Ama bu sadece düşük ATR coinlerde etkili.

---

## BÖLÜM 6: OYLAMA SİSTEMİ

### 6.1 Eşit Ağırlıklar

```python
equal_weights = {
    "RSI": 0.25,
    "MOMENTUM": 0.25,
    "VWAP": 0.25,
    "EDGE_DISCOVERY": 0.25,
}
```

**Problem:** VWAP hiçbir zaman trade üretemez → %25 ağırlık daima NONE sinyali veriyor. Bu, diğer stratejilerin toplam güvenini %25 düşürüyor. 3 aktif strateji max %75 güven üretebilir.

### 6.2 Minimum Güven Eşiği

```python
STRATEGY_MIN_CONFIDENCE = 0.40
```

%40 tek bir streteji için makul. Ama combined score'da VWAP'ın NONE sinyali hesaba katılınca, diğer 3 strateji'nin yeterince yüksek güven üretmesi gerekiyor.

### 6.3 Çatışma Tespiti

İki strateji >%55 güvenle zıt yönde sinyal verirse → NONE. Bu mantıklı bir güvenlik mekanizması.

### 6.4 config.py'de Tanımlı Ama Kullanılmayan REGIME_WEIGHTS

```python
REGIME_WEIGHTS = {
    "TREND_UP":   {"RSI": 0.2, "MOMENTUM": 0.6, "VWAP": 0.2},
    "TREND_DOWN": {"RSI": 0.2, "MOMENTUM": 0.6, "VWAP": 0.2},
    ...
}
```

Bu ağırlıklar config'de var ama orchestrator `equal_weights` kullanıyor. **ÖLÜ KOD** — dikkate alınmıyor.

---

## BÖLÜM 7: VERİ KATMANI

### 7.1 Candle Manager
- Teknik olarak sağlam. Binance REST API'den tarihsel veri çekiyor, tick aggregation yapıyor.
- 100 mum tarihçe yüklüyor (yeterli).
- Debug logging var (her %1 tick'te log).

### 7.2 Sentiment API
- `alternative.me` Fear & Greed API. 5 dakika cache.
- API hata durumunda cache veya varsayılan 50 döndürüyor.
- **Problem:** `should_block_long()` threshold'u 10 (çok düşük), ama `detect_regime()` 20 kullanıyor. İnkonsistans.

### 7.3 Funding Rate
- Binance Funding Rate API mevcut ama **hiçbir yerde kullanılmıyor.** Ölü kod.

---

## BÖLÜM 8: OLUMLU YÖNLER

Adil olmak gerekirse, sistem bazı şeyleri doğru yapıyor:

1. **Teknik altyapı sağlam:** WebSocket stabil, candle aggregation doğru, DB persistence çalışıyor.
2. **Risk yönetimi mantığı var:** Günlük limit, pozisyon boyutu, notional cap.
3. **MFE/MAE tracking:** Profesyonel düzeyde trade analiz altyapısı.
4. **Slippage simülasyonu:** Paper trade'de %0.15 slippage — gerçekçi.
5. **Komizyonlar hesaplanıyor:** Entry ve exit'te %0.1 komisyon.
6. **Trade Journal:** Detaylı kayıt tutma.
7. **Telegram entegrasyonu:** 15 dakikada health report.
8. **Adaptive weights:** Performansa göre ağırlık ayarlama altyapısı var (kullanılmıyor ama altyapı hazır).

---

## BÖLÜM 9: SORUNLARIN ÖNCELİK SIRASI

| # | Sorun | Etki | Ciddiyet |
|---|-------|------|---------|
| 1 | Sentiment < 20 → VOLATILE → %100 blok | 20 gündür sıfır trade | 🔴 KRİTİK |
| 2 | LONG sadece TREND_UP (0/26 coin TREND_UP) | Sentiment olmasa bile sıfır trade | 🔴 KRİTİK |
| 3 | VWAP RANGING'de çalışır ama RANGING'de LONG yasak | Strateji asla çalışamaz | 🔴 KRİTİK |
| 4 | ADX hesabı yanlış (gerçek ADX değil) | TREND_UP tespiti çok nadir | 🟠 YÜKSEK |
| 5 | SHORT tamamen kapalı | En güçlü edge'ler kullanılamıyor | 🟠 YÜKSEK |
| 6 | R:R = 1.33:1 (mediocre) | %43 WR breakeven — yetersiz | 🟡 ORTA |
| 7 | VWAP'ın %25 ağırlığı boşa gidiyor | Combined confidence %25 düşük | 🟡 ORTA |
| 8 | REGIME_WEIGHTS kullanılmıyor (ölü config) | Regime'a göre ağırlık yok | 🟡 ORTA |
| 9 | Funding Rate kodu kullanılmıyor | Ek veri kaynağı israf | 🟢 DÜŞÜK |
| 10 | Gece filtresi (00-06 UTC) | Günün %25'i trade yok | 🟢 DÜŞÜK |

---

## BÖLÜM 10: TEMEL TEŞHİS

### Neden 20 gündür sıfır trade?

**Doğrudan Neden:** Fear & Greed < 20 → VOLATILE → pre_trade hepsini reddediyor.

**Yapısal Neden:** Sentiment filtresi olmasaydı bile sıfır trade olurdu. Çünkü:
- 0/26 coin TREND_UP durumunda
- Pre_trade LONG'u sadece TREND_UP'ta izin veriyor
- VWAP stratejisi RANGING'de çalışır ama RANGING'de trade yasak
- Edge Discovery'nin en güçlü pattern'leri SHORT — ama SHORT kapalı

### Gerçek Sorun Nedir?

**Bu sistem yalnızca çok spesifik bir piyasa koşulunda çalışabilir:**

```
Sentiment > 20 (EXTREME_FEAR değil)
  + En az 1 coin'de ADX > 25 VE 20-bar değişim > %2 (TREND_UP)
  + O coin'de RSI < 30 VEYA Donchian breakout VEYA Edge pattern
  + Saat 06:00-23:59 UTC
  + Korele pair'de pozisyon yok
```

Bu koşullar, ayı piyasasında / korku ortamında **neredeyse hiç oluşmuyor.** Sistem tasarım gereği **sadece boğa piyasasında** çalışabilir.

---

## BÖLÜM 11: ÖNERİLER (Yapılacak Değişiklikler)

### Acil (Sistemin çalışması için minimum gerekli):

#### Öneri 1: Sentiment Filtresini Kademeli Yap
Mevcut: binary on/off (< 20 = blok)  
Önerilen: Kademeli risk azaltma

```
fg < 10  → Pozisyon boyutu %25'e düşür, sadece Top 3 edge coin
fg 10-20 → Pozisyon boyutu %50'ye düşür
fg 20-40 → Normal pozisyon, dikkatli
fg > 40  → Tam pozisyon
```

#### Öneri 2: RANGING'de LONG İzin Ver
Mevcut: LONG sadece TREND_UP  
Önerilen: LONG TREND_UP'ta ve RANGING'de izinli (RANGING'de %50 pozisyon boyutu)

```python
if action == "LONG" and regime == "TREND_DOWN":
    return reject  # Sadece TREND_DOWN'da engelle
```

#### Öneri 3: VWAP Stratejisi Düzelt
VWAP RANGING'de sinyal üretiyor → pre_trade RANGING'de izin vermeli (Öneri 2 ile birlikte)

### Yüksek Öncelik:

#### Öneri 4: ADX Hesabını Düzelt
Gerçek ADX (Wilder's) veya alternatif trend göstergesi kullan. Mevcut approximation çok zayıf.

#### Öneri 5: SHORT'u Koşullu Aç
TREND_DOWN režiminde, edge'i kanıtlanmış pattern'lerle SHORT'a izin ver. En azından:
- VET strong_momentum_down (%87.1 WR)
- ARPA squeeze_breakout_down (%84.1 WR)

#### Öneri 6: R:R'yi İyileştir
SL = 1.5×ATR, TP = 3.0×ATR → R:R = 2:1 → Breakeven WR = %33

### Orta Öncelik:

#### Öneri 7: Regime-Based Ağırlıklar Kullan
`REGIME_WEIGHTS` zaten config'de tanımlı. Orchestrator'da `equal_weights` yerine bunları kullan.

#### Öneri 8: VWAP Yerine Alternatif
VWAP çalışamıyorsa, 4. strateji olarak başka bir şey koy (örn: Volume Profile, Order Flow).

#### Öneri 9: Funding Rate Kullan
`FundingRateSentiment` kodu var ama kullanılmıyor. Funding rate sentiment'ten daha güvenilir bir gösterge.

---

## BÖLÜM 12: SEÇENEKLERİNİZ

### Seçenek A: Minimum Düzeltme (2-3 saat)
1. Sentiment filtresini kademeli yap (Öneri 1)
2. RANGING'de LONG izin ver (Öneri 2)
3. 7 gün daha paper trade

**Beklenen sonuç:** Trade açılmaya başlar ama ayı piyasasında kârlılık garanti değil.

### Seçenek B: Kapsamlı Revizyon (1-2 gün)
1. Tüm Acil + Yüksek Öncelik önerileri (1-6)
2. ADX düzeltmesi
3. Koşullu SHORT
4. R:R iyileştirme
5. 14 gün paper trade

**Beklenen sonuç:** Sistem her piyasa koşulunda trade üretebilir. Kârlılık test edilmeli.

### Seçenek C: Projeyi Kapat
Eğer temelden yeniden yazmak istemiyorsanız, mevcut sistem ayı piyasasında çalışamaz. Boğa piyasası başlayana kadar beklenmeli veya tamamen farklı bir mimari (örn: mean reversion only, veya market neutral) ile yeniden başlanmalı.

---

## BÖLÜM 13: SONUÇ

War Machine'in **altyapısı sağlam** ama **karar mekanizması kırık.** 

20 gün boyunca sıfır trade olmasının sebebi tek bir bug değil — **katmanlı tasarım hatalarının birleşimi:** sentiment filtresi, TREND_UP zorunluluğu, VWAP çelişkisi, SHORT yasağı ve yanlış ADX hesabı.

Her biri tek başına ciddi bir sorun. Hepsi bir arada = **tamamen felç olmuş bir sistem.**

Sistem boğa piyasasında, sentiment > 40 olduğunda, birkaç coin TREND_UP'a girdiğinde çalışabilir. Ama o koşullar olmadan — ki şu an yok — bu sistem bir trade bile açamaz.

**Karar sizin.**

---

*Rapor: War Machine Forensic Audit v1.0*  
*Analiz edilen dosyalar: config.py, orchestrator.py, regime.py, pre_trade.py, stop_manager.py, voting.py, momentum.py, rsi_reversion.py, vwap_reversion.py, edge_discovery.py, sentiment.py, candle_manager.py, signal.py, state.py, paper.py, position_sizer.py*
