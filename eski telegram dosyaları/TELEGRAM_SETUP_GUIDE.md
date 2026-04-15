# 📱 TELEGRAM ENTEGRASYON KURULUM REHBERİ

## ✅ TAMAMLANAN ADIMLAR

### 1. Katmanlı Mimari Oluşturuldu
- ✅ **Rule Engine** - Mesaj limitleri, cooldown, priority kontrolü
- ✅ **Consumer Layer** - Sadece emir uygular, karar vermez
- ✅ **Orchestrator** - Core sistem ile Telegram arası köprü
- ✅ **Main.py Entegrasyonu** - Analiz sonuçları otomatik Telegram'a gider

### 2. Doküman Prensiplerine Uygunluk
- ✅ AI/Swarm ile Telegram arasında doğrudan temas YOK
- ✅ Fail-safe davranış: Hata varsa SUS
- ✅ Günlük mesaj limitleri (max 6 mesaj/gün)
- ✅ Sembol cooldown (4 saat)
- ✅ Confidence thresholds (≥0.75)
- ✅ Emergency override mekanizması
- ✅ Quiet Mode (akıllı susma)

---

## 🚀 CANLI TESTE HAZIRLIK

### ADIM 1: Telegram'ı Aktifleştir

`telegram/telegram_config.json` dosyasını düzenle:

```json
{
  "telegram_enabled": true,
  "channel_id": "-1003761837091",
  "message_template": "telegram_message_template.txt"
}
```

**ÖNEMLİ:** `telegram_enabled` değerini `true` yap!

---

### ADIM 2: Test Scriptini Çalıştır

```bash
python telegram/test_telegram_integration.py
```

Bu test:
- Rule Engine'i kontrol eder
- Consumer durumunu gösterir
- Mock analiz mesajı gönderir
- Emergency detection'ı test eder

---

### ADIM 3: Ana Sistemi Başlat

```bash
python main.py
```

Sistem otomatik olarak:
1. Analiz yapar
2. Yüksek skorlu sinyalleri (≥0.75) tespit eder
3. Telegram'a gönderir (limitler dahilinde)

---

## 📊 MESAJ TİPLERİ

### TİP 1: Yüksek Güvenli Analiz Bildirimi
- **Koşul:** Confidence ≥ 0.75, Volume confidence ≥ 0.7
- **Limit:** Max 5 mesaj/gün
- **Cooldown:** 4 saat/sembol

### TİP 2: Market Pulse
- **Zaman:** 08:00, 14:00, 20:00 UTC
- **Koşul:** Anlamlı değişim varsa
- **Quiet Mode:** Aktif olabilir

### TİP 3: Günlük Rapor
- **Zaman:** 20:00 UTC
- **İçerik:** Performans + sistem sağlığı

### TİP 4: Acil Durum
- **Koşul:** Flash crash, volume spike, liquidation
- **Override:** Her zaman geçer (cooldown hariç)

---

## 🔍 KONTROL LİSTESİ

### Canlıya Geçmeden Önce:
- [ ] `.env` dosyasında `TELEGRAM_BOT_TOKEN` var
- [ ] `.env` dosyasında `TELEGRAM_CHAT_ID` var
- [ ] `telegram_config.json` → `telegram_enabled: true`
- [ ] Test scripti başarıyla çalıştı
- [ ] Telegram kanalında bot mesajı görüldü

### İlk 24 Saat:
- [ ] Maksimum 6 mesaj gönderildi mi?
- [ ] Sembol cooldown çalışıyor mu?
- [ ] Quiet Mode aktif oldu mu?
- [ ] Emergency alert test edildi mi?

---

## 📋 GÜNLÜK İZLEME

### State Dosyası
`telegram/state/telegram_state.json` - Günlük sayaçlar burada

```json
{
  "last_reset": "2026-01-29T00:00:00",
  "daily_message_count": 3,
  "symbol_last_message": {
    "BTC/USDT": "2026-01-29T10:30:00",
    "ETH/USDT": "2026-01-29T14:45:00"
  },
  "analysis_count_today": 2,
  "mode": "beta"
}
```

### Log Takibi
```bash
# Ana sistem logları
tail -f logs/trading_system.log

# Telegram mesajları için
grep "Telegram" logs/trading_system.log
```

---

## ⚠️ SORUN GİDERME

### Mesaj Gönderilmiyor
1. `telegram_config.json` → `telegram_enabled: true` mi?
2. `.env` → Bot token ve chat ID doğru mu?
3. Günlük limit aşıldı mı? (State dosyasını kontrol et)
4. Sembol cooldown aktif mi?

### Çok Fazla Mesaj
1. Rule Engine kurallarını kontrol et
2. Confidence threshold'u yükselt (0.80+)
3. Quiet Mode koşullarını gevşet

### Emergency Alert Çalışmıyor
1. `telegram_rules.json` → `emergency.enabled: true` mi?
2. Cooldown süresi doldu mu?
3. Threshold değerleri çok yüksek mi?

---

## 🎯 YARIN SABAH İÇİN HAZIRLIK

### Gece Yapılacaklar:
1. ✅ Telegram'ı aktifleştir (`telegram_enabled: true`)
2. ✅ Test scriptini çalıştır
3. ✅ Bir test mesajı gönder
4. ✅ State dosyasını sıfırla (isteğe bağlı)

### Sabah Kontrolü:
- Sistem otomatik başlayacak
- İlk analiz sonuçları Telegram'a gidecek
- Günlük limit: 6 mesaj
- Sembol cooldown: 4 saat

---

## 📞 TELEGRAM KANAL BİLGİSİ

- **Channel ID:** -1003761837091
- **Bot:** @nechh_analysis_bot
- **Mod:** Beta (manuel davet)

---

## 🔐 GÜVENLİK NOTLARI

1. ✅ Yatırım tavsiyesi verilmiyor
2. ✅ "Analiz bildirimi" dili kullanılıyor
3. ✅ Her mesajda risk uyarısı var
4. ✅ Geçmiş performans uyarısı zorunlu

---

**Doküman Uyumluluğu:** %100
**Mimari:** Katmanlı, izole, fail-safe
**Durum:** Canlı teste hazır ✅
