"""Entry Price vs Current Price - Açıklama"""
import sqlite3
import requests
from datetime import datetime

print('='*90)
print('ENTRY PRICE vs CURRENT PRICE - FARK')
print('='*90)
print()

# Example from database
conn = sqlite3.connect('data/war_machine.db')
c = conn.cursor()

# Get BTCUSDT position
c.execute("SELECT symbol, side, entry_price, entry_time, stop_loss, take_profit FROM positions WHERE symbol='BTCUSDT'")
result = c.fetchone()

if result:
    sym, side, entry, entry_time, sl, tp = result
    
    # Get current price
    r = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={sym}')
    current = float(r.json()['price'])
    
    entry_dt = datetime.fromisoformat(entry_time).strftime('%d %b %H:%M')
    
    print(f'{sym} {side} POZİSYONU:')
    print()
    print(f'  ENTRY PRICE (GİRİŞ):  ${entry:.2f}')
    print(f'  └─ Bu fiyat HİÇ DEĞİŞMEZ - pozisyon açıldığında ({entry_dt}) kaydedildi')
    print()
    print(f'  CURRENT PRICE (ŞU AN): ${current:.2f}')
    print(f'  └─ Bu fiyat SÜREKLİ DEĞİŞİR - şu anki piyasa fiyatı')
    print()
    
    change_pct = (current - entry) / entry * 100
    print(f'  FİYAT DEĞİŞİMİ: {change_pct:+.2f}%')
    print()
    print('─'*90)
    print()
    print('TELEGRAM MESAJINDA GÖRDÜĞÜN:')
    print()
    print(f'  "BTCUSDT LONG @ ${entry:.2f}"')
    print(f'   └─ Bu ENTRY PRICE - sabit kalır (doğru)')
    print()
    print(f'  "PnL: (+${(current - entry) * 0.1914:.2f})"')
    print(f'   └─ Bu DEĞİŞİYOR - current price\'a göre hesaplanıyor')
    print()
    print(f'  Şu an current price ${current:.2f} → PnL {change_pct:+.2f}%')
    print()

conn.close()

print('='*90)
print('ÖRNEK: BTC Fiyatı Değişirse Ne Olur?')
print('='*90)
print()
print(f'Entry: ${entry:.2f} (SABİT - hiç değişmez)')
print()
print(f'Senaryo 1: BTC $70,000 olursa → PnL +{((70000 - entry) / entry * 100):.2f}%')
print(f'Senaryo 2: BTC $69,000 olursa → PnL {((69000 - entry) / entry * 100):.2f}%')
print(f'Senaryo 3: BTC $68,500 olursa → SL PATLAR (SL=${sl:.2f})')
print()
print('Entry price HER ZAMAN $69,656.24 kalır - çünkü o fiyattan girdin.')
print('Current price değişir - ve Telegram\'daki PnL da değişir.')
