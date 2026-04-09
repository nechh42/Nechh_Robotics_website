"""
deep_analysis.py — WR %50+ hedefi için derin analiz
=====================================================
Mevcut backtest sonuçlarını analiz eder, zayıf noktaları bulur,
ve hangi ayarların WR'yi yükselteceğini test eder.
"""
import sys, os, json
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from backtest.backtest_v3 import BacktestV3

def run_baseline():
    """Mevcut ayarlarla backtest çalıştır ve trade listesi döndür"""
    bt = BacktestV3()
    result = bt.run(days=60)
    return result

def analyze_trades(trades):
    """Trade listesini derinlemesine analiz et"""
    if not trades:
        print("Trade yok!")
        return

    print("\n" + "="*70)
    print("DERİN ANALİZ — WR %50+ HEDEFİ İÇİN KIRILIM")
    print("="*70)

    # 1. Exit reason breakdown with WR
    print(f"\n{'─'*60}")
    print("1. ÇIKIŞ NEDENİ BAZLI WR ve PnL")
    print(f"{'─'*60}")
    reasons = {}
    for t in trades:
        r = t.reason.split(":")[0].strip()
        if r not in reasons:
            reasons[r] = {"wins": 0, "losses": 0, "pnl": 0, "trades": []}
        if t.net_pnl > 0:
            reasons[r]["wins"] += 1
        else:
            reasons[r]["losses"] += 1
        reasons[r]["pnl"] += t.net_pnl
        reasons[r]["trades"].append(t)

    for r, d in sorted(reasons.items(), key=lambda x: -len(x[1]["trades"])):
        total = d["wins"] + d["losses"]
        wr = d["wins"] / total * 100 if total > 0 else 0
        avg = d["pnl"] / total if total > 0 else 0
        print(f"  {r:20s}: {total:3d} trade | WR={wr:5.1f}% | PnL=${d['pnl']:+8.2f} | Avg=${avg:+.2f}")

    # 2. Coin bazlı WR
    print(f"\n{'─'*60}")
    print("2. COİN BAZLI PERFORMANS (WR sıralı)")
    print(f"{'─'*60}")
    coins = {}
    for t in trades:
        sym = t.symbol
        if sym not in coins:
            coins[sym] = {"wins": 0, "losses": 0, "pnl": 0}
        if t.net_pnl > 0:
            coins[sym]["wins"] += 1
        else:
            coins[sym]["losses"] += 1
        coins[sym]["pnl"] += t.net_pnl

    for sym, d in sorted(coins.items(), key=lambda x: x[1]["wins"]/(x[1]["wins"]+x[1]["losses"]) if (x[1]["wins"]+x[1]["losses"]) > 0 else 0, reverse=True):
        total = d["wins"] + d["losses"]
        wr = d["wins"] / total * 100 if total > 0 else 0
        status = "✅" if wr >= 50 else ("⚠️" if wr >= 45 else "❌")
        print(f"  {status} {sym:12s}: {total:3d} trade | WR={wr:5.1f}% | PnL=${d['pnl']:+8.2f}")

    # 3. TIME-EXIT detay (en çok zarar eden)
    print(f"\n{'─'*60}")
    print("3. TIME-EXIT TRADE ANALİZİ (en büyük kayıp kaynağı)")
    print(f"{'─'*60}")
    time_exits = [t for t in trades if "TIME-EXIT" in t.reason]
    if time_exits:
        te_wins = [t for t in time_exits if t.net_pnl > 0]
        te_losses = [t for t in time_exits if t.net_pnl <= 0]
        te_wr = len(te_wins) / len(time_exits) * 100
        print(f"  Time-Exit Toplam: {len(time_exits)} trade")
        print(f"  Time-Exit WR: {te_wr:.1f}%")
        print(f"  Time-Exit PnL: ${sum(t.net_pnl for t in time_exits):+.2f}")
        if te_wins:
            print(f"  Time-Exit Ort Kazanç: ${np.mean([t.net_pnl for t in te_wins]):+.2f}")
        if te_losses:
            print(f"  Time-Exit Ort Kayıp: ${np.mean([t.net_pnl for t in te_losses]):+.2f}")

        # MFE dağılımı — TIME-EXIT trade'ler TP'ye ne kadar yaklaştı?
        print(f"\n  TIME-EXIT MFE dağılımı (TP'ye ne kadar yaklaştı):")
        mfes = [t.mfe_pct for t in time_exits]
        print(f"    MFE < 0.5%:  {sum(1 for m in mfes if m < 0.5):3d} trade (hiç hareket etmedi)")
        print(f"    MFE 0.5-1%:  {sum(1 for m in mfes if 0.5 <= m < 1.0):3d} trade")
        print(f"    MFE 1-2%:    {sum(1 for m in mfes if 1.0 <= m < 2.0):3d} trade")
        print(f"    MFE 2-3%:    {sum(1 for m in mfes if 2.0 <= m < 3.0):3d} trade")
        print(f"    MFE > 3%:    {sum(1 for m in mfes if m >= 3.0):3d} trade (TP'ye yaklaştı!)")

        # Candle bazlı analiz
        print(f"\n  TIME-EXIT candle dağılımı:")
        for c in sorted(set(t.candles_held for t in time_exits)):
            ct = [t for t in time_exits if t.candles_held == c]
            w = sum(1 for t in ct if t.net_pnl > 0)
            wr = w / len(ct) * 100
            pnl = sum(t.net_pnl for t in ct)
            print(f"    {c} candle: {len(ct):3d} trade | WR={wr:.1f}% | PnL=${pnl:+.2f}")

    # 4. STOP-LOSS detay
    print(f"\n{'─'*60}")
    print("4. STOP-LOSS TRADE ANALİZİ")
    print(f"{'─'*60}")
    sl_trades = [t for t in trades if t.reason == "STOP-LOSS"]
    if sl_trades:
        print(f"  SL Toplam: {len(sl_trades)} trade")
        print(f"  SL Ort. Kayıp: ${np.mean([t.net_pnl for t in sl_trades]):+.2f}")
        print(f"  SL Ort. MAE: {np.mean([t.mae_pct for t in sl_trades]):.2f}%")

        # Breakeven sonrası SL vuranlar (SL = entry price)
        be_sl = [t for t in sl_trades if abs(t.exit_price - t.entry_price) / t.entry_price < 0.002]
        print(f"  Breakeven SL (≈entry): {len(be_sl)} trade")
        real_sl = [t for t in sl_trades if abs(t.exit_price - t.entry_price) / t.entry_price >= 0.002]
        print(f"  Gerçek SL (entry'den uzak): {len(real_sl)} trade | PnL=${sum(t.net_pnl for t in real_sl):+.2f}")

    # 5. MFE vs sonuç analizi — kâr bırakıyor muyuz?
    print(f"\n{'─'*60}")
    print("5. KÂR BIRAKMA ANALİZİ (tüm trade'ler)")
    print(f"{'─'*60}")
    losing = [t for t in trades if t.net_pnl <= 0]
    high_mfe_losers = [t for t in losing if t.mfe_pct >= 1.0]
    print(f"  Zararda kapanan ama MFE≥1% olan: {len(high_mfe_losers)} trade")
    print(f"    → Bu trade'ler kârdaydı ama döndü! Kayıp: ${sum(t.net_pnl for t in high_mfe_losers):+.2f}")
    very_high = [t for t in losing if t.mfe_pct >= 2.0]
    print(f"  Zararda kapanan ama MFE≥2% olan: {len(very_high)} trade")
    print(f"    → Ciddi kâr bırakıldı! Kayıp: ${sum(t.net_pnl for t in very_high):+.2f}")

    # 6. Holding süresi vs PnL
    print(f"\n{'─'*60}")
    print("6. CANDLE BAZLI PERFORMANS (holding süresi)")
    print(f"{'─'*60}")
    for c in range(1, 5):
        ct = [t for t in trades if t.candles_held == c]
        if ct:
            w = sum(1 for t in ct if t.net_pnl > 0)
            wr = w / len(ct) * 100
            pnl = sum(t.net_pnl for t in ct)
            avg = pnl / len(ct)
            print(f"  {c} candle ({c*4}h): {len(ct):3d} trade | WR={wr:.1f}% | PnL=${pnl:+8.2f} | Avg=${avg:+.2f}")

    # 7. WR %50+ için ne lazım?
    print(f"\n{'─'*60}")
    print("7. WR %50+ İÇİN MATEMATİK")
    print(f"{'─'*60}")
    total = len(trades)
    wins = sum(1 for t in trades if t.net_pnl > 0)
    needed_for_50 = int(total * 0.50) - wins + 1
    print(f"  Toplam: {total} trade, Kazanç: {wins}, WR: {wins/total*100:.1f}%")
    print(f"  %50 WR için {needed_for_50} trade daha kazanmamız lazım")
    print(f"  VEYA {needed_for_50} kaybeden trade'i kazanana çevirmemiz lazım")

    # En zayıf halkayı bul
    print(f"\n  EN ZAYIF HALKA (en çok düzeltilebilir):")

    # TIME-EXIT losers that had MFE > 0.5% → could have been partial TP
    te_recoverable = [t for t in time_exits if t.net_pnl <= 0 and t.mfe_pct >= 0.5]
    print(f"    TIME-EXIT zararda ama MFE≥0.5%: {len(te_recoverable)} trade")
    print(f"      → Daha erken TP1 veya daha dar TP bunları kurtarabilir")

    # SL trades that had MFE > 1% → breakeven should have saved them
    sl_recoverable = [t for t in sl_trades if t.mfe_pct >= 1.0]
    print(f"    SL zararda ama MFE≥1%: {len(sl_recoverable)} trade")
    print(f"      → Breakeven daha erken tetiklenmeli ({config.BREAKEVEN_ATR_TRIGGER}x ATR şu an)")

    return {
        "reasons": reasons,
        "coins": coins,
        "time_exits": time_exits,
        "sl_trades": sl_trades,
    }


def test_optimizations(baseline_trades):
    """Farklı parametreleri test et ve karşılaştır"""
    print("\n" + "="*70)
    print("OPTİMİZASYON TESTLERİ — A/B KARŞILAŞTIRMA")
    print("="*70)

    tests = []

    # Test 1: MAX_HOLD_CANDLES = 2 (12h → 8h)
    print("\n--- Test 1: MAX_HOLD_CANDLES 3→2 ---")
    old_val = config.MAX_HOLD_CANDLES
    config.MAX_HOLD_CANDLES = 2
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("MAX_HOLD=2", r))
    config.MAX_HOLD_CANDLES = old_val

    # Test 2: BREAKEVEN 0.7 → 0.5
    print("\n--- Test 2: BREAKEVEN 0.7→0.5 ---")
    old_val = config.BREAKEVEN_ATR_TRIGGER
    config.BREAKEVEN_ATR_TRIGGER = 0.5
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("BE=0.5", r))
    config.BREAKEVEN_ATR_TRIGGER = old_val

    # Test 3: TP 1.2 → 1.0 (daha dar TP, daha çok vuruş)
    print("\n--- Test 3: RANGING TP 1.2→1.0 ---")
    old_rr = config.DYNAMIC_RR["RANGING"].copy()
    config.DYNAMIC_RR["RANGING"] = {"sl": 1.0, "tp": 1.0}
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("TP=1.0", r))
    config.DYNAMIC_RR["RANGING"] = old_rr

    # Test 4: SL 1.0 → 0.8 (daha dar SL)
    print("\n--- Test 4: RANGING SL 1.0→0.8 ---")
    old_rr = config.DYNAMIC_RR["RANGING"].copy()
    config.DYNAMIC_RR["RANGING"] = {"sl": 0.8, "tp": 1.2}
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("SL=0.8", r))
    config.DYNAMIC_RR["RANGING"] = old_rr

    # Test 5: Partial TP %70 → %80
    print("\n--- Test 5: PARTIAL_TP %70→%80 ---")
    old_val = config.PARTIAL_TP_CLOSE_PCT
    config.PARTIAL_TP_CLOSE_PCT = 0.80
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("PTP=80%", r))
    config.PARTIAL_TP_CLOSE_PCT = old_val

    # Test 6: Confidence 0.40 → 0.45
    print("\n--- Test 6: MIN_CONFIDENCE 0.40→0.45 ---")
    old_val = config.STRATEGY_MIN_CONFIDENCE
    config.STRATEGY_MIN_CONFIDENCE = 0.45
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("CONF=0.45", r))
    config.STRATEGY_MIN_CONFIDENCE = old_val

    # Test 7: TP 1.2 → 1.1 + SL 1.0 → 0.9
    print("\n--- Test 7: RANGING SL=0.9 TP=1.1 (sıkılaştırma) ---")
    old_rr = config.DYNAMIC_RR["RANGING"].copy()
    config.DYNAMIC_RR["RANGING"] = {"sl": 0.9, "tp": 1.1}
    bt = BacktestV3()
    r = bt.run(days=60)
    tests.append(("SL0.9/TP1.1", r))
    config.DYNAMIC_RR["RANGING"] = old_rr

    # === SONUÇ TABLOSU ===
    print("\n" + "="*70)
    print("OPTİMİZASYON SONUÇ TABLOSU")
    print("="*70)
    print(f"  {'Test':<16s} | {'Trade':>5s} | {'WR':>6s} | {'PnL':>10s} | {'PF':>5s} | {'MaxDD':>6s} | {'AvgWin':>7s} | {'AvgLoss':>7s}")
    print(f"  {'─'*80}")

    # Baseline
    bl = baseline_trades
    bl_wins = [t for t in bl if t.net_pnl > 0]
    bl_losses = [t for t in bl if t.net_pnl <= 0]
    bl_pnl = sum(t.net_pnl for t in bl)
    bl_wr = len(bl_wins) / len(bl) * 100
    gw = sum(t.net_pnl for t in bl_wins)
    gl = abs(sum(t.net_pnl for t in bl_losses))
    bl_pf = gw / gl if gl > 0 else 0
    bl_aw = np.mean([t.net_pnl for t in bl_wins]) if bl_wins else 0
    bl_al = np.mean([t.net_pnl for t in bl_losses]) if bl_losses else 0
    print(f"  {'BASELINE':<16s} | {len(bl):5d} | {bl_wr:5.1f}% | ${bl_pnl:+8.2f} | {bl_pf:5.2f} | {'3.8%':>6s} | ${bl_aw:+6.2f} | ${bl_al:+6.2f}")

    for name, r in tests:
        marker = " ✅" if r.win_rate > bl_wr and r.total_pnl > bl_pnl else ""
        print(f"  {name:<16s} | {r.total_trades:5d} | {r.win_rate:5.1f}% | ${r.total_pnl:+8.2f} | {r.profit_factor:5.2f} | {r.max_drawdown_pct:5.1f}% | ${r.avg_win:+6.2f} | ${r.avg_loss:+6.2f}{marker}")

    print(f"\n  ✅ = WR VE PnL ikisi de baseline'dan iyi")
    print("="*70)

    return tests


if __name__ == "__main__":
    print("WAR MACHINE — DERİN ANALİZ VE OPTİMİZASYON\n")

    # 1. Baseline çalıştır
    result = run_baseline()

    # 2. Derin analiz
    analysis = analyze_trades(result.trades)

    # 3. Optimizasyon testleri
    tests = test_optimizations(result.trades)
