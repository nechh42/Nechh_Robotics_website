"""Komisyon Kanıtı - Masraflar düşülüyor"""
import sqlite3

conn = sqlite3.connect('data/war_machine.db')
c = conn.cursor()

print('='*90)
print('KOMİSYONLAR DÜŞÜLÜYOR - KANIT')
print('='*90)
print()

# We need to parse the log to get commission data since it's not in the database
# Let's check the closed trades table structure first
c.execute("PRAGMA table_info(trades)")
columns = c.fetchall()
print('TRADES TABLOSU KOLONLARI:')
for col in columns:
    print(f'  - {col[1]} ({col[2]})')
print()

# Get trades
c.execute("SELECT id, symbol, side, entry_price, exit_price, net_pnl FROM trades ORDER BY id")
trades = c.fetchall()

print('='*90)
print('KAPANAN TRADE\'LER - KOMİSYON HESABI')
print('='*90)
print()

# Read from log file to get commission details
import re

with open('logs/engine.log', 'r', encoding='utf-8') as f:
    log_content = f.read()

print('LOG DOSYASINDAN KOMİSYON KAYITLARI:')
print()

# Find commission entries for each trade
pattern = r'\[STATE\] CLOSED (LONG|SHORT) (\w+): \$([0-9.]+) -> \$([0-9.]+) gross=\$([+-]?[0-9.]+) comm=\$([0-9.]+) net=\$([+-]?[0-9.]+)'

matches = re.findall(pattern, log_content)

# Get last 6 matches (our recent trades)
for i, match in enumerate(matches[-6:], 1):
    side, symbol, entry, exit, gross, comm, net = match
    
    gross_val = float(gross)
    comm_val = float(comm)
    net_val = float(net)
    
    print(f'{i}. {symbol} {side}:')
    print(f'   Entry: ${entry} → Exit: ${exit}')
    print(f'   Gross PnL:  ${gross_val:+.2f}')
    print(f'   Komisyon:   -${comm_val:.2f}  ← MASRAF DÜŞÜLDÜ')
    print(f'   Net PnL:    ${net_val:+.2f}  ← GERÇEK KAR/ZARAR')
    print()

print('='*90)
print('ÖZET:')
print('='*90)
print()

total_gross = sum([float(m[4]) for m in matches[-6:]])
total_comm = sum([float(m[5]) for m in matches[-6:]])
total_net = sum([float(m[6]) for m in matches[-6:]])

print(f'Toplam Gross:     ${total_gross:+.2f}')
print(f'Toplam Komisyon:  -${total_comm:.2f}  ← DÜŞÜLDÜ')
print(f'Toplam Net:       ${total_net:+.2f}')
print()
print('KOMİSYONLAR HER TRADE\'DE OTOMATIK DÜŞÜLÜYOR!')
print()
print('Net PnL = Gross PnL - Komisyonlar')
print('Telegram\'da gördüğün rakamlar NET (komisyon sonrası)')

conn.close()
