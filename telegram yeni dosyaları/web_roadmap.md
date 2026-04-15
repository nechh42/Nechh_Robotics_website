# 🌐 Nechh Robotics — Web Sitesi Yol Haritası

> Slogan: **"SYSTEM SPEAKS. NOT LUCK."** / **"SİSTEM KONUŞUR. ŞANS DEĞİL."**

---

## 📋 SAYFA LİSTESİ & ÖNCELİK SIRASI

### ✅ FAZ 1 — Kritik (Hemen Yapılacak)

---

### 1. ANA SAYFA (index / Hero)
**Amaç:** İlk izlenim. Ziyaretçi 5 saniyede ne olduğunu anlamalı.

**Bölümler:**
- **Hero Banner**
  - Başlık: "SYSTEM SPEAKS. NOT LUCK."
  - Alt başlık: "Algorithmic crypto trading signals — no gut feeling, no guessing."
  - CTA butonu: "Join Telegram →"
  - Arka plan: siyah + yeşil grafik animasyonu (mevcut site stili)

- **Canlı Sayaç Barı** (en önemli eksik!)
  - 📊 Toplam setup: `247`
  - ✅ Win rate: `%71`
  - 📅 Aktif gün: `63`
  - ⚙️ Sistem durumu: `🟢 LIVE`
  - *Not: Papertrade olduğunu küçük yazıyla belirt — dürüstlük güven verir*

- **Nasıl Çalışır — 3 Adım**
  1. Sistem koşulu tarar
  2. Setup kriterleri karşılanırsa pozisyon açılır
  3. TP/SL otomatik yönetilir — duygu yok

- **Son 5 Sinyal** (canlı feed — küçük kartlar)
  - BTCUSDT LONG ✅ +3.2%
  - ETHUSDT SHORT ✅ +1.8%
  - SOLUSDT LONG ❌ -0.9%

- **Telegram Kanalı CTA**
  - "Free channel → 3,000+ members" (hedef rakam, önce küçük başla)

---

### 2. PERFORMANS SAYFASI
**Amaç:** "Sistem konuşur" sloganının kanıtı. En önemli güven sayfası.

**Bölümler:**
- **Üst Banner**
  - "All results are from paper trading. Real capital deployment coming soon."
  - Tarih aralığı filtresi (son 7 gün / 30 gün / tümü)

- **Özet Kartları**
  - Toplam işlem | Win/Loss | Win Rate | Ortalama PnL | En iyi gün | En kötü gün

- **Trade Geçmişi Tablosu**
  | Tarih | Sembol | Yön | Giriş | Çıkış | PnL | Süre |
  |-------|--------|-----|-------|-------|-----|------|
  - JSON'dan otomatik çekilir, sayfa yenilenmeden güncellenir

- **Aylık PnL Grafiği** (bar chart)
- **Win/Loss Dağılımı** (pie chart)

*Teknik: Statik JSON dosyası → Vercel'de host et → JavaScript ile render*

---

### 3. HAKKINDA SAYFASI
**Amaç:** "Kim bu sistem, neden güveneyim?"

**İçerik:**
- **Sistemin Hikayesi** (kişisel değil, sistemin hikayesi)
  - "2 years of development. 63 days of live paper trading. Zero emotion."
- **Strateji Felsefesi** (detay vermeden)
  - Likidite analizi
  - Multi-timeframe doğrulama
  - Risk yönetimi (pozisyon başına maks. risk)
- **Neden Papertrade?** — şeffaf açıklama
- **Yol Haritası** (public roadmap — güven için)

---

### ⚡ FAZ 2 — Abonelik (Sistem hazır olunca)

---

### 4. ABONE OL SAYFASI
**Bölümler:**
- Plan karşılaştırma tablosu:

| Özellik | FREE | PRO | VIP |
|---------|------|-----|-----|
| Telegram kanalı | ✅ Public | ✅ Özel | ✅ Özel |
| Trade sinyalleri | Örnek | Tümü | Tümü |
| AI piyasa analizi | ❌ | ✅ Günlük | ✅ 3x/gün |
| Coin raporları | ❌ | ❌ | ✅ |
| Haftalık özet | ❌ | ✅ | ✅ |
| Fiyat | Ücretsiz | $X/ay | $Y/ay |

- Kripto ödeme butonu (NOWPayments)
- "Ödeme nasıl yapılır?" accordion SSS

---

### 5. BLOG / ANALİZ SAYFASI (Opsiyonel, Faz 3)
- AI'ın ürettiği haftalık analizler burada da yayınlanır
- SEO trafiği için
- "Bu analizlerin tamamını Telegram'da alın →" CTA

---

## 🛠️ TEKNİK DETAYLAR

### Stack (mevcut Vercel üzerinde)
```
/
├── index.html          ← Ana sayfa
├── performance.html    ← Performans
├── about.html          ← Hakkında
├── subscribe.html      ← Abone ol
├── data/
│   └── trades.json     ← Trade geçmişi (bot buraya yazar)
├── js/
│   ├── performance.js  ← Tablo + grafik
│   └── live-feed.js    ← Ana sayfadaki son sinyaller
└── css/
    └── style.css       ← Mevcut stil korunur
```

### trades.json Formatı
```json
{
  "updated_at": "2024-01-15T20:00:00Z",
  "stats": {
    "total": 247,
    "wins": 175,
    "losses": 72,
    "win_rate": 70.9,
    "avg_pnl": 1.8
  },
  "trades": [
    {
      "date": "2024-01-15",
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "entry": 67450,
      "exit": 69200,
      "pnl": 2.6,
      "duration_minutes": 380,
      "result": "TP"
    }
  ]
}
```

### Bot → Vercel Entegrasyonu
Mevcut Python botu, her trade kapandığında `trades.json` dosyasını günceller.
Vercel'e push için iki seçenek:
1. **GitHub Actions** — bot commit atar, Vercel otomatik deploy eder
2. **Vercel API** — bot direkt Vercel Storage'a yazar (daha temiz)

---

## 📅 YAPIM TAKVİMİ

| Hafta | Görev |
|-------|-------|
| Hafta 1 | Ana sayfa hero + sayaç barı + son sinyaller feed |
| Hafta 2 | Performans sayfası — tablo + grafikler |
| Hafta 3 | Hakkında sayfası |
| Hafta 4 | Abone ol sayfası + NOWPayments |
| Hafta 5 | trades.json bot entegrasyonu |
| Hafta 6 | Test + SEO + mobil uyum |

---

## ✍️ SONRAKİ ADIM

Önce `data/trades.json` şemasını kesinleştir → sonra `performance.html` sayfasını yazarız.
Bunu Vercel'e nasıl push ettiğini anlat (GitHub var mı?) — ona göre bot entegrasyonunu kodlarız.
