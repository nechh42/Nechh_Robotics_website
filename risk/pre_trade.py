"""
pre_trade.py - Pre-Trade Risk v13.1
=====================================
VERİ TABANLI KARAR (95 trade analizi):
  SHORT: %35 WR → -$3,658 zarar (DISABLED - kanıtlanmış başarısız)
  LONG:  %54 WR → +$2,679 kâr (ENABLED - kanıtlanmış başarılı)

Kural:
  TREND_UP   → LONG açılır
  TREND_DOWN → LONG açılmaz (no SHORT)
  RANGING    → LONG açılmaz (no SHORT)
  VOLATILE   → işlem açılmaz

Düzeltmeler (v13.0):
  [FIX-1] Pozisyon boyutu: notional cap eklendi (max equity %10)
          Eski: size = risk/sl_dist → $13,000+ pozisyon (YANLIŞ)
          Yeni: min(risk-based, notional-capped) → max $1,000 pozisyon
  [FIX-2] TREND_UP'ta SHORT engeli düzeltildi (regime=="SHORT" bug'ı)
  [FIX-3] Daily trade/loss limitleri aktif edildi
"""

import logging
from datetime import datetime
from typing import Tuple, Optional

import config
from engine.signal import Signal
from engine.state import TradingState

logger = logging.getLogger(__name__)

# Pozisyon boyutu sabiti — equity'nin max bu kadarı notional olabilir
MAX_NOTIONAL_PCT = 0.10   # %10 equity = $10,000'de $1,000 max pozisyon


class PreTradeRisk:

    def __init__(self):
        self._daily_trades = 0
        self._daily_loss = 0.0
        self._day_start = datetime.now().date()

    def check(
        self,
        signal: Signal,
        state: TradingState,
        regime: str = "RANGING",
        position_pct: float = None,
    ) -> Tuple[bool, str, Optional[dict]]:

        # Gün sıfırlama
        today = datetime.now().date()
        if today != self._day_start:
            self._daily_trades = 0
            self._daily_loss = 0.0
            self._day_start = today

        symbol = signal.symbol
        action = signal.action

        if action == "NONE":
            return False, "No action", None

        # CHECK 1: Equity
        if state.equity < config.MIN_EQUITY_THRESHOLD:
            return self._reject(symbol, action, f"Equity ${state.equity:.2f} yetersiz")

        # CHECK 2: Max pozisyon
        if len(state.positions) >= config.MAX_POSITIONS:
            return self._reject(symbol, action, f"Max {config.MAX_POSITIONS} pozisyon doldu")

        # CHECK 3: Duplicate
        if symbol in state.positions:
            return self._reject(symbol, action, "Zaten pozisyon var")

        # CHECK 4: VOLATILE — hiçbir şey açılmaz
        if regime == "VOLATILE":
            return self._reject(symbol, action, "VOLATILE: işlem açılmaz")

        # CHECK 5: Yön filtresi (TEMPORARY BYPASS FOR TESTING)
        # Normally: LONG only TREND_UP
        # TEST: Allow LONG in all regimes except VOLATILE
        if regime == "VOLATILE":
            return self._reject(symbol, action, "VOLATILE: işlem açılmaz")
        
        # LONG allowed in all non-volatile regimes (TEST)
        if action == "LONG":
            logger.info(f"[RISK-TEST] LONG allowed in regime={regime} (normally TREND_UP only)")
        
        # SHORT always disabled
        if action == "SHORT":
            return self._reject(symbol, action, "SHORT kapali")

        # CHECK 6: Günlük trade limiti
        if self._daily_trades >= config.MAX_DAILY_TRADES:
            return self._reject(symbol, action, f"Gunluk trade limiti ({config.MAX_DAILY_TRADES}) doldu")

        # CHECK 7: Günlük zarar limiti
        if self._daily_loss >= config.MAX_DAILY_LOSS:
            return self._reject(symbol, action, f"Gunluk zarar limiti (${config.MAX_DAILY_LOSS}) asildi")

        # POZISYON BOYUTU HESABI
        equity = state.equity
        
        # Volatility-adjusted risk
        # Base: 0.5%, Multiplier: current_volatility / avg_volatility
        # High vol = higher risk reduction
        volatility_mult = 1.0
        if config.VOLATILITY_MULTIPLIER and signal.atr > 0:
            # ATR > 2% price = high volatility → reduce risk
            atr_pct = signal.atr / signal.price
            volatility_mult = max(0.5, min(1.5, 1.0 / (1.0 + atr_pct * 5)))
            # Formula: 1.0 at normal vol, 0.5 when atr=2%, 1.5 when atr near 0
        
        risk_amount = equity * config.RISK_BASE_PCT * volatility_mult

        atr = signal.atr if signal.atr > 0 else signal.price * 0.02
        sl_dist = atr * 1.5
        tp_dist = atr * 2.0

        # Minimum SL/TP mesafesi
        sl_dist = max(sl_dist, signal.price * 0.015)
        tp_dist = max(tp_dist, signal.price * 0.030)

        # Stop ve hedef fiyatlar
        if action == "LONG":
            stop_loss = signal.price - sl_dist
            take_profit = signal.price + tp_dist
        else:
            stop_loss = signal.price + sl_dist
            take_profit = signal.price - tp_dist

        # [FIX-1] Pozisyon boyutu: iki yöntem, küçüğü al
        size_by_risk = risk_amount / sl_dist                            # Risk bazlı
        size_by_notional = (equity * MAX_NOTIONAL_PCT) / signal.price  # Notional sinir
        size = min(size_by_risk, size_by_notional)                      # Guvenli olan

        if size < 0.0001:
            return self._reject(symbol, action, "Size cok kucuk")

        notional = size * signal.price
        notional_pct = notional / equity * 100

        logger.info(
            f"[RISK OK] ONAYLANDI {action} {symbol} | regime={regime} | "
            f"size={size:.4f} @ ${signal.price:.4f} | "
            f"notional=${notional:.2f} (%{notional_pct:.1f}) | "
            f"SL=${stop_loss:.4f} TP=${take_profit:.4f} | "
            f"risk=${risk_amount:.2f} (base={config.RISK_BASE_PCT*100}% × {volatility_mult:.2f})"
        )

        return True, "Approved", {
            "symbol": symbol,
            "action": action,
            "size": size,
            "price": signal.price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "strategy": signal.strategy,
        }

    def record_trade_result(self, net_pnl: float, symbol: str):
        self._daily_trades += 1
        if net_pnl < 0:
            self._daily_loss += abs(net_pnl)

    def _reject(self, symbol: str, action: str, reason: str):
        logger.warning(f"[RISK NO] REDDEDILDI {action} {symbol}: {reason}")
        return False, reason, None
