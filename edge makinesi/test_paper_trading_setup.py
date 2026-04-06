#!/usr/bin/env python3
"""
Paper Trading Setup Test
========================
Teste et:
  1. Telegram bağlantısı
  2. Top 3 Coin konfigürasyonu  
  3. Edge Discovery ayarları
  4. Likidation Alert system
"""

import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from monitoring.telegram import telegram


async def test_telegram_connection():
    """Telegram bot bağlantı testi"""
    print("\n" + "="*70)
    print("TEST 1: TELEGRAM BAĞLANTISI")
    print("="*70)
    
    if not config.TELEGRAM_ENABLED:
        print("❌ TELEGRAM_ENABLED = False")
        print("   → Lütfen .env dosyasında TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ekleyin")
        return False
    
    print(f"✅ Bot Token: {config.TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"✅ Chat ID: {config.TELEGRAM_CHAT_ID}")
    
    # Test bağlantısı
    try:
        await telegram.send(
            "🟢 <b>PAPER TRADING TEST BAŞLANDI</b>\n"
            "War Machine v3 sistemi bağlantı testi yapılıyor...\n"
            f"Tarih: <code>2026-04-03</code>\n"
            f"Mod: <code>PAPER TRADING</code>"
        )
        print("✅ Test mesajı başarıyla gönderildi!")
        return True
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False


async def test_config_setup():
    """Config TEST'i"""
    print("\n" + "="*70)
    print("TEST 2: TOP 3 COIN KONFIGÜRASYONU")
    print("="*70)
    
    assert config.ALLOW_EDGE_DISCOVERY, "❌ ALLOW_EDGE_DISCOVERY = False"
    print(f"✅ ALLOW_EDGE_DISCOVERY = {config.ALLOW_EDGE_DISCOVERY}")
    
    assert len(config.TOP_3_COINS) == 3, f"❌ TOP_3_COINS != 3 (gelen: {len(config.TOP_3_COINS)})"
    print(f"✅ TOP_3_COINS = {config.TOP_3_COINS}")
    assert "ARPAUSDT" in config.TOP_3_COINS
    assert "SOLUSDT" in config.TOP_3_COINS
    assert "XRPUSDT" in config.TOP_3_COINS
    print("   ✓ ARPAUSDT (81.48% WR, low_volatility)")
    print("   ✓ SOLUSDT (68.97% WR, ranging_bb_upper)")
    print("   ✓ XRPUSDT (66.67% WR, rsi_below_30)")
    
    assert config.EDGE_MIN_SAMPLE_SIZE == 50, "❌ N sample check başarısız"
    print(f"✅ EDGE_MIN_SAMPLE_SIZE = {config.EDGE_MIN_SAMPLE_SIZE}")
    
    assert config.EDGE_MIN_WIN_RATE >= 0.65, "❌ WR threshold başarısız"
    print(f"✅ EDGE_MIN_WIN_RATE = {config.EDGE_MIN_WIN_RATE:.1%}")
    
    return True


async def test_liquidation_config():
    """Likidation Alert TEST'i"""
    print("\n" + "="*70)
    print("TEST 3: LIKIDATION ALERT KONFIGÜRASYONU")
    print("="*70)
    
    assert config.LIQUIDATION_ALERT_ENABLED, "❌ LIQUIDATION_ALERT_ENABLED = False"
    print(f"✅ LIQUIDATION_ALERT_ENABLED = {config.LIQUIDATION_ALERT_ENABLED}")
    
    assert config.LIQUIDATION_RISK_THRESHOLD > 0, "❌ Risk threshold başarısız"
    print(f"✅ LIQUIDATION_RISK_THRESHOLD = {config.LIQUIDATION_RISK_THRESHOLD:.1%}")
    
    assert config.LIQUIDATION_CRITICAL_THRESHOLD > 0, "❌ Critical threshold başarısız"
    print(f"✅ LIQUIDATION_CRITICAL_THRESHOLD = {config.LIQUIDATION_CRITICAL_THRESHOLD:.1%}")
    
    print(f"✅ LIQUIDATION_CHECK_INTERVAL = {config.LIQUIDATION_CHECK_INTERVAL}s")
    
    return True


async def test_paper_trading_mode():
    """Paper Trading MODE TEST'i"""
    print("\n" + "="*70)
    print("TEST 4: PAPER TRADING MODE")
    print("="*70)
    
    assert config.PAPER_TRADING_MODE, "❌ PAPER_TRADING_MODE = False"
    print(f"✅ PAPER_TRADING_MODE = {config.PAPER_TRADING_MODE}")
    
    assert not config.REAL_TRADING_ENABLED, "❌ REAL_TRADING AÇIK DURUMDA!"
    print(f"✅ REAL_TRADING_ENABLED = {config.REAL_TRADING_ENABLED} (KAPALI = GÜVENLİ)")
    
    assert config.PAPER_TRADING_DURATION_DAYS == 7, "❌ Süre 7 gün değil"
    print(f"✅ PAPER_TRADING_DURATION_DAYS = {config.PAPER_TRADING_DURATION_DAYS} gün")
    
    print(f"✅ PAPER_TRADING_START_DATE = {config.PAPER_TRADING_START_DATE}")
    
    return True


async def test_edge_discovery_methods():
    """Edge Discovery metodları TEST'i"""
    print("\n" + "="*70)
    print("TEST 5: EDGE DISCOVERY METODLARI")
    print("="*70)
    
    try:
        from strategies.indicators import (
            detect_low_volatility,
            detect_ranging_bb_upper,
            detect_rsi_30_50
        )
        print("✅ detect_low_volatility() loaded")
        print("✅ detect_ranging_bb_upper() loaded")
        print("✅ detect_rsi_30_50() loaded")
        return True
    except ImportError as e:
        print(f"❌ Import hatası: {e}")
        return False


async def test_telegram_liquidation_alert():
    """Telegram liquidation_spike_alert() TEST'i"""
    print("\n" + "="*70)
    print("TEST 6: TELEGRAM LIKIDATION ALERT FONKSIYONU")
    print("="*70)
    
    try:
        # Check method exists
        assert hasattr(telegram, 'liquidation_spike_alert'), \
            "❌ liquidation_spike_alert method bulunamadı"
        print("✅ telegram.liquidation_spike_alert() exists")
        
        # Check method signature
        import inspect
        sig = inspect.signature(telegram.liquidation_spike_alert)
        params = list(sig.parameters.keys())
        required_params = ['symbol', 'risk_level', 'liquidation_price', 'current_price', 'distance_pct']
        
        for param in required_params:
            assert param in params, f"❌ Parameter {param} eksik"
        print(f"✅ Tüm gerekli parametreler var:")
        for param in required_params:
            print(f"   • {param}")
        
        # Test method call (dummy)
        await telegram.liquidation_spike_alert(
            symbol='ARPAUSDT',
            risk_level='HIGH',
            liquidation_price=0.6850,
            current_price=0.7120,
            distance_pct=3.94,
            liquidation_count=234,
            volume_spike=45.2
        )
        print("✅ Likidation alert mesajı başarıyla gönderildi (TEST)!")
        return True
        
    except AssertionError as e:
        print(f"❌ {e}")
        return False
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False


async def test_telegram_top3_signal():
    """Telegram top_3_coins_signal() TEST'i"""
    print("\n" + "="*70)
    print("TEST 7: TELEGRAM TOP 3 COIN SIGNAL FONKSIYONU")
    print("="*70)
    
    try:
        # Check method exists
        assert hasattr(telegram, 'top_3_coins_signal'), \
            "❌ top_3_coins_signal method bulunamadı"
        print("✅ telegram.top_3_coins_signal() exists")
        
        # Test method call (dummy)
        await telegram.top_3_coins_signal(
            coin='ARPAUSDT',
            pattern='low_volatility',
            win_rate=0.8148,
            signal_reason='Low volatility environment with clear resistance',
            confidence=0.92
        )
        print("✅ Top 3 Coin signal mesajı başarıyla gönderildi (TEST)!")
        return True
        
    except AssertionError as e:
        print(f"❌ {e}")
        return False
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False


async def main():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  PAPER TRADING SETUP TEST - War Machine v3".ljust(68) + "║")
    print("║" + "  Telegram + Edge Discovery + Likidation Protection".ljust(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {}
    
    # Test 1: Telegram
    try:
        results['Telegram'] = await test_telegram_connection()
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")
        results['Telegram'] = False
    
    # Test 2: Config
    try:
        results['Config'] = await test_config_setup()
    except AssertionError as e:
        print(f"❌ {e}")
        results['Config'] = False
    
    # Test 3: Likidation Config
    try:
        results['Likidation Config'] = await test_liquidation_config()
    except AssertionError as e:
        print(f"❌ {e}")
        results['Likidation Config'] = False
    
    # Test 4: Paper Trading Mode
    try:
        results['Paper Trading Mode'] = await test_paper_trading_mode()
    except AssertionError as e:
        print(f"❌ {e}")
        results['Paper Trading Mode'] = False
    
    # Test 5: Edge Discovery Methods
    try:
        results['Edge Discovery Methods'] = await test_edge_discovery_methods()
    except Exception as e:
        print(f"❌ {e}")
        results['Edge Discovery Methods'] = False
    
    # Test 6: Liquidation Alert Telegram
    try:
        results['Telegram Likidation Alert'] = await test_telegram_liquidation_alert()
    except Exception as e:
        print(f"❌ {e}")
        results['Telegram Likidation Alert'] = False
    
    # Test 7: Top 3 Signal Telegram
    try:
        results['Telegram Top 3 Signal'] = await test_telegram_top3_signal()
    except Exception as e:
        print(f"❌ {e}")
        results['Telegram Top 3 Signal'] = False
    
    # Summary
    print("\n" + "="*70)
    print("ÖZET")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\nSonuç: {passed}/{total} test geçti")
    
    if passed == total:
        print("\n🟢 PAPER TRADING BAŞLATMAYA HAZIR!")
        print("\nSonraki adımlar:")
        print("1. main.py dosyasını başlat: python main.py")
        print("2. 7 gün boyunca Telegram sinyallerini izle")
        print("3. ARPAUSDT, SOLUSDT, XRPUSDT'in pattern'larını gözlemle")
        print("4. Likidation alert'lerinin doğruluğunu test et")
        return 0
    else:
        print("\n🔴 Lütfen kırmızı testleri düzelt")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
