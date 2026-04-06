import sqlite3
conn = sqlite3.connect('data/war_machine.db')

# Tablolar
print("=== TABLOLAR ===")
for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(t[0])

# Kapanan tradeler
print("\n=== KAPALI TRADELER ===")
trades = conn.execute("SELECT * FROM trades ORDER BY rowid DESC").fetchall()
if not trades:
    print("(HİÇ KAPALI TRADE YOK)")
else:
    for r in trades:
        print(r)

# Açık pozisyonlar
print("\n=== AÇIK POZİSYONLAR ===")
for r in conn.execute("SELECT symbol, side, entry_price, size, stop_loss, take_profit, entry_time, strategy FROM positions ORDER BY entry_time").fetchall():
    print(f"  {r[0]:12s} {r[1]:5s} @ ${r[2]:.6f} | SL=${r[4]:.6f} TP=${r[5]:.6f} | {r[6]} | {r[7]}")

# Journal entries
print("\n=== JOURNAL ===")
try:
    for r in conn.execute("SELECT * FROM trade_journal ORDER BY rowid DESC LIMIT 20").fetchall():
        print(r)
except:
    print("(trade_journal tablosu yok)")

# Adaptive weights
print("\n=== ADAPTIVE WEIGHTS ===")
try:
    for r in conn.execute("SELECT * FROM adaptive_weights ORDER BY rowid DESC LIMIT 10").fetchall():
        print(r)
except:
    print("(adaptive_weights tablosu yok)")

conn.close()
