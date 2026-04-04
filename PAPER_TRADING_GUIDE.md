# PAPER TRADING BAŞLATMA KILAVUZU
## War Machine v3 - 7 Günlük Deneme

**Tarih:** 2026-04-03  
**Süre:** 7 gün (Pazartesi → Pazar)  
**Koinler:** ARPAUSDT, SOLUSDT, XRPUSDT  
**Koruma:** Likidation İğnesi Detection aktif  
**Risk:** 0% - HEPSI SANAL IŞLEM (paper trading)

---

## ✅ ÖN KONTROL (TAMAMLANDI)

```
✅ TEST 1: TELEGRAM BAĞLANTISI              ✅ GEÇTI
✅ TEST 2: TOP 3 COIN KONFIGÜRASYONU         ✅ GEÇTI  
✅ TEST 3: LIKIDATION ALERT KONFIGÜRASYONU   ✅ GEÇTI
✅ TEST 4: PAPER TRADING MODE                ✅ GEÇTI
✅ TEST 5: EDGE DISCOVERY METODLARI          ✅ GEÇTI
✅ TEST 6: TELEGRAM LIKIDATION ALERT         ✅ GEÇTI
✅ TEST 7: TELEGRAM TOP 3 SIGNAL             ✅ GEÇTI
```

---

## 🚀 YER AYNI BAŞLATMA

### ADIM 1: Main.py'yi Başlat

```bash
cd C:\war_machine
python main.py
```

**Beklenen çıktı:**
```
═══════════════════════════════════════════
  🟢 WAR MACHINE STARTED
Symbols: 24
Balance: $10,000.00
Mode: PAPER

[ARPAUSDT] Veri çekiliyor... ✓
[SOLUSDT] Veri çekiliyor... ✓
[XRPUSDT] Veri çekiliyor... ✓
...

┌─ Orchestrator başlatıldı (async loop)
│  • Edge Discovery aktif
│  • Top 3 koinler monitored
│  • Likidation spike detection: ON
└─ Telegram sinyalleri aktif

➜ Beklemede... (4h candlelar için)
```

---

## 📊 PAPER TRADING İZLEME KONTROL LİSTESİ

### Günlük Izleme (Sabah + Öğle + Akşam)

**Sabah Kontrolü (08:00):**
- [ ] Telegram'da gece bildirimleri kontrol et
- [ ] ARPAUSDT, SOLUSDT, XRPUSDT güncel fiyatlarını not et
- [ ] Likidation alert'i geldi mi? (varsa risk seviyesini not et)

**Öğle Kontrolü (14:00):**
- [ ] Açık sinyaller ve kapalı işlemler
- [ ] Win rate nereye?
- [ ] Pattern'ler makinenin dediği gibi mi gidiyor?

**Akşam Kontrolü (20:00):**
- [ ] Günlük özet
- [ ] Performance raporu
- [ ] Likidation hareketleri

### Beklenen Sinyaller

**ARPAUSDT - low_volatility** (81.48% WR)
```
Trigger: Bollinger Band'ın ortasında, volatilite düşük
Expected: 24 saat içinde fiyat üste doğru
Telegram: "ARPAUSDT - low_volatility yakalandı (92% confidence)"
```

**SOLUSDT - ranging_bb_upper** (68.97% WR)
```
Trigger: BB üst bandında, range market
Expected: 4 saat içinde fiyat altında mean reversion
Telegram: "SOLUSDT - ranging_bb_upper tamamlandı"
```

**XRPUSDT - rsi_below_30** (66.67% WR)
```
Trigger: RSI < 30 (oversold)
Expected: 4 saat içinde bounce (recovery)
Telegram: "XRPUSDT - rsi_below_30 harekete hazır"
```

---

## ⚠️ LIKIDATION ALERT İZLEME

### Risk Seviyeleri

🟡 **LOW RISK** (<5% likidation mesafesi)
- Normale yakın, işlem devam edebilir
- Telegram: "LİKİDASYON İĞNESİ - LOW"

🟠 **MEDIUM RISK** (5-10% likidation mesafesi)
- Stop loss'u gözlemle, order book'ta basınç var
- Telegram: "LİKİDASYON İĞNESİ - MEDIUM"

🔴 **HIGH RISK** (2-5% likidation mesafesi)
- Stop loss yaklaştı, pozisyon boyutunu düşürmeyi düşün
- Telegram: "LİKİDASYON İĞNESİ - HIGH"

🚨 **CRITICAL** (<2% likidation mesafesi)
- Masif likidation olayı - acil exit önerilir
- Telegram: "LİKİDASYON İĞNESİ - CRITICAL ⛔"

---

## 📋 7 GÜNLÜK GÖZLEM KARNESİ

### Hafta Raporu Şablonu

**Gün 1 (Çarşamba 2026-04-03)**
```
Başlangıç Bakiye: $10,000
Açık Sinyaller: ___
Tamamlanan İşlem: ___
Win Rate: ___%
Net PnL: $___
Likidation Alert'leri: ___ tane (risk seviyeleri: ___)

NOTLAR:
- ARPAUSDT pattern'i...
- SOLUSDT davranışı...
- XRPUSDT gözlem...
- Likidation spike detayı...
```

**Gün 2-7:** Aynı format

---

## 🔍 KRİTİK SORULAR - GÜNLÜK CEVAPLAYACAĞINIZ

1. **Pattern Doğruluğu**
   - Makine "ARPAUSDT low_volatility yakalandı" dedi → Fiyat 24h'de yükseldi mi?
   - Eğer %80+ başarı görüyorsan, %81.48 WR'nin gerçek olduğu anlamına gelir

2. **Likidation Alert Kesinliği**
   - Likidation alert geldiğinde gerçekten volume spike mi var?
   - Order book'ta masif satış/alım mu?

3. **Top 3 Coin Diversifikasyonu**
   - 3 coin aynı yönde mi hareket ediyor?
   - Correlation'ları düşük mü (sağlıklı diversifikasyon)?

4. **Timing Kesinliği**
   - Pattern 4h fiyatla eşleşiyor mu, yoksa gecikme mi var?
   - 1h candle'da başlama mı, kapanışta mı başlıyor?

---

## 🛑 PAPER TRADING'E KAYDOLMA KOŞULLARı

### Eğer 7 Gün Sonra...

✅ **GO LIVE HAZIR** (3+ şartı sağlıyorsa):
- [ ] Toplam Win Rate ≥ 60% (backtest'teki %66% yakınında)
- [ ] Likidation alert'leri %85+  doğruydu
- [ ] Top 3 coin pattern'leri tutarlı (minimum sapma)
- [ ] Hiçbir "black swan" oluşmadı
- [ ] Telegram sisteminde hiç hata olmadı

🟡 **YAKIN BAND** (60% confidence):
- Biraz daha test gerekebilir (2-3 gün extra)
- Risk parametrelerini ince ayar yap

❌ **PAUSE & DEBUG** (<60% başarı):
- Backtest'le yayında uyuşmuyor
- Tekrar tarama yap (v3 rescanning)
- Parametre optimize et

---

## 📞 ACIL DURUM

**Sistem Çöküyor:**
```bash
# Kill old processes
pkill -f "python main.py"

# Restart clean
python main.py
```

**Telegram Hata:**
```python
# .env dosyasında kontrol et:
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Test edin:
python test_paper_trading_setup.py
```

**Database Sorun:**
```bash
# Cache sil
rm -rf data/war_machine.db

# Restart
python main.py
```

---

## 📈 BEKLENTİLER

### Orta Seviye Senaryo (Tip %) 
```
Başlama: 100 işlem sinyali
Tamamlanan: ~70 işlem (30% missed)
Win Rate: ~62% (vs. 66% backtest)
Likidation Alert doğruluğu: ~88%
```

### Pessimist Senaryo (Başarı <55%)
```
Ortak nedenler:
1. Market regime değişti (backtest'teki dönem farklı)
2. Likidite yok (low cap coin'lerde slippage)
3. Feed gecikmesi (Binance WebSocket lag)
4. Spread değişimi (4h frame'de yatay hareketler)

Çözüm: v3 Rescanning (latest 3000 candle'lar)
```

---

## ✨ BAŞARILI PAPER TRADING ÖZETİ

**Amaç:** 
Makinenin istatistiksel avantajını (edge) canlı pazarda doğrulamak.

**Başarı Tanımı:**
- [ ] ≥60% win rate (sabit)
- [ ] Likidation alert'leri ≥85% doğruluk
- [ ] Top 3 coin pattern'leri tutarlı
- [ ] Sistem %100 uptime (downtime yok)

**Sonra:**
7. gün sonu → Full Live Trading (başlangıçta 1% risk)

---

**Status:** 🟢 HER ŞEY HAZIR - BAŞLAT!
