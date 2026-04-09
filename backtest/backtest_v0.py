"""
backtest_v0.py — War Machine v0 Basit Backtest
=================================================
Binance'den 4h mum çeker, ScalpV0 stratejisini test eder.
Hiçbir karmaşıklık yok: giriş → SL/TP/MAX_HOLD → çıkış.

Kullanım:
    python -m backtest.backtest_v0          (default 60 gün)
    python -m backtest.backtest_v0 --days 90
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
import requests

import config
from strategies.scalp_v0 import ScalpV0Strategy
from strategies.regime import detect_regime

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Veri İndirme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_candles(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Binance'den OHLCV mum verisi çek."""
    url = "https://api.binance.com/api/v3/klines"
    end_ms = int(datetime.utcnow().timestamp() * 1000)
    start_ms = int((datetime.utcnow() - timedelta(days=days + 10)).timestamp() * 1000)

    all_candles = []
    while start_ms < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "limit": 1000,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        all_candles.extend(data)
        start_ms = data[-1][0] + 1  # sonraki mumdan devam

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df[["time", "open", "high", "low", "close", "volume"]].copy()
    df = df.reset_index(drop=True)
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Trade Kaydı
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class BacktestTrade:
    symbol: str
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    size: float
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    pnl: float = 0.0
    hold_candles: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Backtest Motoru
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_backtest_for_symbol(symbol: str, df: pd.DataFrame, strategy: ScalpV0Strategy) -> List[BacktestTrade]:
    """Tek coin için backtest çalıştır."""
    trades: List[BacktestTrade] = []
    open_trade: Optional[BacktestTrade] = None
    hold_count = 0

    lookback = config.CANDLE_HISTORY_COUNT  # 100 mum geriye bak

    for i in range(lookback, len(df)):
        window = df.iloc[i - lookback:i + 1].copy().reset_index(drop=True)
        current = df.iloc[i]
        price = current["close"]
        high = current["high"]
        low = current["low"]
        candle_time = current["time"]

        # ─── Açık pozisyon var mı? ───
        if open_trade is not None:
            hold_count += 1

            # SL kontrolü (mum içi low ile)
            if low <= open_trade.stop_loss:
                open_trade.exit_price = open_trade.stop_loss
                open_trade.exit_time = candle_time
                open_trade.exit_reason = "STOP-LOSS"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _calc_pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue

            # TP kontrolü (mum içi high ile)
            if high >= open_trade.take_profit:
                open_trade.exit_price = open_trade.take_profit
                open_trade.exit_time = candle_time
                open_trade.exit_reason = "TAKE-PROFIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _calc_pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue

            # MAX_HOLD kontrolü
            if hold_count >= config.MAX_HOLD_CANDLES:
                open_trade.exit_price = price
                open_trade.exit_time = candle_time
                open_trade.exit_reason = "TIME-EXIT"
                open_trade.hold_candles = hold_count
                open_trade.pnl = _calc_pnl(open_trade)
                trades.append(open_trade)
                open_trade = None
                hold_count = 0
                continue

            # Pozisyon açıkken yeni sinyal arama
            continue

        # ─── Yeni sinyal ara ───
        regime = detect_regime(window)

        # Pre-trade basit filtreler (v0: sadece TREND_DOWN ve VOLATILE bloke)
        if regime in ("TREND_DOWN", "VOLATILE"):
            continue

        signal = strategy.evaluate(window, symbol, regime)
        if signal.action != "LONG":
            continue
        if signal.confidence < config.STRATEGY_MIN_CONFIDENCE:
            continue

        # Pozisyon boyutu (basit: equity %1 risk / SL mesafesi)
        atr = signal.atr
        rr = config.DYNAMIC_RR.get(regime, {"sl": 1.0, "tp": 1.0})
        sl_dist = atr * rr["sl"]
        tp_dist = atr * rr["tp"]

        # Minimum SL mesafesi
        min_sl = price * 0.005
        if sl_dist < min_sl:
            scale = min_sl / sl_dist
            sl_dist = min_sl
            tp_dist *= scale

        sl_price = price - sl_dist
        tp_price = price + tp_dist

        # Pozisyon boyutu
        equity = 10000.0  # Sabit equity (basitlik)
        risk_amount = equity * config.RISK_BASE_PCT
        size_by_risk = risk_amount / sl_dist
        size_by_notional = (equity * config.MAX_NOTIONAL_PCT) / price
        size = min(size_by_risk, size_by_notional)

        open_trade = BacktestTrade(
            symbol=symbol,
            entry_price=price,
            entry_time=candle_time,
            stop_loss=sl_price,
            take_profit=tp_price,
            size=size,
        )
        hold_count = 0

    # Açık kalan pozisyonu kapat
    if open_trade is not None:
        last = df.iloc[-1]
        open_trade.exit_price = last["close"]
        open_trade.exit_time = last["time"]
        open_trade.exit_reason = "BACKTEST-END"
        open_trade.hold_candles = hold_count
        open_trade.pnl = _calc_pnl(open_trade)
        trades.append(open_trade)

    return trades


def _calc_pnl(trade: BacktestTrade) -> float:
    """Net PnL (komisyon dahil)."""
    gross = (trade.exit_price - trade.entry_price) * trade.size
    commission = trade.entry_price * trade.size * config.COMMISSION_RATE * 2  # giriş + çıkış
    return gross - commission


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Sonuç Raporu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_results(all_trades: List[BacktestTrade], days: int):
    """Backtest sonuçlarını yazdır."""
    if not all_trades:
        print("\n❌ HİÇ TRADE AÇILMADI — strateji koşulları hiç sağlanmadı.")
        return

    total_pnl = sum(t.pnl for t in all_trades)
    winners = [t for t in all_trades if t.pnl > 0]
    losers = [t for t in all_trades if t.pnl <= 0]
    win_rate = len(winners) / len(all_trades) * 100

    gross_profit = sum(t.pnl for t in winners) if winners else 0
    gross_loss = abs(sum(t.pnl for t in losers)) if losers else 0.001
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = gross_profit / len(winners) if winners else 0
    avg_loss = gross_loss / len(losers) if losers else 0

    # Çıkış nedeni dağılımı
    exit_counts = {}
    exit_pnl = {}
    for t in all_trades:
        r = t.exit_reason
        exit_counts[r] = exit_counts.get(r, 0) + 1
        exit_pnl[r] = exit_pnl.get(r, 0) + t.pnl

    # Coin başına sonuçlar
    coin_stats = {}
    for t in all_trades:
        if t.symbol not in coin_stats:
            coin_stats[t.symbol] = {"trades": 0, "pnl": 0, "wins": 0}
        coin_stats[t.symbol]["trades"] += 1
        coin_stats[t.symbol]["pnl"] += t.pnl
        if t.pnl > 0:
            coin_stats[t.symbol]["wins"] += 1

    # Max drawdown hesabı
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted(all_trades, key=lambda x: x.entry_time):
        cumulative += t.pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    print("\n" + "=" * 60)
    print(f"  WAR MACHINE v0 BACKTEST — {days} GÜN")
    print("=" * 60)
    print(f"  Toplam Trade   : {len(all_trades)}")
    print(f"  Kazanan        : {len(winners)} ({win_rate:.1f}%)")
    print(f"  Kaybeden       : {len(losers)} ({100-win_rate:.1f}%)")
    print(f"  Toplam PnL     : ${total_pnl:+.2f}")
    print(f"  Profit Factor  : {profit_factor:.2f}")
    print(f"  Ort. Kazanç    : ${avg_win:.2f}")
    print(f"  Ort. Kayıp     : ${avg_loss:.2f}")
    print(f"  Max Drawdown   : ${max_dd:.2f}")
    print("-" * 60)

    print("\n  ÇIKİŞ NEDENLERİ:")
    for reason in sorted(exit_counts.keys()):
        cnt = exit_counts[reason]
        pnl = exit_pnl[reason]
        print(f"    {reason:15s}: {cnt:4d} trade | ${pnl:+8.2f}")

    print("\n  COİN BAZLI:")
    for sym in sorted(coin_stats.keys()):
        s = coin_stats[sym]
        wr = s["wins"] / s["trades"] * 100 if s["trades"] > 0 else 0
        print(f"    {sym:12s}: {s['trades']:3d} trade | WR={wr:5.1f}% | ${s['pnl']:+8.2f}")

    print("\n" + "=" * 60)

    # ─── KARAR ───
    print("\n  📊 KARAR:")
    if profit_factor >= 1.0 and win_rate >= 45:
        print(f"  ✅ GEÇTI — PF={profit_factor:.2f} (≥1.0) & WR={win_rate:.1f}% (≥45%)")
        print("  → Paper trading'e geçilebilir!")
    else:
        reasons = []
        if profit_factor < 1.0:
            reasons.append(f"PF={profit_factor:.2f} (<1.0)")
        if win_rate < 45:
            reasons.append(f"WR={win_rate:.1f}% (<45%)")
        print(f"  ❌ KALDI — {', '.join(reasons)}")
        print("  → Edge yok. Strateji değiştirilmeli veya proje durdurulmalı.")

    print("=" * 60)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ana Fonksiyon
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(description="War Machine v0 Backtest")
    parser.add_argument("--days", type=int, default=60, help="Kaç günlük veri (default: 60)")
    parser.add_argument("--max-hold", type=int, default=None, help="MAX_HOLD_CANDLES override")
    parser.add_argument("--sl", type=float, default=None, help="SL ATR multiplier override")
    parser.add_argument("--tp", type=float, default=None, help="TP ATR multiplier override")
    parser.add_argument("--label", type=str, default="", help="Test etiketi")
    args = parser.parse_args()

    days = args.days

    # CLI override'lar
    if args.max_hold is not None:
        config.MAX_HOLD_CANDLES = args.max_hold
    if args.sl is not None or args.tp is not None:
        sl_val = args.sl if args.sl is not None else 1.0
        tp_val = args.tp if args.tp is not None else 1.0
        for regime in config.DYNAMIC_RR:
            config.DYNAMIC_RR[regime] = {"sl": sl_val, "tp": tp_val}

    symbols = config.SYMBOLS
    strategy = ScalpV0Strategy()

    label = f" [{args.label}]" if args.label else ""
    rr_info = config.DYNAMIC_RR.get("RANGING", {"sl": 1.0, "tp": 1.0})

    print(f"\n🔍 War Machine v0 Backtest{label} başlıyor...")
    print(f"   Periyot: {days} gün | Interval: {config.CANDLE_INTERVAL}")
    print(f"   Coinler: {', '.join(symbols)}")
    print(f"   SL/TP: {rr_info['sl']}x ATR / {rr_info['tp']}x ATR | MAX_HOLD: {config.MAX_HOLD_CANDLES} candle")
    print(f"   Min Confidence: {config.STRATEGY_MIN_CONFIDENCE}")

    all_trades: List[BacktestTrade] = []

    for sym in symbols:
        print(f"\n   📥 {sym} veri çekiliyor...", end=" ", flush=True)
        try:
            df = fetch_candles(sym, config.CANDLE_INTERVAL, days)
            if df.empty or len(df) < config.CANDLE_HISTORY_COUNT + 10:
                print(f"yetersiz veri ({len(df)} mum)")
                continue
            print(f"{len(df)} mum", end=" → ", flush=True)
            trades = run_backtest_for_symbol(sym, df, strategy)
            print(f"{len(trades)} trade")
            all_trades.extend(trades)
        except Exception as e:
            print(f"HATA: {e}")

    print_results(all_trades, days)

    # Sonuçları dosyaya kaydet
    if all_trades:
        result_file = os.path.join(os.path.dirname(__file__), "backtest_v0_results.txt")
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(f"War Machine v0 Backtest — {days} gün\n")
            f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"Coinler: {', '.join(symbols)}\n\n")
            total_pnl = sum(t.pnl for t in all_trades)
            winners = [t for t in all_trades if t.pnl > 0]
            wr = len(winners) / len(all_trades) * 100
            gp = sum(t.pnl for t in winners) if winners else 0
            gl = abs(sum(t.pnl for t in all_trades if t.pnl <= 0)) or 0.001
            pf = gp / gl
            f.write(f"Trades: {len(all_trades)}\n")
            f.write(f"Win Rate: {wr:.1f}%\n")
            f.write(f"PnL: ${total_pnl:+.2f}\n")
            f.write(f"Profit Factor: {pf:.2f}\n\n")
            f.write("Trade Detayları:\n")
            f.write("-" * 100 + "\n")
            for t in sorted(all_trades, key=lambda x: x.entry_time):
                f.write(
                    f"{t.entry_time.strftime('%m/%d %H:%M')} | {t.symbol:12s} | "
                    f"${t.entry_price:>10.4f} → ${t.exit_price:>10.4f} | "
                    f"PnL=${t.pnl:>+8.2f} | {t.exit_reason:12s} | {t.hold_candles}c\n"
                )
        print(f"\n📄 Detaylar kaydedildi: {result_file}")


if __name__ == "__main__":
    main()
