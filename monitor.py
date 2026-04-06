"""
monitor.py - War Machine Detaylı İzleme Raporu
=================================================
Her çalıştırıldığında sistemin tam röntgenini çeker:
  1. Sistem çalışıyor mu? (process check)
  2. Son logları analiz et (hata, uyarı, regime, trade)
  3. DB durumu (trade, pozisyon, bakiye)
  4. Canlı regime + sentiment kontrol
  5. Strateji sinyal simülasyonu (hangi coinler sinyal üretecek?)
  6. Sorun tespiti + erken uyarı

Kullanım: python monitor.py
"""

import os, sys, sqlite3, glob, json
from datetime import datetime, timedelta

sys.path.insert(0, '.')

import requests
import pandas as pd
import numpy as np

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def print_section(title):
    print(f"\n--- {title} ---")

# ============================================================
# BÖLÜM 1: LOG ANALİZİ
# ============================================================
def analyze_logs():
    print_header("1. LOG ANALİZİ")
    
    log_dir = "logs"
    if not os.path.exists(log_dir):
        print("  Log dizini yok!")
        return

    # En son log dosyasını bul
    log_files = sorted(glob.glob(os.path.join(log_dir, "*.log")), key=os.path.getmtime, reverse=True)
    if not log_files:
        # Log dosyası olmayabilir, stdout'a yazılıyor olabilir
        print("  Log dosyası bulunamadı (stdout'a yazılıyor olabilir)")
        return
    
    latest_log = log_files[0]
    print(f"  Son log: {latest_log}")
    
    errors = []
    warnings = []
    trades_opened = []
    trades_closed = []
    candle_closes = []
    regime_logs = []
    risk_rejected = []
    risk_approved = []
    
    try:
        with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if '[ERROR]' in line:
                    errors.append(line)
                elif '[WARNING]' in line or 'RISK NO' in line:
                    if 'RISK NO' in line:
                        risk_rejected.append(line)
                    else:
                        warnings.append(line)
                elif 'OPENED' in line and 'STATE' in line:
                    trades_opened.append(line)
                elif 'CLOSED' in line and 'STATE' in line:
                    trades_closed.append(line)
                elif '[CANDLE]' in line and 'regime=' in line:
                    candle_closes.append(line)
                elif '[REGIME]' in line:
                    regime_logs.append(line)
                elif 'RISK OK' in line:
                    risk_approved.append(line)
    except Exception as e:
        print(f"  Log okuma hatası: {e}")
        return
    
    print_section("Hatalar")
    if errors:
        for e in errors[-10:]:  # Son 10 hata
            print(f"  🔴 {e[-120:]}")
        if len(errors) > 10:
            print(f"  ... toplam {len(errors)} hata")
    else:
        print("  ✅ Hata yok")
    
    print_section("Uyarılar (son 5)")
    if warnings:
        for w in warnings[-5:]:
            print(f"  ⚠️ {w[-120:]}")
    else:
        print("  ✅ Uyarı yok")
    
    print_section("Regime Tespitleri (son 5)")
    if regime_logs:
        for r in regime_logs[-5:]:
            print(f"  📊 {r[-120:]}")
    else:
        print("  ⚠️ Henüz regime tespiti yok")
    
    print_section("Risk Onayları")
    print(f"  ✅ Onaylanan: {len(risk_approved)}")
    print(f"  ❌ Reddedilen: {len(risk_rejected)}")
    if risk_rejected:
        # Ret nedenlerini grupla
        reasons = {}
        for r in risk_rejected:
            # "REDDEDILDI LONG BTCUSDT: LONG sadece TREND_UP'ta..." gibi
            parts = r.split(":", 1)
            reason = parts[-1].strip()[:60] if len(parts) > 1 else "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1])[:5]:
            print(f"    {count}x → {reason}")
    
    print_section("Trade'ler")
    print(f"  Açılan: {len(trades_opened)}")
    print(f"  Kapanan: {len(trades_closed)}")
    for t in trades_opened[-3:]:
        print(f"    📈 {t[-100:]}")
    for t in trades_closed[-3:]:
        print(f"    📉 {t[-100:]}")

# ============================================================
# BÖLÜM 2: VERİTABANI DURUMU
# ============================================================
def check_database():
    print_header("2. VERİTABANI DURUMU")
    
    db_path = "data/war_machine.db"
    if not os.path.exists(db_path):
        print("  ❌ DB bulunamadı!")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Tablolar
    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for tbl in tables:
        name = tbl['name']
        cnt = c.execute(f"SELECT COUNT(*) as c FROM [{name}]").fetchone()['c']
        print(f"  {name}: {cnt} satır")
    
    # Trade'ler
    print_section("Trade Özeti")
    trades = c.execute("SELECT * FROM trades ORDER BY id").fetchall()
    if trades:
        wins = [dict(t) for t in trades if float(dict(t).get('net_pnl', 0)) > 0]
        losses = [dict(t) for t in trades if float(dict(t).get('net_pnl', 0)) <= 0]
        total_pnl = sum(float(dict(t).get('net_pnl', 0)) for t in trades)
        wr = len(wins) / len(trades) * 100 if trades else 0
        
        print(f"  Toplam trade: {len(trades)} ({len(wins)}W / {len(losses)}L)")
        print(f"  Win Rate: {wr:.1f}%")
        print(f"  Toplam PnL: ${total_pnl:.2f}")
        
        if wins and losses:
            avg_win = sum(float(dict(t)['net_pnl']) for t in wins) / len(wins)
            avg_loss = sum(float(dict(t)['net_pnl']) for t in losses) / len(losses)
            pf = sum(float(dict(t)['net_pnl']) for t in wins) / abs(sum(float(dict(t)['net_pnl']) for t in losses))
            print(f"  Ortalama Win: ${avg_win:.2f}")
            print(f"  Ortalama Loss: ${avg_loss:.2f}")
            print(f"  Profit Factor: {pf:.2f}")
            print(f"  R:R gerçekleşen: {abs(avg_win/avg_loss):.2f}")
        
        # Son 5 trade
        print_section("Son Trade'ler")
        for t in trades[-5:]:
            d = dict(t)
            pnl = float(d.get('net_pnl', 0))
            symbol = d.get('symbol', '?')
            side = d.get('side', '?')
            reason = str(d.get('reason', ''))[:30]
            emoji = "✅" if pnl > 0 else "❌"
            print(f"    {emoji} {symbol:12s} {side:5s} PnL=${pnl:+.4f} [{reason}]")
    else:
        print("  Henüz trade yok")
    
    # Açık pozisyonlar
    print_section("Açık Pozisyonlar")
    positions = c.execute("SELECT * FROM positions").fetchall()
    if positions:
        for p in positions:
            d = dict(p)
            print(f"    {d.get('symbol','?'):12s} {d.get('side','?'):5s} "
                  f"entry=${float(d.get('entry_price',0)):.4f} "
                  f"SL=${float(d.get('stop_loss',0)):.4f} "
                  f"TP=${float(d.get('take_profit',0)):.4f}")
    else:
        print("  Açık pozisyon yok")
    
    conn.close()

# ============================================================
# BÖLÜM 3: CANLI PİYASA + REGIME DURUMU
# ============================================================
def check_live_market():
    print_header("3. CANLI PİYASA + REGIME")
    
    # Fear & Greed
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5)
        d = r.json()['data'][0]
        fg = int(d['value'])
        fg_label = d['value_classification']
        
        if fg < 10:
            sent_mult = 0.25
        elif fg < 20:
            sent_mult = 0.50
        elif fg < 40:
            sent_mult = 0.75
        else:
            sent_mult = 1.00
        
        print(f"  Fear & Greed: {fg} ({fg_label}) → pozisyon çarpanı ×{sent_mult:.2f}")
    except Exception as e:
        fg = 50
        sent_mult = 1.0
        print(f"  FG API hatası: {e}")
    
    # Regime dağılımı
    from strategies.regime import detect_regime, _calc_wilder_adx
    from strategies.indicators import calc_atr, calc_rsi
    import config
    
    print_section("Regime Dağılımı (canlı 4h veri)")
    
    regime_map = {"TREND_UP": [], "TREND_DOWN": [], "RANGING": [], "VOLATILE": []}
    
    for sym in config.SYMBOLS:
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": sym, "interval": "4h", "limit": 100}
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            df = pd.DataFrame(data[:-1], columns=['timestamp','open','high','low','close','volume',
                                                   'close_time','quote_vol','trades','taker_buy_base',
                                                   'taker_buy_quote','ignore'])
            for col in ['open','high','low','close','volume']:
                df[col] = df[col].astype(float)
            
            regime = detect_regime(df)
            regime_map[regime].append(sym)
            
            import time
            time.sleep(0.05)
        except Exception as e:
            print(f"    {sym}: HATA - {e}")
    
    for regime, coins in regime_map.items():
        emoji = {"TREND_UP": "🟢", "TREND_DOWN": "🔴", "RANGING": "🟡", "VOLATILE": "⚡"}.get(regime, "?")
        can_trade = ""
        if regime == "TREND_UP":
            can_trade = f"→ LONG ×{sent_mult:.2f}"
        elif regime == "RANGING":
            can_trade = f"→ LONG ×{sent_mult*0.5:.2f}"
        elif regime == "TREND_DOWN":
            can_trade = f"→ SHORT koşullu ×{sent_mult:.2f}"
        elif regime == "VOLATILE":
            can_trade = "→ BLOKLU"
        
        print(f"  {emoji} {regime:12s}: {len(coins):2d} coin {can_trade}")
        if coins:
            print(f"      {', '.join(coins)}")
    
    total_tradeable = len(regime_map["TREND_UP"]) + len(regime_map["RANGING"]) + len(regime_map["TREND_DOWN"])
    print(f"\n  Trade açılabilir coin: {total_tradeable}/{len(config.SYMBOLS)}")
    
    return regime_map, fg, sent_mult

# ============================================================
# BÖLÜM 4: SORUN TESPİTİ + ERKEN UYARI
# ============================================================
def diagnostics(regime_map, fg, sent_mult):
    print_header("4. SORUN TESPİTİ + ERKEN UYARI")
    
    issues = []
    info = []
    
    # Saat kontrolü — gece filtresi
    from datetime import timezone
    utc_hour = datetime.now(timezone.utc).hour
    if 0 <= utc_hour < 6:
        issues.append(f"⏰ Gece filtresi aktif ({utc_hour:02d}:00 UTC) — trade engelleniyor (06:00'a kadar)")
    else:
        info.append(f"✅ Gece filtresi kapalı ({utc_hour:02d}:00 UTC) — trade açılabilir")
    
    # 4h mum kapanış saatleri
    next_4h = ((utc_hour // 4) + 1) * 4
    if next_4h >= 24:
        next_4h -= 24
    info.append(f"⏱️ Sonraki 4h mum kapanışı: {next_4h:02d}:00 UTC")
    
    # Sentiment kontrolü
    if fg < 10:
        issues.append(f"🔴 Aşırı korku (fg={fg}) — pozisyon boyutu ×0.25 (çok küçük)")
    elif fg < 20:
        info.append(f"🟡 Yüksek korku (fg={fg}) — pozisyon boyutu ×0.50")
    else:
        info.append(f"✅ Sentiment OK (fg={fg})")
    
    # Regime kontrolü
    if len(regime_map["TREND_UP"]) == 0 and len(regime_map["TREND_DOWN"]) == 0:
        issues.append("⚠️ Trend yok — tüm coinler RANGING/VOLATILE (sadece VWAP/Edge sinyal üretebilir)")
    
    if len(regime_map["VOLATILE"]) > len(regime_map["TREND_UP"]) + len(regime_map["RANGING"]):
        issues.append("🔴 Çoğu coin VOLATILE — çok az trade beklenir")
    
    # Trade beklentisi
    n_long = len(regime_map["TREND_UP"]) + len(regime_map["RANGING"])
    n_short = len(regime_map["TREND_DOWN"])
    if n_long + n_short == 0:
        issues.append("❌ Trade açılabilir coin yok!")
    else:
        info.append(f"📊 {n_long} coin LONG + {n_short} coin SHORT olası")
    
    # Logda hata kontrolü
    log_dir = "logs"
    if os.path.exists(log_dir):
        log_files = sorted(glob.glob(os.path.join(log_dir, "*.log")), key=os.path.getmtime, reverse=True)
        if log_files:
            error_count = 0
            try:
                with open(log_files[0], 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if '[ERROR]' in line:
                            error_count += 1
            except:
                pass
            if error_count > 0:
                issues.append(f"🔴 Log'da {error_count} hata var — kontrol et!")
            else:
                info.append("✅ Log'da hata yok")
    
    # DB kontrolü
    db_path = "data/war_machine.db"
    if not os.path.exists(db_path):
        issues.append("❌ Veritabanı bulunamadı — sistem çalışmıyor olabilir!")
    else:
        db_size = os.path.getsize(db_path)
        if db_size < 1024:
            info.append(f"📁 DB boyutu: {db_size} byte (yeni/boş)")
        else:
            info.append(f"📁 DB boyutu: {db_size/1024:.1f} KB")
    
    # Sonuç
    if issues:
        print("  SORUNLAR:")
        for i in issues:
            print(f"    {i}")
    
    print("  BİLGİ:")
    for i in info:
        print(f"    {i}")
    
    # Genel durum
    print_section("GENEL DURUM")
    if not issues:
        print("  🟢 SAĞLIKLI — Sorun tespit edilmedi")
    elif any("❌" in i for i in issues):
        print("  🔴 KRİTİK — Acil müdahale gerekli")
    else:
        print("  🟡 DİKKAT — Sorunlar var ama kritik değil")

# ============================================================
# BÖLÜM 5: CONFIG ÖZETİ
# ============================================================
def show_config():
    print_header("5. AKTİF CONFIG")
    import config
    
    print(f"  Mode: {'LIVE' if config.REAL_TRADING_ENABLED else 'PAPER'}")
    print(f"  Balance: ${config.INITIAL_BALANCE:,.0f}")
    print(f"  Coins: {len(config.SYMBOLS)}")
    print(f"  Max Positions: {config.MAX_POSITIONS}")
    print(f"  ALLOW_LONG: {config.ALLOW_LONG}")
    print(f"  ALLOW_SHORT: {config.ALLOW_SHORT}")
    print(f"  ALLOW_SHORT_CONDITIONAL: {getattr(config, 'ALLOW_SHORT_CONDITIONAL', False)}")
    print(f"  SL: {config.SL_ATR_MULTIPLIER}x ATR")
    print(f"  TP: {config.TP_ATR_MULTIPLIER}x ATR")
    print(f"  R:R: {config.TP_ATR_MULTIPLIER/config.SL_ATR_MULTIPLIER:.1f}:1")
    print(f"  Breakeven WR: {1/(1+config.TP_ATR_MULTIPLIER/config.SL_ATR_MULTIPLIER)*100:.1f}%")
    print(f"  Min Confidence: {config.STRATEGY_MIN_CONFIDENCE}")
    print(f"  Night Filter: KALDIRILDI (7/24 aktif)")
    print(f"  Trailing: activate={config.TRAILING_STOP_ACTIVATE*100:.1f}%, dist={config.TRAILING_STOP_DISTANCE*100:.1f}%")

# ============================================================
# ANA
# ============================================================
if __name__ == "__main__":
    now = datetime.now()
    print(f"╔══════════════════════════════════════════════════════════════════════╗")
    print(f"║  WAR MACHINE İZLEME RAPORU — {now.strftime('%Y-%m-%d %H:%M:%S'):>30}     ║")
    print(f"╚══════════════════════════════════════════════════════════════════════╝")
    
    show_config()
    check_database()
    analyze_logs()
    regime_map, fg, sent_mult = check_live_market()
    diagnostics(regime_map, fg, sent_mult)
    
    print(f"\n{'='*70}")
    print(f"  RAPOR SONU — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*70}")
