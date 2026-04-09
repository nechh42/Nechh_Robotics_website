"""
coin_expansion_test.py — Yeni coin ekleme + momentum analizi
==============================================================
Soru: Binance'te yüzlerce coin var. Farklı coinler WR'yi artırır mı?

Test 1: Mevcut 12 aktif coin (baseline)
Test 2: Top volume futures coinleri ekleme
Test 3: Momentum coinleri (yüksek volatilite)
Test 4: Sadece en iyi 5 coin (kalite > miktar)
Test 5: Mevcut bl'den geri ekleme (SUI, WIF özellikle)
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from backtest.backtest_v3 import BacktestV3

tests = []

# Mevcut aktif coinler = SYMBOLS - BLACKLIST
active = [s for s in config.SYMBOLS if s not in config.COIN_BLACKLIST]
print(f"Aktif coinler ({len(active)}): {active}")

# === BASELINE ===
print("\n=== BASELINE (12 aktif coin) ===")
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("BASELINE-12", r))

# === Test 1: Sadece en iyi 5 coin ===
print("\n=== Sadece TOP 5 (VET,ETH,CRV,DOGE,ADA) ===")
old_bl = config.COIN_BLACKLIST.copy()
keep_5 = ["VETUSDT", "ETHUSDT", "CRVUSDT", "DOGEUSDT", "ADAUSDT"]
config.COIN_BLACKLIST = [s for s in config.SYMBOLS if s not in keep_5]
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("TOP5", r))
config.COIN_BLACKLIST = old_bl

# === Test 2: Sadece en iyi 7 (WR>=%49) ===
print("\n=== TOP 7 (VET,ETH,CRV,ADA,DOGE,BTC,ZEC) ===")
old_bl = config.COIN_BLACKLIST.copy()
keep_7 = ["VETUSDT", "ETHUSDT", "CRVUSDT", "ADAUSDT", "DOGEUSDT", "BTCUSDT", "ZECUSDT"]
config.COIN_BLACKLIST = [s for s in config.SYMBOLS if s not in keep_7]
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("TOP7", r))
config.COIN_BLACKLIST = old_bl

# === Test 3: YENİ COİNLER EKLE (Binance futures top volume) ===
print("\n=== 12 coin + YENİ 5 coin (LINK,DOT,FIL,MATIC,ARB) ===")
old_symbols = config.SYMBOLS.copy()
new_coins = ["LINKUSDT", "DOTUSDT", "FILUSDT", "MATICUSDT", "ARBUSDT"]
config.SYMBOLS = old_symbols + new_coins
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("12+5yeni", r))

# Yeni coin performansı
new_trades = [t for t in r.trades if t.symbol in new_coins]
if new_trades:
    nw = sum(1 for t in new_trades if t.net_pnl > 0)
    print(f"\n  YENİ COİN PERFORMANSI:")
    for nc in new_coins:
        nt = [t for t in new_trades if t.symbol == nc]
        if nt:
            ncw = sum(1 for t in nt if t.net_pnl > 0)
            print(f"    {nc:12s}: {len(nt):3d} trade | WR={ncw/len(nt)*100:.1f}% | PnL=${sum(t.net_pnl for t in nt):+.2f}")
config.SYMBOLS = old_symbols

# === Test 4: YENİ 5 coin 2. set (DYDX, APE, GMT, SAND, MANA) ===
print("\n=== 12 coin + YENİ 5 coin SET2 (DYDX,APE,GMT,SAND,MANA) ===")
old_symbols = config.SYMBOLS.copy()
new_coins2 = ["DYDXUSDT", "APEUSDT", "GMTUSDT", "SANDUSDT", "MANAUSDT"]
config.SYMBOLS = old_symbols + new_coins2
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("12+5set2", r))

new_trades2 = [t for t in r.trades if t.symbol in new_coins2]
if new_trades2:
    print(f"\n  YENİ COİN SET2 PERFORMANSI:")
    for nc in new_coins2:
        nt = [t for t in new_trades2 if t.symbol == nc]
        if nt:
            ncw = sum(1 for t in nt if t.net_pnl > 0)
            print(f"    {nc:12s}: {len(nt):3d} trade | WR={ncw/len(nt)*100:.1f}% | PnL=${sum(t.net_pnl for t in nt):+.2f}")
config.SYMBOLS = old_symbols

# === Test 5: WIFUSDT geri ekle (v15.7'de %49 WR, sınırda) ===
print("\n=== WIFUSDT geri ekle ===")
old_bl = config.COIN_BLACKLIST.copy()
config.COIN_BLACKLIST = [c for c in old_bl if c != "WIFUSDT"]  # WIF zaten blacklist'te değil
# Actually WIF is not in blacklist, it's active. Let's check
wif_active = "WIFUSDT" not in config.COIN_BLACKLIST
if wif_active:
    print("  WIF zaten aktif. Skipping.")
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("WIF-aktif", r))
else:
    config.COIN_BLACKLIST = [c for c in old_bl if c != "WIFUSDT"]
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("+WIF", r))
    config.COIN_BLACKLIST = old_bl

# === Test 6: Büyük hacimli stablecoin paritesi ===
print("\n=== 12 coin + TRX, HBAR, FTM ===")
old_symbols = config.SYMBOLS.copy()
new_coins3 = ["TRXUSDT", "HBARUSDT", "FTMUSDT"]
config.SYMBOLS = old_symbols + new_coins3
bt = BacktestV3()
r = bt.run(days=60)
tests.append(("12+TRX/HBAR/FTM", r))

new_trades3 = [t for t in r.trades if t.symbol in new_coins3]
if new_trades3:
    print(f"\n  YENİ COİN SET3 PERFORMANSI:")
    for nc in new_coins3:
        nt = [t for t in new_trades3 if t.symbol == nc]
        if nt:
            ncw = sum(1 for t in nt if t.net_pnl > 0)
            print(f"    {nc:12s}: {len(nt):3d} trade | WR={ncw/len(nt)*100:.1f}% | PnL=${sum(t.net_pnl for t in nt):+.2f}")
config.SYMBOLS = old_symbols

# === SONUÇ TABLOSU ===
print("\n" + "="*85)
print("COİN GENİŞLEME TEST SONUÇLARI")
print("="*85)
print(f"  {'Test':<20s} | {'Coin':>4s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'MaxDD':>6s} | {'AvgW':>6s} | {'AvgL':>6s}")
print(f"  {'─'*88}")

for name, r in tests:
    active_c = len(set(t.symbol for t in r.trades))
    marker = " ★" if r.win_rate >= 51.0 and r.total_pnl > tests[0][1].total_pnl else (" ✅" if r.total_pnl > tests[0][1].total_pnl else "")
    print(f"  {name:<20s} | {active_c:4d} | {r.total_trades:5d} | {r.win_rate:5.1f}% | ${r.total_pnl:+8.2f} | {r.profit_factor:5.2f} | {r.max_drawdown_pct:5.1f}% | ${r.avg_win:+5.2f} | ${r.avg_loss:+5.2f}{marker}")

print(f"\n  ★ = WR≥51% + PnL baseline'dan iyi  |  ✅ = PnL iyi")
print("="*85)
