import config
from risk.pre_trade import PreTradeRisk
from engine.signal import Signal
from engine.state import TradingState

risk = PreTradeRisk()
state = TradingState()

print('='*70)
print('FIX DOGRULAMA -- Dynamic R:R artik dogru calismali')
print('='*70)

# SENARYO 1: BTC TREND_UP 4h -- ATR 500, price 69000
print()
print('--- BTC TREND_UP 4h (ATR=500) ---')
sig = Signal(symbol='BTCUSDT', action='LONG', confidence=0.7, reason='t', strategy='VOTE', price=69000.0, atr=500.0)
ok, _, p = risk.check(sig, state, 'TREND_UP')
sl_d = 69000 - p['stop_loss']
tp_d = p['take_profit'] - 69000
rr = tp_d / sl_d
expected_rr = 4.0 / 1.5
print(f'  SL dist:  ({sl_d/69000*100:.2f}%)')
print(f'  TP dist:  ({tp_d/69000*100:.2f}%)')
print(f'  R:R: {rr:.2f}:1 (beklenen: {expected_rr:.2f}:1)')
print(f'  TP1:  (TP nin %50 si)')
status = 'PASS' if abs(rr - expected_rr) < 0.01 else 'FAIL'
print(f'  [{status}]')

# SENARYO 2: SOL RANGING 4h -- ATR 1.2, price 82
print()
print('--- SOL RANGING 4h (ATR=1.2) ---')
state2 = TradingState()
sig2 = Signal(symbol='SOLUSDT', action='LONG', confidence=0.6, reason='t', strategy='VOTE', price=82.0, atr=1.2)
ok2, _, p2 = PreTradeRisk().check(sig2, state2, 'RANGING')
sl_d2 = 82 - p2['stop_loss']
tp_d2 = p2['take_profit'] - 82
rr2 = tp_d2 / sl_d2
expected_rr2 = 1.5 / 1.0
print(f'  SL dist:  ({sl_d2/82*100:.2f}%)')
print(f'  TP dist:  ({tp_d2/82*100:.2f}%)')
print(f'  R:R: {rr2:.2f}:1 (beklenen: {expected_rr2:.2f}:1)')
print(f'  TP1: ')
status2 = 'PASS' if abs(rr2 - expected_rr2) < 0.01 else 'FAIL'
print(f'  [{status2}]')

# SENARYO 3: SOL RANGING 1h -- ATR 0.6, price 82
print()
print('--- SOL RANGING 1h (ATR=0.6, %50 size) ---')
state3 = TradingState()
sig3 = Signal(symbol='SOLUSDT', action='LONG', confidence=0.6, reason='t', strategy='VOTE', price=82.0, atr=0.6)
ok3, _, p3 = PreTradeRisk().check(sig3, state3, 'RANGING')
if p3:
    p3['size'] *= 0.50
    sl_d3 = 82 - p3['stop_loss']
    tp_d3 = p3['take_profit'] - 82
    rr3 = tp_d3 / sl_d3
    expected_rr3 = 1.5 / 1.0
    print(f'  SL dist:  ({sl_d3/82*100:.2f}%) -- artik floor yok!')
    print(f'  TP dist:  ({tp_d3/82*100:.2f}%)')
    print(f'  R:R: {rr3:.2f}:1 (beklenen: {expected_rr3:.2f}:1)')
    print(f'  Size: {p3["size"]:.4f} SOL = ')
    status3 = 'PASS' if abs(rr3 - expected_rr3) < 0.01 else 'FAIL'
    print(f'  [{status3}]')

# SENARYO 4: Cok dusuk ATR -- floor aktif olmali
print()
print('--- XRP AZ VOL (ATR=0.002, price=2.0) -- floor testi ---')
state4 = TradingState()
sig4 = Signal(symbol='XRPUSDT', action='LONG', confidence=0.7, reason='t', strategy='VOTE', price=2.0, atr=0.002)
ok4, _, p4 = PreTradeRisk().check(sig4, state4, 'TREND_UP')
if p4:
    sl_d4 = 2.0 - p4['stop_loss']
    tp_d4 = p4['take_profit'] - 2.0
    rr4 = tp_d4 / sl_d4
    expected_rr4 = 4.0 / 1.5
    print(f'  ATR-based SL: ')
    print(f'  Floor SL (0.5%): ')
    print(f'  ACTUAL SL dist: ')
    print(f'  TP dist: ')
    print(f'  R:R: {rr4:.2f}:1 (beklenen: {expected_rr4:.2f}:1 -- korunmali!)')
    floor_used = sl_d4 >= 2.0 * 0.005
    print(f'  Floor aktif: {floor_used}')
    status4 = 'PASS' if abs(rr4 - expected_rr4) < 0.01 and floor_used else 'FAIL'
    print(f'  [{status4}]')

# SENARYO 5: SHORT yon testi
print()
print('--- ETH TREND_DOWN SHORT (ATR=50, price=3500) ---')
state5 = TradingState()
sig5 = Signal(symbol='ETHUSDT', action='SHORT', confidence=0.7, reason='t', strategy='VOTE', price=3500.0, atr=50.0)
ok5, r5, p5 = PreTradeRisk().check(sig5, state5, 'TREND_DOWN')
if p5:
    sl_d5 = p5['stop_loss'] - 3500
    tp_d5 = 3500 - p5['take_profit']
    rr5 = tp_d5 / sl_d5
    expected_rr5 = 4.0 / 1.5
    print(f'  SL:  (entry+)')
    print(f'  TP:  (entry-)')
    print(f'  R:R: {rr5:.2f}:1 (beklenen: {expected_rr5:.2f}:1)')
    status5 = 'PASS' if abs(rr5 - expected_rr5) < 0.01 else 'FAIL'
    print(f'  [{status5}]')
else:
    print(f'  REJECTED: {r5}')
    cond = getattr(config, 'ALLOW_SHORT_CONDITIONAL', False) or config.ALLOW_SHORT
    print(f'  (SHORT allowed? ALLOW_SHORT={config.ALLOW_SHORT}, CONDITIONAL={getattr(config, "ALLOW_SHORT_CONDITIONAL", False)})')
    status5 = 'INFO'

# SENARYO 6: VOLATILE -- reddedilmeli
print()
print('--- VOLATILE rejimi -- reddedilmeli ---')
state6 = TradingState()
sig6 = Signal(symbol='BTCUSDT', action='LONG', confidence=0.9, reason='t', strategy='VOTE', price=69000.0, atr=1500.0)
ok6, r6, p6 = PreTradeRisk().check(sig6, state6, 'VOLATILE')
status6 = 'PASS' if not ok6 else 'FAIL'
print(f'  OK={ok6}, Reason={r6} [{status6}]')

# OZET
print()
print('='*70)
print('SONUC OZETI')
print('='*70)
results = [('BTC TREND_UP 4h R:R', status), ('SOL RANGING 4h R:R', status2),
           ('SOL RANGING 1h R:R', status3), ('XRP low ATR floor', status4),
           ('ETH SHORT dir', status5), ('VOLATILE reject', status6)]
all_pass = all(s in ('PASS','INFO') for _,s in results)
for name, st in results:
    icon = 'OK' if st in ('PASS','INFO') else 'XX'
    print(f'  [{icon}] {name}: {st}')
print(f'  GENEL: {"HEPSI GECTI" if all_pass else "BAZI TESTLER BASARISIZ!"}')
