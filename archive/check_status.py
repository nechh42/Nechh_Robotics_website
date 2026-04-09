"""Quick status check script"""
import sqlite3, os, sys
sys.path.insert(0, '.')

db = "data/war_machine.db"
if not os.path.exists(db):
    print("NO DB"); sys.exit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Full trade dump
print("=== FULL TRADE DUMP ===")
all_trades = c.execute("SELECT * FROM trades ORDER BY id").fetchall()
for t in all_trades:
    d = dict(t)
    for k, v in d.items():
        print(f"  {k}: {v}")
    print("---")

# Tables
print("\n=== TABLES ===")
tbls = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for tbl in tbls:
    name = tbl['name']
    cnt = c.execute(f"SELECT COUNT(*) as c FROM {name}").fetchone()['c']
    print(f"  {name}: {cnt} rows")

# Full positions
print("\n=== FULL POSITIONS ===")
all_pos = c.execute("SELECT * FROM positions").fetchall()
for p in all_pos:
    d = dict(p)
    for k, v in d.items():
        print(f"  {k}: {v}")
    print("---")

# Now do the summary with old logic
trades = c.execute("SELECT timestamp,symbol,side,entry_price,exit_price,net_pnl,reason FROM trades ORDER BY id").fetchall()
pos = c.execute("SELECT symbol,side,entry_price,size,stop_loss,take_profit FROM positions").fetchall()

print(f"=== TRADES: {len(trades)} ===")
wins = []
losses = []
for t in trades:
    pnl = float(t[5] or 0)
    if pnl > 0:
        wins.append(pnl)
    else:
        losses.append(pnl)
    print(f"  {str(t[0])[:16]} {str(t[1]):12} {str(t[2]):5} pnl=${pnl:+.4f} [{str(t[6] or '')[:35]}]")

total_pnl = sum(wins) + sum(losses)
wr = len(wins)/len(trades)*100 if trades else 0
avg_win = sum(wins)/len(wins) if wins else 0
avg_loss = sum(losses)/len(losses) if losses else 0

print(f"\n=== SUMMARY ===")
print(f"  Total PnL: ${total_pnl:.2f}")
print(f"  Win Rate: {wr:.1f}% ({len(wins)}W/{len(losses)}L)")
print(f"  Avg Win: ${avg_win:.2f}")
print(f"  Avg Loss: ${avg_loss:.2f}")

if wins and losses:
    expectancy = (wr/100 * avg_win) + ((1-wr/100) * avg_loss)
    pf = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else 999
    print(f"  Expectancy: ${expectancy:.2f}")
    print(f"  Profit Factor: {pf:.2f}")
    rr = avg_win / abs(avg_loss) if avg_loss != 0 else 999
    print(f"  Risk/Reward: {rr:.2f}")
    roi = total_pnl / 10000 * 100
    print(f"  ROI: {roi:.3f}%")

print(f"\n=== OPEN POSITIONS: {len(pos)} ===")
long_count = 0
short_count = 0
for p in pos:
    side = str(p[1])
    if side == "LONG": long_count += 1
    else: short_count += 1
    print(f"  {str(p[0]):12} {side:5} @${p[2]:.4f} SL=${p[4]:.4f} TP=${p[5]:.4f}")
print(f"  Direction: {long_count}L / {short_count}S")

conn.close()
