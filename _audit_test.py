import config
from risk.pre_trade import PreTradeRisk
from engine.signal import Signal
from engine.state import TradingState

risk = PreTradeRisk()
state = TradingState()

print('='*70)
print('SENARYO 1: BTC TREND_UP - 4h trade')
print('='*70)
sig = Signal(symbol='BTCUSDT', action='LONG', confidence=0.7, reason='test', strategy='VOTE', price=69000.0, atr=500.0)
ok, reason, params = risk.check(sig, state, 'TREND_UP')
if params:
    print(f'  Entry: ${params["price"]:.2f}')
    print(f'  SL: ${params["stop_loss"]:.2f} (mesafe: ${69000-params["stop_loss"]:.2f} = {(69000-params["stop_loss"])/69000*100:.2f}%)')
    print(f'  TP1: ${params["take_profit_1"]:.2f} (mesafe: ${params["take_profit_1"]-69000:.2f})')
    print(f'  TP2: ${params["take_profit"]:.2f} (mesafe: ${params["take_profit"]-69000:.2f} = {(params["take_profit"]-69000)/69000*100:.2f}%)')
    print(f'  R:R = {(params["take_profit"]-69000)/(69000-params["stop_loss"]):.2f}:1')
    print(f'  Size: {params["size"]:.6f} BTC = ${params["size"]*69000:.2f} notional')
    print(f'  ATR: ${params["atr"]:.2f}')
    print(f'  Breakeven trigger: ${params["atr"]*1.0:.2f} profit -> SL moves to entry')
    print(f'  Partial TP1 at: ${params["take_profit_1"]:.2f} -> close 50% -> SL to entry')
else:
    print(f'  REJECTED: {reason}')

print()
print('='*70)
print('SENARYO 2: SOL RANGING - 4h trade')
print('='*70)
sig2 = Signal(symbol='SOLUSDT', action='LONG', confidence=0.6, reason='test', strategy='VOTE', price=82.0, atr=1.2)
ok2, reason2, params2 = risk.check(sig2, state, 'RANGING')
if params2:
    print(f'  Entry: ${params2["price"]:.2f}')
    print(f'  SL: ${params2["stop_loss"]:.4f} (mesafe: ${82-params2["stop_loss"]:.4f} = {(82-params2["stop_loss"])/82*100:.2f}%)')
    print(f'  TP1: ${params2["take_profit_1"]:.4f} (mesafe: ${params2["take_profit_1"]-82:.4f})')
    print(f'  TP2: ${params2["take_profit"]:.4f} (mesafe: ${params2["take_profit"]-82:.4f} = {(params2["take_profit"]-82)/82*100:.2f}%)')
    print(f'  R:R = {(params2["take_profit"]-82)/(82-params2["stop_loss"]):.2f}:1')
    print(f'  Size: {params2["size"]:.4f} SOL = ${params2["size"]*82:.2f} notional')
    print(f'  ATR: ${params2["atr"]:.4f}')
    print(f'  Breakeven trigger: ${params2["atr"]*1.0:.4f} profit -> SL moves to entry')
    print(f'  Min SL floor: ${82*0.015:.4f} vs ATR-based: ${1.2*1.0:.4f}')
    tp1_hours_est = (params2['take_profit_1']-82) / (1.2/4)
    print(f'  Tahmini TP1 suresi: ~{tp1_hours_est:.1f} saat (rough)')
else:
    print(f'  REJECTED: {reason2}')

print()
print('='*70)
print('SENARYO 3: SOL RANGING - 1h trade (size 50% kucuk)')
print('='*70)
sig3 = Signal(symbol='SOLUSDT', action='LONG', confidence=0.6, reason='test', strategy='VOTE', price=82.0, atr=0.6)
state3 = TradingState()
ok3, reason3, params3 = PreTradeRisk().check(sig3, state3, 'RANGING')
if params3:
    params3['size'] *= 0.50
    print(f'  Entry: ${params3["price"]:.2f}')
    sl_d = 82 - params3['stop_loss']
    tp_d = params3['take_profit'] - 82
    print(f'  ATR-based SL dist: ${0.6*1.0:.4f}')
    print(f'  Min SL floor (1.5%): ${82*0.015:.4f}')
    print(f'  ACTUAL SL dist: ${sl_d:.4f} (which was used?)')
    print(f'  SL: ${params3["stop_loss"]:.4f} ({sl_d/82*100:.2f}%)')
    print(f'  TP1: ${params3["take_profit_1"]:.4f}')
    print(f'  TP2: ${params3["take_profit"]:.4f} ({tp_d/82*100:.2f}%)')
    print(f'  R:R = {tp_d/sl_d:.2f}:1')
    print(f'  Size: {params3["size"]:.4f} SOL = ${params3["size"]*82:.2f} notional')
    if sl_d > 0.6:
        print(f'  WARNING: MIN SL FLOOR ATR BAZLI SL yi EZDI! 0.60 vs {sl_d:.4f}')
        print(f'  -> R:R BOZULMUS! Beklenen 1.5:1, Gercek: {tp_d/sl_d:.2f}:1')
else:
    print(f'  REJECTED: {reason3}')

print()
print('='*70)
print('SENARYO 4: Funding Fee hesaplama')
print('='*70)
notional = 500
fee_8h = notional * config.FUNDING_FEE_RATE
fee_24h = fee_8h * 3
print(f'  Notional: ${notional}')
print(f'  Fee per 8h: ${fee_8h:.4f}')
print(f'  Fee per 24h: ${fee_24h:.4f}')
print(f'  Fee per 7 days: ${fee_24h*7:.4f}')
print(f'  % of notional per day: {fee_24h/notional*100:.4f}%')

print()
print('='*70)
print('SENARYO 5: Breakeven + Partial TP siralaması dogruluk testi')
print('='*70)
from risk.stop_manager import check_exit
from engine.state import Position
from datetime import datetime

pos = Position('BTCUSDT', 'LONG', 0.01, 69000, datetime.now(), 67770, 71000)
pos.take_profit_1 = 70000
pos._entry_atr = 500

r1 = check_exit(pos, 69500)
print(f'  @ $69500 (1xATR profit): exit={r1}, SL now=${pos.stop_loss:.2f}, BE={pos._breakeven_applied}')

r2 = check_exit(pos, 70000)
print(f'  @ $70000 (TP1): exit={r2}, partial_closed={pos._partial_closed}')

pos._partial_closed = True
pos.stop_loss = 69000

r3 = check_exit(pos, 69500)
print(f'  @ $69500 (after partial, price drops): exit={r3}, SL=${pos.stop_loss:.2f}')

r4 = check_exit(pos, 69000)
print(f'  @ $69000 (at entry/BE): exit={r4}')

r5 = check_exit(pos, 71000)
print(f'  @ $71000 (TP2): exit={r5}')

print()
print('AUDIT COMPLETE')
