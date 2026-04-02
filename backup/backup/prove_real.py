"""GERÇEK VERİ KANITI - Database doğrudan okuma"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/war_machine.db')
c = conn.cursor()

print('='*90)
print('WAR_MACHINE.DB - GERÇEK DATABASE KAYITLARI')
print('='*90)
print()

# Get all trades
c.execute("SELECT timestamp, symbol, side, entry_price, exit_price, net_pnl, reason FROM trades ORDER BY id")
trades = c.fetchall()

print(f'KAPANAN TRADE\'LER: {len(trades)}')
print()

total_closed = 0
wins = 0
losses = 0

for i, (ts, sym, side, entry, exit, pnl, reason) in enumerate(trades, 1):
    dt = datetime.fromisoformat(ts).strftime('%d %b %H:%M')
    pnl_val = float(pnl or 0)
    total_closed += pnl_val
    
    if pnl_val > 0:
        wins += 1
        status = '✓ WIN'
    else:
        losses += 1
        status = '✗ LOSS'
    
    print(f'{i}. [{dt}] {sym:12} {side:5} | ${entry:.4f} → ${exit:.4f}')
    print(f'   PnL: ${pnl_val:+.2f} {status}')
    print(f'   Sebep: {reason[:50]}')
    print()

print('='*90)
print(f'TOPLAM KAPANAN TRADE PnL: ${total_closed:+.2f}')
print(f'Win/Loss: {wins}W / {losses}L ({wins/(wins+losses)*100:.1f}% WR)')
print('='*90)
print()

# Get open positions
c.execute("SELECT symbol, side, entry_price, size, stop_loss, take_profit FROM positions")
positions = c.fetchall()

print(f'AÇIK POZİSYONLAR: {len(positions)}')
print()

# Get current prices from Binance
import requests
total_unrealized = 0

for sym, side, entry, size, sl, tp in positions:
    try:
        r = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={sym}')
        current_price = float(r.json()['price'])
        
        if side == 'LONG':
            unrealized = (current_price - entry) * size
        else:
            unrealized = (entry - current_price) * size
        
        total_unrealized += unrealized
        
        print(f'{sym:12} {side:5} | Entry: ${entry:.4f} → Now: ${current_price:.4f}')
        print(f'  Unrealized PnL: ${unrealized:+.2f}')
        print()
    except:
        print(f'{sym:12} {side:5} | Entry: ${entry:.4f} (fiyat okunamadı)')
        print()

print('='*90)
print(f'AÇIK POZİSYONLAR GERÇEKLEŞMEMİŞ PnL: ${total_unrealized:+.2f}')
print('='*90)
print()

print('TOPLAM DURUM:')
print(f'  Kapanan trade\'ler (gerçek):      ${total_closed:+.2f}')
print(f'  Açık pozisyonlar (gerçekleşmemiş): ${total_unrealized:+.2f}')
print(f'  ----------------------------------------')
print(f'  TOTAL EQUITY CHANGE:              ${total_closed + total_unrealized:+.2f}')
print()
print(f'Bu sayı Telegram\'daki "Equity: $11,987" ile eşleşmeli (başlangıç $10,000)')

conn.close()
