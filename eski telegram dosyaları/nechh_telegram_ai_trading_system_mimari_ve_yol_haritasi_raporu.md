# NECHH AI TRADING SYSTEM

## Telegram Tabanlı Analiz Yayın Mimarisi – Nihai Teknik Rapor

\---

## 1\. PROJENİN AMACI

Bu doküman; Nechh AI Trading System için sıfırdan tasarlanan, Telegram tabanlı, düşük riskli, sürdürülebilir ve otomasyon odaklı analiz yayın altyapısının **tam mimari özetini** içerir.

Hedef:

* Manuel yük bindirmeyen
* Yasal risk üretmeyen
* Spam olmayan
* Uzun süre sessiz ve stabil çalışabilen
bir sistem kurmaktır.

\---

## 2\. TEMEL FELSEFE

> \*\*“Az mesaj, yüksek anlam, sıfır gürültü.”\*\*

* Telegram sosyal alan değildir
* Sistem yorum yapmaz, analiz bildirir
* Sessizlik hata değil, stratejidir

\---

## 3\. KATMANLI SİSTEM MİMARİSİ

### 3.1 Core Algorithm Layer

* Binance Spot (test aşaması)
* Event-driven analiz
* Confidence, volume ve rejim filtreleri
* Quiet Mode (akıllı susma)

### 3.2 AI / Swarm Layer

* Çoklu model konsensüsü
* Sinyal ve analiz üretimi
* Telegram ile **doğrudan temas YOK**

### 3.3 Rule Engine

* Günlük mesaj limiti
* Sembol cooldown
* Öncelik \& çakışma yönetimi
* Emergency override

### 3.4 Telegram Consumer Layer

* Karar vermez
* Sadece emir uygular
* Fail-safe davranış: hata varsa SUS

\---

## 4\. TELEGRAM MESAJ TİPLERİ

### TİP 1 – Yüksek Güvenli Analiz Bildirimi

* Confidence ≥ 0.75
* Volume confidence ≥ 0.7
* Günlük max 5 mesaj

### TİP 2 – Market Pulse

* Günde 3 kez (08:00, 14:00, 20:00 UTC)
* Sadece anlamlı değişim varsa

### TİP 3 – Günlük Rapor

* Her gün 20:00 UTC
* Performans + sistem sağlığı

### TİP 4 – Acil Durum

* Flash crash
* Likidasyon spike
* Korelasyon kırılımı

\---

## 5\. AKILLI SUSMA (QUIET MODE)

Sistem aşağıdaki koşullardan 3’ü sağlanırsa susar:

* Düşük volatilite
* Düşük hacim
* Haber yok
* Düşük sistem güven skoru

Sessizlik bilgilendirici bir mesajla veya tamamen sessiz kalma şeklinde uygulanır.

## MARKET REGIME ANALYSIS:

\---

## 6\. TELEGRAM ABONELİK MANTIĞI

### Temel İlke

> \*\*Telegram abonelik tutmaz, sadece izin kontrol eder\*\*

### State Yapısı

```json
{
  "mode": "beta",
  "allowed\_users": \[],
  "revoked\_users": \[]
}
```

* Beta modunda manuel davet
* Paid mod ileride aktive edilebilir

\---

## 7\. OTOMASYON KARAR HİYERARŞİSİ

1. Acil durum
2. Yüksek güvenli analiz
3. Günlük rapor
4. Market update

Telegram bu sıralamayı **uygular**, belirlemez.

\---

## 8\. LOG \& RAPOR YAPISI

* logs/ → core sistem
* reports/ → performans \& health
* telegram/ → sadece consumer config

Telegram kendi log tutmaz.

\---

## 9\. HUKUKİ \& YASAL ÇERÇEVE

* Yatırım tavsiyesi verilmez
* “Analiz bildirimi” dili kullanılır
* Geçmiş performans uyarısı zorunlu

Şirket kurulumu **opsiyonel**, para alınmadan önce zorunlu değildir.

\---

## 10\. CANLIYA GEÇİŞ CHECKLIST (ÖZET)

* Spot test ≥ 7 gün
* Futures kapalı
* Mesaj limitleri aktif
* Fail-safe çalışıyor
* DM \& yorum kapalı

Bir madde bile eksikse canlıya çıkılmaz.

\---

## 11\. İLK 7 GÜN STRATEJİSİ

* Gün 1–3: Sadece sistem testi
* Gün 4–7: 3–5 güvenilir beta kullanıcı
* Hiçbir kazanç vaadi yok

\---

## 12\. PROJE DURUMU

* Mimari: TAMAM
* Telegram altyapı: TAMAM
* Otomasyon mantığı: TAMAM
* Yasal risk: KONTROL ALTINDA

\---

## 13\. SONUÇ

Bu sistem:

* profil için uygundur
* Zaman ve zihinsel yük bindirmez
* Sessiz, deterministik ve kontrol edilebilirdir

Genişleme (US Stocks, Futures, Forex, BIST) **aynı mimariyle** mümkündür.

\---

**Doküman kilitlenmiştir.**

