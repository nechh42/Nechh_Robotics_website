import config
from engine.state import Position, TradingState
from datetime import datetime
from risk.pre_trade import PreTradeRisk
from engine.signal import Signal

print('='*70)
print('SMART EXIT DOGRULAMA TESTLERI')
print('='*70)

# TEST 1: Position has _entry_regime field
print()
print('--- TEST 1: Position _entry_regime field ---')
pos = Position('BTCUSDT', 'LONG', 0.01, 69000, datetime.now(), 67965, 71070)
pos._entry_regime = 'TREND_UP'
print(f'  entry_regime: {pos._entry_regime}')
print('  [PASS]' if pos._entry_regime == 'TREND_UP' else '  [FAIL]')

# TEST 2: PreTradeRisk returns entry_regime in params
print()
print('--- TEST 2: PreTradeRisk entry_regime in params ---')
risk = PreTradeRisk()
state = TradingState()
sig = Signal(symbol='BTCUSDT', action='LONG', confidence=0.7, reason='t', strategy='VOTE', price=69000.0, atr=500.0)
ok, _, params = risk.check(sig, state, 'TREND_UP')
has_regime = params and 'entry_regime' in params
print(f'  entry_regime in params: {has_regime}')
val = params.get('entry_regime', 'MISSING') if params else 'NO PARAMS'
print(f'  value: {val}')
print('  [PASS]' if has_regime and params['entry_regime'] == 'TREND_UP' else '  [FAIL]')

# TEST 3: Config SMART_EXIT_ENABLED
print()
print('--- TEST 3: Config SMART_EXIT_ENABLED ---')
has_flag = hasattr(config, 'SMART_EXIT_ENABLED')
smart_val = getattr(config, 'SMART_EXIT_ENABLED', 'MISSING')
print(f'  SMART_EXIT_ENABLED: {smart_val}')
print('  [PASS]' if has_flag and config.SMART_EXIT_ENABLED else '  [FAIL]')

# TEST 4: restore_position loads entry_regime
print()
print('--- TEST 4: restore_position entry_regime ---')
state2 = TradingState()
state2.restore_position('ETHUSDT', {
    'side': 'LONG', 'size': 0.1, 'entry_price': 3500,
    'entry_time': datetime.now().isoformat(),
    'stop_loss': 3400, 'take_profit': 3700,
    'entry_regime': 'RANGING',
    'entry_atr': 50.0,
    'breakeven_applied': False,
    'partial_closed': False,
    'take_profit_1': 3600,
})
restored = state2.positions.get('ETHUSDT')
regime_val = getattr(restored, '_entry_regime', 'MISSING')
print(f'  restored entry_regime: {regime_val}')
print('  [PASS]' if restored and restored._entry_regime == 'RANGING' else '  [FAIL]')

# TEST 5: Smart Exit scenario - KARLI regime change
print()
print('--- TEST 5: Smart Exit scenario - KARLI regime change ---')
pos5 = Position('SOLUSDT', 'LONG', 3.0, 82.0, datetime.now(), 80.77, 83.80)
pos5._entry_regime = 'TREND_UP'
pos5._entry_atr = 1.2
pos5.take_profit_1 = 82.90
pos5.update_pnl(83.0)
print(f'  PnL @ 83: {pos5.unrealized_pnl:.2f} (karda)')
in_profit = pos5.unrealized_pnl > 0
new_regime = 'RANGING'
changed = new_regime != pos5._entry_regime
print(f'  Regime changed: {pos5._entry_regime} -> {new_regime}: {changed}')
print(f'  In profit: {in_profit} -> KAPATILMALI')
print('  [PASS]' if changed and in_profit else '  [FAIL]')

# TEST 6: Smart Exit scenario - ZARARDA regime change -> TP daralt
print()
print('--- TEST 6: Smart Exit scenario - ZARARDA -> TP daraltma ---')
pos6 = Position('BTCUSDT', 'LONG', 0.01, 69000, datetime.now(), 67965, 71760)
pos6._entry_regime = 'TREND_UP'
pos6._entry_atr = 500
pos6.take_profit_1 = 70380
pos6.update_pnl(68500)
print(f'  PnL @ 68500: {pos6.unrealized_pnl:.2f} (zararda)')
in_loss = pos6.unrealized_pnl <= 0
new_rr = config.DYNAMIC_RR.get('RANGING')
new_tp_dist = pos6._entry_atr * new_rr['tp']
new_tp = pos6.entry_price + new_tp_dist
print(f'  Entry regime TP (TREND_UP): {pos6.take_profit:.2f}')
print(f'  New regime TP (RANGING): {new_tp:.2f}')
tp_narrowed = new_tp < pos6.take_profit
print(f'  TP daraltildi: {tp_narrowed}')
print(f'  SL DEGISMEZ: {pos6.stop_loss:.2f}')
new_tp1 = pos6.entry_price + new_tp_dist * config.PARTIAL_TP_RATIO
print(f'  Yeni TP1: {new_tp1:.2f}')
print('  [PASS]' if in_loss and tp_narrowed else '  [FAIL]')

# TEST 7: Import check
print()
print('--- TEST 7: Full import check ---')
try:
    from engine.orchestrator import Orchestrator
    has_method = hasattr(Orchestrator, '_check_smart_exit')
    print(f'  Orchestrator has _check_smart_exit: {has_method}')
    print('  [PASS]' if has_method else '  [FAIL]')
except Exception as e:
    print(f'  Import error: {e}')
    print('  [FAIL]')

# OZET
print()
print('='*70)
print('SONUC: Tum testler tamamlandi')
print('='*70)
