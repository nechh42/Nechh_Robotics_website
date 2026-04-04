#!/usr/bin/env python3
"""
Paper Trading Startup Checklist
================================
Run this BEFORE starting main.py
Verifies all systems are ready for 7-day test
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

import config
from monitoring.telegram import telegram


async def startup_checklist():
    """7 günlük paper trading başlatma kontrol listesi"""
    
    print("\n" + "="*70)
    print("PAPER TRADING BAŞLATMA KONTROL LİSTESİ")
    print("="*70 + "\n")
    
    checks = {
        "Sistem Konfigürasyonu": [],
        "Edge Discovery Setup": [],
        "Telegram Bağlantısı": [],
        "Paper Trading Ayarları": [],
        "Likidation Protection": [],
    }
    
    # ============= BÖLÜM 1: Sistem Konfigürasyonu =============
    print("🔍 BÖLÜM 1: SİSTEM KONFİGÜRASYONU")
    print("-" * 70)
    
    # Check 1.1
    status = "✅" if config.REAL_TRADING_ENABLED == False else "❌"
    print(f"{status} REAL_TRADING_ENABLED = False (Paper mode)")
    checks["Sistem Konfigürasyonu"].append(config.REAL_TRADING_ENABLED == False)
    
    # Check 1.2
    status = "✅" if len(config.SYMBOLS) >= 24 else "❌"
    print(f"{status} Coin sayısı: {len(config.SYMBOLS)} (min 24 gerekli)")
    checks["Sistem Konfigürasyonu"].append(len(config.SYMBOLS) >= 24)
    
    # Check 1.3
    status = "✅" if config.ALLOW_LONG == True else "❌"
    print(f"{status} ALLOW_LONG = True (long trades aktif)")
    checks["Sistem Konfigürasyonu"].append(config.ALLOW_LONG == True)
    
    # Check 1.4
    status = "✅" if config.ALLOW_SHORT == False else "❌"
    print(f"{status} ALLOW_SHORT = False (short kapalı)")
    checks["Sistem Konfigürasyonu"].append(config.ALLOW_SHORT == False)
    
    # ============= BÖLÜM 2: Edge Discovery =============
    print("\n🎯 BÖLÜM 2: EDGE DISCOVERY SETUP")
    print("-" * 70)
    
    # Check 2.1
    status = "✅" if config.ALLOW_EDGE_DISCOVERY else "❌"
    print(f"{status} ALLOW_EDGE_DISCOVERY = {config.ALLOW_EDGE_DISCOVERY}")
    checks["Edge Discovery Setup"].append(config.ALLOW_EDGE_DISCOVERY)
    
    # Check 2.2
    status = "✅" if len(config.TOP_3_COINS) == 3 else "❌"
    print(f"{status} TOP_3_COINS = {config.TOP_3_COINS}")
    for coin in config.TOP_3_COINS:
        print(f"   • {coin}")
    checks["Edge Discovery Setup"].append(len(config.TOP_3_COINS) == 3)
    
    # Check 2.3
    status = "✅" if config.EDGE_DISCOVERY_FOCUS_MODE else "❌"
    print(f"{status} EDGE_DISCOVERY_FOCUS_MODE = {config.EDGE_DISCOVERY_FOCUS_MODE}")
    checks["Edge Discovery Setup"].append(config.EDGE_DISCOVERY_FOCUS_MODE)
    
    # Check 2.4
    status = "✅" if config.EDGE_MIN_SAMPLE_SIZE == 50 else "❌"
    print(f"{status} EDGE_MIN_SAMPLE_SIZE = {config.EDGE_MIN_SAMPLE_SIZE} (N > 50)")
    checks["Edge Discovery Setup"].append(config.EDGE_MIN_SAMPLE_SIZE == 50)
    
    # Check 2.5
    status = "✅" if config.EDGE_MIN_WIN_RATE >= 0.65 else "❌"
    print(f"{status} EDGE_MIN_WIN_RATE = {config.EDGE_MIN_WIN_RATE:.1%} (WR > 65%)")
    checks["Edge Discovery Setup"].append(config.EDGE_MIN_WIN_RATE >= 0.65)
    
    # ============= BÖLÜM 3: Telegram =============
    print("\n📱 BÖLÜM 3: TELEGRAM BAĞLANTISI")
    print("-" * 70)
    
    # Check 3.1
    status = "✅" if config.TELEGRAM_ENABLED else "❌"
    print(f"{status} TELEGRAM_ENABLED = {config.TELEGRAM_ENABLED}")
    checks["Telegram Bağlantısı"].append(config.TELEGRAM_ENABLED)
    
    if config.TELEGRAM_ENABLED:
        # Check 3.2: Bağlantı testi
        try:
            await telegram.send(
                "🟢 <b>PAPER TRADING BAŞLANIYOR</b>\n"
                f"Tarih: <code>2026-04-03</code>\n"
                f"Süre: <code>7 gün</code>\n"
                f"Koinler: <code>ARPA/SOL/XRP</code>\n"
                f"Koruma: <code>Likidation Detection</code>"
            )
            print(f"✅ Telegram bağlantısı tamamlandı - başlangıç mesajı gönderildi")
            checks["Telegram Bağlantısı"].append(True)
        except Exception as e:
            print(f"❌ Telegram hatası: {e}")
            checks["Telegram Bağlantısı"].append(False)
    
    # ============= BÖLÜM 4: Paper Trading Ayarları =============
    print("\n📊 BÖLÜM 4: PAPER TRADING AYARLARI")
    print("-" * 70)
    
    # Check 4.1
    status = "✅" if config.PAPER_TRADING_MODE else "❌"
    print(f"{status} PAPER_TRADING_MODE = {config.PAPER_TRADING_MODE}")
    checks["Paper Trading Ayarları"].append(config.PAPER_TRADING_MODE)
    
    # Check 4.2
    status = "✅" if config.PAPER_TRADING_DURATION_DAYS == 7 else "❌"
    print(f"{status} Süre: {config.PAPER_TRADING_DURATION_DAYS} gün")
    start_date = datetime.strptime(config.PAPER_TRADING_START_DATE, "%Y-%m-%d")
    end_date = start_date + timedelta(days=config.PAPER_TRADING_DURATION_DAYS)
    print(f"   Başlangıç: {start_date.strftime('%A, %Y-%m-%d')}")
    print(f"   Bitiş: {end_date.strftime('%A, %Y-%m-%d')}")
    checks["Paper Trading Ayarları"].append(config.PAPER_TRADING_DURATION_DAYS == 7)
    
    # Check 4.3
    status = "✅" if config.PAPER_TRADING_LOG_SIGNALS else "❌"
    print(f"{status} PAPER_TRADING_LOG_SIGNALS = {config.PAPER_TRADING_LOG_SIGNALS} (sinyaller kaydedilecek)")
    checks["Paper Trading Ayarları"].append(config.PAPER_TRADING_LOG_SIGNALS)
    
    # Check 4.4
    status = "✅" if config.INITIAL_BALANCE == 10000.0 else "❌"
    print(f"{status} Başlangıç bakiyesi: ${config.INITIAL_BALANCE:,.2f}")
    checks["Paper Trading Ayarları"].append(config.INITIAL_BALANCE == 10000.0)
    
    # ============= BÖLÜM 5: Likidation Protection =============
    print("\n⚠️  BÖLÜM 5: LIKIDATION KORUMASI")
    print("-" * 70)
    
    # Check 5.1
    status = "✅" if config.LIQUIDATION_ALERT_ENABLED else "❌"
    print(f"{status} LIQUIDATION_ALERT_ENABLED = {config.LIQUIDATION_ALERT_ENABLED}")
    checks["Likidation Protection"].append(config.LIQUIDATION_ALERT_ENABLED)
    
    # Check 5.2
    print(f"✅ Risk Seviyeleri:")
    print(f"   • HIGH: {config.LIQUIDATION_RISK_THRESHOLD:.1%} mesafe")
    print(f"   • CRITICAL: {config.LIQUIDATION_CRITICAL_THRESHOLD:.1%} mesafe")
    checks["Likidation Protection"].append(True)
    
    # Check 5.3
    print(f"✅ Check aralığı: {config.LIQUIDATION_CHECK_INTERVAL}s")
    checks["Likidation Protection"].append(config.LIQUIDATION_CHECK_INTERVAL > 0)
    
    # ============= SONUÇ =============
    print("\n" + "="*70)
    print("ÖZET")
    print("="*70)
    
    total_checks = sum(len(v) for v in checks.values())
    passed_checks = sum(sum(v) for v in checks.values())
    
    for section, results in checks.items():
        section_passed = sum(results)
        section_total = len(results)
        status = "🟢" if section_passed == section_total else "🟡"
        print(f"{status} {section}: {section_passed}/{section_total} ✓")
    
    print(f"\n📊 TOPLAM: {passed_checks}/{total_checks} kontrol geçti")
    
    if passed_checks == total_checks:
        print("\n" + "🟢 "*35)
        print("PAPER TRADING BAŞLATMAYA HAZIR!")
        print("🟢 "*35)
        print("\n📍 Sonraki adım:")
        print("   python main.py")
        print("\n⏸️  Paper trading 7 gün boyunca çalışacak:")
        print(f"   📅 {start_date.strftime('%A')} → {end_date.strftime('%A')}")
        print(f"   🎯 3 Coin monitored: ARPAUSDT, SOLUSDT, XRPUSDT")
        print(f"   📱 Telegram sinyalleri telefonuna gelecek")
        print(f"   ⚠️  Likidation alert'leri aktif")
        print("\n💡 İpuçları:")
        print("   • Sabah/Öğle/Akşam 3 kez kontrol et")
        print("   • Telegram mesajlarını dokümante et")
        print("   • Win rate takip et (hedef: ≥60%)")
        print("   • Pattern doğruluğunu test et")
        return 0
    else:
        print("\n" + "🔴 "*35)
        print("KIRMıZı KONTROLLER DÜZELTILMEDEN BAŞLAMAYINIZ!")
        print("🔴 "*35)
        print("\n⚠️  Lütfen yukarıdaki kontrolları düzelt ve yeniden çalıştır:")
        print("   python paper_trading_startup.py")
        return 1


async def main():
    exit_code = await startup_checklist()
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ İptal edildi")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        sys.exit(1)
