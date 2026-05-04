# Nechh Robotics — Website Geliştirme Raporu
**Son Güncelleme:** 5 Mayıs 2026  
**Site:** https://nechh-robotics-website.vercel.app  
**GitHub:** github.com/nechh42/Nechh_Robotics_website (branch: main)  
**Hosting:** Vercel (Hobby Plan — ücretsiz)  
**Stack:** Statik HTML/CSS/JS + Vercel Serverless Functions

---

## Tamamlanan Adımlar

### Temel Altyapı (ADIM 1-10)
| Adım | Yapılan | Dosya(lar) |
|------|---------|------------|
| 1 | Risk banner (her sayfada üstte) | index.html, tüm sayfalar |
| 2 | Footer (Terms, Privacy, Risk Disclosure linkleri) | index.html |
| 3 | about.html — Ekip & sistem hakkında sayfası | about.html |
| 4 | legal/ klasörü — Terms, Privacy, Risk Disclosure, Refund Policy | legal/*.html |
| 5 | contact.html — İletişim formu (Formspree) | contact.html |
| 6 | Cookie banner (GDPR/KVKK uyumlu) | assets/cookie-banner.js |
| 7 | faq.html — Sıkça Sorulan Sorular | faq.html |
| 8 | blog.html — Blog ana sayfası (grid layout, 7 makale kartı) | blog.html |
| 9 | SEO meta tags — OG, Twitter Card, canonical | tüm HTML sayfalar |
| 10 | Schema.org structured data — Organization + WebSite markup | index.html |

### İçerik & Güven (ADIM 11-20)
| Adım | Yapılan | Dosya(lar) |
|------|---------|------------|
| 11 | sitemap.xml — Tüm sayfalar dahil | sitemap.xml |
| 12 | robots.txt | robots.txt |
| 13 | Trust badges bölümü (Secure, Real-Time, Transparent, Regulated) | index.html |
| 14 | Testimonials — 3 kullanıcı yorumu (placeholder) | index.html |
| 15 | Lead magnet — "Free Weekly Market Report" formu | index.html |
| 16 | Anti-scam uyarı kutusu | index.html |
| 17 | Performance Preview kartı (canlı veri: API → index.html) | index.html |
| 18 | performance.html — Canlı equity curve, trade tablosu | performance.html |
| 19 | pricing.html — Paketler ve fiyatlandırma | pricing.html |
| 20 | register.html — Kayıt formu | register.html |

### Blog Yazıları (ADIM 21)
7 adet tam blog yazısı alt sayfası oluşturuldu — `blog/` klasöründe:

| Dosya | Konu | Kategori |
|-------|------|----------|
| profit-factor-vs-win-rate.html | PF vs Win Rate karşılaştırması | Strategy Research |
| avoiding-lookahead-bias.html | Backtest'te look-ahead bias | Backtesting |
| ema-pullback-strategy.html | EMA Pullback — BTC PF=1.93, ETH PF=2.59, SOL PF=1.28 | Market Analysis |
| position-sizing-guide.html | 4 position sizing yöntemi | Risk Management |
| crypto-to-equities.html | Kripto'dan US stocks'a geçiş (Q3 2026) | Multi-Market |
| algo-signal-pipeline.html | 7-adımlı sinyal pipeline açıklaması | Technology |
| surviving-drawdowns.html | Drawdown'dan sağ çıkma — 5 kural | Risk Management |
| **market-structure.html** | **Market Structure — HH/HL, BOS, CHoCH** | **Education (YENİ)** |
| **volatility-regimes.html** | **Volatility Regimes — Low/Normal/High** | **Strategy (YENİ)** |
| **risk-management.html** | **5 Non-Negotiable Risk Rules** | **Education (YENİ)** |
| **multi-timeframe.html** | **Multi-Timeframe Confluence — 75% threshold** | **Strategy (YENİ)** |
| **sector-rotation.html** | **Sector Rotation & Risk-On/Risk-Off** | **Macro (YENİ)** |
| **central-bank-alerts.html** | **Central Bank Policy — Fed/ECB/CBRT response** | **Macro (YENİ)** |

**Toplam:** 13 blog yazısı (7 orijinal + 6 yeni eğitim)

### Hızlı Düzeltmeler (5 Mayıs 2026)
- `about.html` — Bozuk emoji karakterleri düzeltildi (📊 🤖 🛡️ ⚖️ 🔒 🌍 📈 💱 🇹🇷 🇨🇳 𝕏 ✈️ ©)
- `blog.html` — 6 yeni makale kartı eklendi
- `sitemap.xml` — 6 yeni blog URL'si eklendi

### Analitik & Takip (ADIM 22)
- **GA4 Measurement ID:** `G-439H3JBHZR` — 10 HTML dosyasına inject edildi
- **GA4 Events** (`assets/analytics-events.js`): subscribe_click, lead_magnet_submit, contact_form_submit, faq_open, blog_read_50pct, social_click, cookie_accept, cookie_decline

### Canlı Chat (ADIM 27)
- **Tawk.to** entegrasyonu aktif
- Property ID: `68ecb86033a03a194942cfa4`
- Widget ID: `1j7eb0f2h`
- Dosya: `assets/chatbot.js`

### PWA (ADIM 29)
- `manifest.json` — PWA manifest (standalone display, theme: #2563eb)
- `sw.js` — Service Worker (network-first, cache fallback)
- Gerekli ama eksik: `assets/icon-192.png` ve `assets/icon-512.png` (192×192, 512×512 px PNG oluşturulmalı)

### API Docs (ADIM 31)
- `api-docs.html` — Tam REST API dokümantasyonu
- Endpoints: GET /v1/signals, GET /v1/performance, GET /v1/assets
- Webhook events, error codes, authentication dökümü

### Email Otomasyonu (ADIM 33)
- **Resend API** entegrasyonu — `api/email/send.js`
- Welcome email template (HTML, branded, risk disclaimer dahil)
- Weekly report email template (sinyal tablosu, CTA)
- Form submit → Formspree (kayıt) + Resend (email) paralel çalışır
- **Env var:** `RESEND_API_KEY` — Vercel'e eklendi ✅

### Yasal Uyumluluk (Yeni — ADIM 36)
- **Multi-step Yasal Onay Sistemi** — `assets/js/legal-modal.js`
- 4 adımlı zorunlu onay: Yaş (18+) → Yasal Uyarı → Risk Açıklaması → Gizlilik
- Tüm onaylar `localStorage`'da saklanır, eksikse site tamamen bloklanır
- Sürekli yasal footer (Risk, Gizlilik, Koşullar linkleri + "Onayları Sıfırla")
- ESC ve arka plan tıklama engellenir
- Tüm 30 HTML sayfaya otomatik injekte edildi

### Admin Panel (ADIM 30 — Tamamlandı)
- `admin.html` — Dark tema, mobil uyumlu admin panel
- Login: `X-Admin-Secret` header ile API doğrulama
- İstatistikler: Toplam üye, aktif, ödeme bekleyen, süresi dolmuş, MRR
- Abone tablosu: email, Telegram, plan, durum, bitiş tarihi, uyarı, kayıt
- Aksiyonlar: Aktif et, +30 gün ekle, Uyar, Banla
- CSV export desteği
- 60 saniyede otomatik yenileme

### Üye Dashboard (ADIM 26 — Ön Yüz)
- `dashboard.html` — Sinyaller, geçmiş, ayarlar sekmeleri
- Aktif sinyaller kartı (LONG/SHORT badge)
- Trade history tablosu
- Bildirim ayarları (Email, Telegram, Browser)
- Abonelik durumu paneli
- Mobil uyumlu grid layout

### Affiliate Sistemi (ADIM 32 — Ön Yüz)
- `affiliate.html` — 3 kademe komisyon: Starter %20, Pro %25, Elite %30
- Referans linki oluşturma ve kopyalama
- Demo istatistikler: Clicks, Signups, Conversion, Earned
- Program kuralları (self-referral yasak, $100 min payout, 90 gün cookie)
- `assets/js/affiliate-tracker.js` — URL `?ref=` parametresi takibi, localStorage kaydı

### A/B Test Sistemi (ADIM 34 — Tamamlandı)
- `assets/js/ab-test.js` — Deterministic bucket assignment (localStorage seed)
- Deney: Hero CTA metni
  - Control: "Get Access →" (50%)
  - Variant A: "Start Free Trial →" (25%)
  - Variant B: "Join Now →" (25%)
- GA4 `ab_exposure` eventi ile otomatik raporlama

### Gerçek Zamanlı Bildirimler (ADIM 35 — Ön Yüz)
- `assets/js/realtime-notifications.js` — 30 saniyede bir `trades.json` poll
- Yeni sinyal algılandığında slide-in toast bildirim (LONG=yeşil, SHORT=kırmızı)
- Browser push notification desteği (isteğe bağlı, kullanıcı onaylı)
- GA4 `signal_notification` event tracking
- Toast'tan tıklama → dashboard.html yönlendirmesi

---

## Aktif Servisler & API'lar

| Servis | Kullanım | Durum |
|--------|----------|-------|
| Vercel | Hosting + Serverless Functions | ✅ Aktif (Hobby Plan) |
| GitHub | Kod deposu + CI/CD | ✅ Aktif |
| GA4 | Kullanıcı analitik takibi | ✅ Aktif (G-439H3JBHZR) |
| Formspree | Form submit → email | ✅ Aktif (xwkgjdyz) |
| Resend | Transactional email | ✅ Aktif (API key eklendi) |
| Tawk.to | Canlı chat widget | ✅ Aktif |
| Supabase | Database (abone listesi) | ⏳ Hazır (Stripe bekliyor) |

---

## Önemli Env Variables (Vercel Dashboard)

| Key | Açıklama | Durum |
|-----|----------|-------|
| `RESEND_API_KEY` | Email gönderimi | ✅ Eklendi |
| `SUPABASE_URL` | Database URL | ⏳ Stripe aktif olunca |
| `SUPABASE_SERVICE_KEY` | Admin DB yetkisi | ⏳ Stripe aktif olunca |
| `TELEGRAM_BOT_TOKEN` | Aboneyi gruba ekle | ⏳ Stripe aktif olunca |
| `TELEGRAM_ADMIN_CHAT_ID` | Sana bildirim | ⏳ İsteğe bağlı |
| `TELEGRAM_GROUP_ID` | Sinyal grubu | ⏳ Stripe aktif olunca |
| `CRON_SECRET` | Cron job güvenliği | ⏳ İsteğe bağlı |

---

## Bekleyen / Atlanmış Adımlar

| Adım | İçerik | Neden Bekliyor |
|------|--------|----------------|
| ADIM 25 | Stripe Checkout | Türkiye'de Stripe çalışmıyor — alternatif: Paddle, LemonSqueezy, kripto ödeme |
| ADIM 28 | i18n (TR/EN) | Next.js gerektirir — şimdilik statik HTML |
| ADIM 35 (Backend) | WebSocket/SSE gerçek zamanlı | Vercel Hobby Plan WebSocket desteklemiyor — polling ile çözüldü |

---

## Dosya Yapısı (Önemli Dosyalar)

```
website_repo/
├── index.html              ← Ana sayfa
├── about.html              ← Hakkında
├── performance.html        ← Canlı trade istatistikleri
├── pricing.html            ← Fiyatlandırma
├── contact.html            ← İletişim
├── faq.html                ← SSS
├── blog.html               ← Blog ana sayfası
├── api-docs.html           ← API dokümantasyonu
├── trades.json             ← War Machine trade verisi (canlı güncellenir)
├── manifest.json           ← PWA manifest
├── sw.js                   ← Service Worker
├── sitemap.xml             ← SEO sitemap
├── robots.txt              ← SEO robots
├── vercel.json             ← Vercel config + routes + cron
├── assets/
│   ├── cookie-banner.js    ← GDPR cookie banner
│   ├── analytics-events.js ← GA4 custom events
│   └── chatbot.js          ← Tawk.to widget (aktif)
├── api/
│   ├── nechh-data.js       ← Ana veri API (trades.json + website_data.json okur)
│   ├── register.js         ← Kayıt endpoint
│   ├── email/
│   │   └── send.js         ← Resend email API (welcome + weekly_report)
│   ├── admin/
│   │   └── subscribers.js  ← Admin abone yönetimi
│   ├── telegram/
│   │   └── add-user.js     ← Telegram grup ekle
│   └── cron/
│       └── daily-check.js  ← Günlük otomatik kontrol (09:00 UTC)
├── blog/
│   ├── profit-factor-vs-win-rate.html
│   ├── avoiding-lookahead-bias.html
│   ├── ema-pullback-strategy.html
│   ├── position-sizing-guide.html
│   ├── crypto-to-equities.html
│   ├── algo-signal-pipeline.html
│   ├── surviving-drawdowns.html
│   ├── market-structure.html       ← YENİ (Education)
│   ├── volatility-regimes.html     ← YENİ (Strategy)
│   ├── risk-management.html        ← YENİ (Education)
│   ├── multi-timeframe.html        ← YENİ (Strategy)
│   ├── sector-rotation.html        ← YENİ (Macro)
│   └── central-bank-alerts.html   ← YENİ (Macro)
├── dashboard.html          ← Üye dashboard (sinyal + geçmiş + ayarlar)
├── affiliate.html          ← Affiliate programı (3 kademe komisyon)
├── admin.html              ← Admin panel (abone yönetimi + CSV export)
└── assets/js/
    ├── legal-modal.js        ← Multi-step yasal onay (4 adım)
    ├── ab-test.js            ← A/B test sistemi
    ├── affiliate-tracker.js  ← Referans kodu takibi
    └── realtime-notifications.js ← Yeni sinyal toast bildirimleri
```

---

## emotice.com

- **Durum:** 301 Redirect → `https://nechh-robotics-website.vercel.app`
- **Platform:** Hostinger (Yönlendirmeler bölümünden ayarlandı)
- **Gelecek Plan:** Nechh'te 50-100 aktif kullanıcı oluşunca trader sosyal ağına dönüştürülecek

---

## Ödeme Alternatifleri (Stripe yerine)

Türkiye'den çalışan seçenekler:
- **Paddle** — Türkiye destekli, Merchant of Record (vergi halleder)
- **LemonSqueezy** — Paddle alternatifi, daha basit kurulum
- **Kripto ödeme** — USDT/USDC ile direkt (Binance Pay, NOWPayments)
- **Papara / IBAN** — Manuel kontrol (küçük ölçek için)

---

*Bu rapor her büyük geliştirmeden sonra güncellenir.*
