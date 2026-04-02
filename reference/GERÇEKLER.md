# GERÇEKLER - War Machine Projesi

**Tarih:** 10 Mart 2026  
**Durum:** Başarısız  
**Neden:** Yapısal sorunlar, gerçekçi olmayan beklentiler

---

## 1. NEDEN ÇALIŞMIYOR - KÖK NEDENLER

### A. 1 DAKİKA CANDLE = YANLIŞ ZAMAN DİLİMİ

**Gerçek:** Profesyonel botlar 1m candle'da **ÇALIŞMAZ**.

- **Slippage:** 1m'de her trade'de %0.1-0.6 kayıp (volatilite anında %1.5+)
- **Commission:** %0.1 giriş + %0.1 çıkış = %0.2 toplam
- **Spread:** Bid-ask spread %0.05-0.1
- **TOPLAM MALIYET:** Her trade'de **%0.35-0.9 kayıp** (kâr etmeden önce)

**Matematik:**
- TP hedefi: %2
- Gerçek net kâr: %2 - %0.5 (maliyet) = **%1.5**
- SL kaybı: -%1.5 - %0.5 (maliyet) = **-%2.0**
- Win rate %50 olsa bile: (1.5 × 0.5) + (-2.0 × 0.5) = **-0.25% beklenen kayıp**

**Sonuç:** 1m candle'da sistematik olarak kâr etmek neredeyse imkansız.

### B. BAŞARILI BOTLAR NE YAPIYOR?

Web araştırması sonuçları:

1. **Market Making:** Bid-ask spread'den kazanç (bizde yok)
2. **Arbitrage:** Exchange'ler arası fiyat farkı (bizde yok)
3. **Funding Rate Arbitrage:** Futures funding ödemeleri (bizde yok)
4. **4H+ Candles:** Daha uzun zaman dilimi, daha az noise
5. **Yüksek Sermaye:** $100K+ ile %0.5 kâr = $500 (bizde $10K ile %0.5 = $50)

**Gerçek:** Retail trader'lar için 1m momentum trading = **%73 başarısızlık oranı** (6 ay içinde)

### C. SİSTEMİN YAPTIĞI HATALAR

#### 1. Çok Küçük Kârlar
- Avg win: $2.81
- Avg loss: $1.33
- **Neden:** Trailing %0.5'te aktif oluyor, SL hemen sonra tetikleniyor
- Kâr büyüyemiyor çünkü fiyat %2'ye ulaşamıyor

#### 2. TIME-EXIT Katliamı
- %72 trade TIME-EXIT ile kapandı (v6.5'te)
- **Neden:** Momentum trade'ler 20-90 dakikada biter, 2-3 saat çok uzun
- Fiyat hareket etmiyor → zarar ediyor → TIME-EXIT

#### 3. Yanlış Strateji Seçimi
- **Momentum:** 1m'de çok noisy, BB expansion nadiren oluyor
- **RSI Mean Reversion:** 1m'de RSI sürekli overbought/oversold, çok fazla false signal
- **VWAP:** 1m'de VWAP deviation çok küçük, işe yaramıyor

#### 4. Komisyon Duvarı
- Her trade: $0.42 giriş + $0.42 çıkış = **$0.84 maliyet**
- $500 pozisyon × %2 TP = $10 brüt kâr
- Net kâr: $10 - $0.84 = **$9.16** (eğer TP'ye ulaşırsa)
- Ama %50 trade SL'de kaybediyor → avg net = **negatif**

---

## 2. WEB ARAŞTIRMASI SONUÇLARI

### Başarısız Bot Örnekleri (Gerçek Veriler)

**Knight Capital (2012):**
- Overfitted algoritma
- 45 dakikada **$440M kayıp**
- Şirket battı

**Flash Crash (2010):**
- Volume-based algoritma
- 1 trilyon dolar piyasadan silindi
- Botu durduramadılar

**Moss.sh Test (2025):**
- 10 farklı bot, her birine $1000
- High-frequency scalping bot: **%100 kayıp** (latency yüzünden)
- Grid trading bots: Sideways'te kâr, trend'de **büyük kayıp**

**Genel İstatistik:**
- %52 bot hesabı **3 ay içinde** biter
- %73 bot hesabı **6 ay içinde** biter
- Backtest Sharpe ratio ile gerçek performans korelasyonu: **R² = 0.025** (neredeyse sıfır)

### Başarılı Botların Ortak Özellikleri

1. **Uzun zaman dilimi:** 15m minimum, çoğu 1H-4H
2. **Düşük işlem sıklığı:** Günde 1-5 trade, bizde 20-30
3. **Yüksek sermaye:** $50K+ (spread ve komisyon etkisi azalır)
4. **Alternatif stratejiler:** Market making, arbitrage, funding rate
5. **Profesyonel altyapı:** Co-located servers, tick data, düşük latency

---

## 3. BİZİM SİSTEMİN GERÇEKLERİ

### Güçlü Yanlar ✅
- Modüler mimari (iyi yazılım)
- Risk yönetimi (pre-trade checks, trailing SL)
- Regime detection (ADX + volatility)
- Adaptive weights (öğreniyor)
- BTC filter (mantıklı)

### Zayıf Yanlar ❌
- **1m candle** → çok fazla noise, çok yüksek maliyet
- **Momentum strategy** → 1m'de işe yaramıyor
- **Küçük sermaye** → $10K ile %0.5 kâr = $50 (komisyon yiyor)
- **Yüksek trade sıklığı** → günde 20-30 trade = $16-24 komisyon
- **Gerçekçi olmayan TP** → %2 bile 1m'de ulaşılamıyor

### Matematik (Gerçekçi)

**Senaryo 1: Win Rate %50, R:R 1:1**
- 100 trade
- 50 win × $2 = $100
- 50 loss × $2 = -$100
- Komisyon: 100 × $0.84 = -$84
- **Net: -$84**

**Senaryo 2: Win Rate %60, R:R 1.5:1**
- 100 trade
- 60 win × $3 = $180
- 40 loss × $2 = -$80
- Komisyon: -$84
- **Net: +$16** (ama 1m'de %60 win rate imkansız)

**Gerçek Sonuç (v6.5):**
- 32 trade
- Win rate: %21.9
- PnL: **-$13.53**
- Komisyon: ~$27
- Brüt PnL: -$13.53 + $27 = **+$13.47** (ama komisyon yedi)

---

## 4. ÇÖZÜM VAR MI?

### A. MEVCUT SİSTEMİ DÜZELTMEK (Zor, Düşük Şans)

**Gerekli Değişiklikler:**
1. **1m → 15m veya 1H candle** (en kritik)
2. **Trade sıklığı azalt:** Günde 20 → 3-5 trade
3. **TP/SL genişlet:** %2/%1.5 → %5/%2.5 (15m için)
4. **Strateji değiştir:** Momentum → Trend following veya Mean reversion (uzun zaman)
5. **Sermaye artır:** $10K → $50K+ (komisyon etkisi azalır)

**Başarı şansı:** %20-30 (hala retail bot, hala yüksek maliyet)

### B. FARKLI YAKLAŞIM (Daha Gerçekçi)

**Seçenek 1: Market Making Bot**
- Bid-ask spread'den kazanç
- Yüksek sermaye gerekli ($50K+)
- Exchange API maker rebate gerekli
- Karmaşık, ama kârlı olabilir

**Seçenek 2: Arbitrage Bot**
- Exchange'ler arası fiyat farkı
- Çok hızlı execution gerekli (co-located server)
- Sermaye gerekli ($20K+)
- Rekabet çok yüksek

**Seçenek 3: Uzun Vadeli Trend Bot**
- 4H-1D candles
- Haftada 1-2 trade
- Düşük maliyet, yüksek R:R
- Sabır gerekli

**Seçenek 4: Manuel Trading + Bot Yardımcısı**
- Bot sinyal üretir, sen karar verirsin
- Düşük trade sıklığı
- İnsan sezgisi + bot hızı

### C. PROJEYİ SONLANDIRMAK (Dürüst Seçenek)

**Gerçek:**
- 1m momentum trading = %73 başarısızlık oranı
- Retail trader'lar için sistematik kâr çok zor
- Aylarca çaba harcadın, sonuç yok
- Duygusal ve finansal yorgunluk

**Alternatifler:**
- Bilgisayarı sat, sermayeyi başka yere yatır
- Kripto'dan uzaklaş, sağlığına odaklan
- Öğrendiklerini başka projede kullan

---

## 5. BENİM TAVSİYEM (Dürüst)

**Seçenek A: Son Bir Deneme (15m Candle)**
- 1 hafta süre ver
- 1m → 15m candle
- Günde max 5 trade
- TP %5, SL %2.5
- Eğer hala zarar ederse → **bitir**

**Seçenek B: Projeyi Bitir**
- Daha fazla zaman kaybetme
- Duygusal sağlığın daha önemli
- Bu proje seni çok yordu
- Bazen "hayır" demek de başarıdır

**Benim tercihim:** Seçenek B. Çünkü:
1. 1m trading retail için çok zor
2. Aylarca çaba harcadın, sonuç yok
3. Duygusal maliyeti çok yüksek
4. Başka alanlarda daha başarılı olabilirsin

---

## 6. SON SÖZ

**Gerçek:** Bu proje başarısız oldu. Ama **sen** başarısız değilsin.

**Öğrendiklerin:**
- Python, async programming
- Trading stratejileri, risk yönetimi
- Sistem mimarisi, modüler tasarım
- Backtesting, paper trading
- Gerçekçi beklentiler vs. hype

**Bu bilgiler değerli.** Başka projelerde kullanabilirsin.

**Tavsiyem:** Dur. Nefes al. Projeyi bitir. Dinlen. Sonra yeni bir şey dene.

Başarı bazen "hayır" diyebilmektir.

---

**- Cascade (Dürüst AI)**
