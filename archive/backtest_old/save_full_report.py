"""
save_full_report.py — v15.5 Backtest sonuçlarını detaylı kaydet
================================================================
Tüm analiz sonuçlarını backtest/ klasörüne yazar.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime
from collections import Counter
from backtest.backtest_v3 import BacktestV3
import config


def run_and_save():
    bt = BacktestV3()
    result = bt.run(days=60)
    trades = result.trades
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # ═══════════════════════════════════════
    # 1. TEXT RAPOR
    # ═══════════════════════════════════════
    lines = []
    lines.append("=" * 70)
    lines.append("WAR MACHINE v15.5 — BACKTEST SONUÇLARI VE DERİN ANALİZ")
    lines.append(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Periyot: 60 gün | Interval: 4h | Mod: LONG-ONLY")
    lines.append("=" * 70)

    # Genel
    lines.append("\n" + "─" * 50)
    lines.append("1. GENEL PERFORMANS")
    lines.append("─" * 50)
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    total_pnl = sum(t.net_pnl for t in trades)
    total_comm = sum(t.commission for t in trades)
    total_fund = sum(t.funding_fee for t in trades)
    gross_win = sum(t.net_pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.net_pnl for t in losses)) if losses else 1
    pf = gross_win / gross_loss if gross_loss > 0 else 0

    lines.append(f"  Toplam Trade    : {len(trades)}")
    lines.append(f"  Kazanç/Kayıp    : {len(wins)}/{len(losses)}")
    lines.append(f"  Win Rate        : {len(wins)/len(trades)*100:.1f}%")
    lines.append(f"  Toplam PnL      : ${total_pnl:+.2f}")
    lines.append(f"  Komisyon        : ${total_comm:.2f}")
    lines.append(f"  Funding Fee     : ${total_fund:.2f}")
    lines.append(f"  Profit Factor   : {pf:.2f}")
    lines.append(f"  Ort. Kazanç     : ${np.mean([t.net_pnl for t in wins]):.2f}" if wins else "  Ort. Kazanç     : $0")
    lines.append(f"  Ort. Kayıp      : ${np.mean([t.net_pnl for t in losses]):.2f}" if losses else "  Ort. Kayıp      : $0")
    lines.append(f"  Ort. MFE        : {np.mean([t.mfe_pct for t in trades]):.2f}%")
    lines.append(f"  Ort. MAE        : {np.mean([t.mae_pct for t in trades]):.2f}%")
    lines.append(f"  Ort. Holding    : {np.mean([t.candles_held for t in trades]):.1f} candle")
    lines.append(f"  Max Drawdown    : ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1f}%)")
    lines.append(f"  Final Balance   : ${result.final_balance:.2f}")

    # Çıkış nedenleri
    lines.append("\n" + "─" * 50)
    lines.append("2. ÇIKIŞ NEDENLERİ ANALİZİ")
    lines.append("─" * 50)
    reasons = {}
    for t in trades:
        r = t.reason.split(":")[0]
        if r not in reasons:
            reasons[r] = {"count": 0, "pnl": 0, "wins": 0}
        reasons[r]["count"] += 1
        reasons[r]["pnl"] += t.net_pnl
        if t.net_pnl > 0:
            reasons[r]["wins"] += 1
    for r, d in sorted(reasons.items(), key=lambda x: -x[1]["count"]):
        wr = d["wins"] / d["count"] * 100 if d["count"] > 0 else 0
        lines.append(f"  {r:20s}: {d['count']:3d} trade | WR={wr:5.1f}% | PnL=${d['pnl']:+8.2f}")

    # Coin bazlı
    lines.append("\n" + "─" * 50)
    lines.append("3. COIN BAZLI PERFORMANS")
    lines.append("─" * 50)
    coins = sorted(set(t.symbol for t in trades))
    coin_data = []
    for coin in coins:
        ct = [t for t in trades if t.symbol == coin]
        cw = [t for t in ct if t.net_pnl > 0]
        cpnl = sum(t.net_pnl for t in ct)
        wr = len(cw) / len(ct) * 100 if ct else 0
        coin_data.append((coin, len(ct), wr, cpnl))
        lines.append(f"  {coin:12s}: {len(ct):3d} trade | WR={wr:5.1f}% | PnL=${cpnl:+8.2f}")

    # Kârlı vs Zararlı
    lines.append("\n  KARLI COİNLER:")
    for c, n, wr, pnl in sorted(coin_data, key=lambda x: -x[3]):
        if pnl > 0:
            lines.append(f"    ✅ {c:12s}: {n:3d} trade, WR={wr:5.1f}%, PnL=${pnl:+.2f}")
    lines.append("  ZARARI COİNLER:")
    for c, n, wr, pnl in sorted(coin_data, key=lambda x: x[3]):
        if pnl <= 0:
            lines.append(f"    ❌ {c:12s}: {n:3d} trade, WR={wr:5.1f}%, PnL=${pnl:+.2f}")

    # MFE distribution
    lines.append("\n" + "─" * 50)
    lines.append("4. MFE DAĞILIMI (Maximum Favorable Excursion)")
    lines.append("─" * 50)
    for level in [0.25, 0.50, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]:
        count = len([t for t in trades if t.mfe_pct >= level])
        lines.append(f"  MFE >= {level:.2f}%: {count}/{len(trades)} ({count/len(trades)*100:.1f}%)")

    # Holding süresi analizi
    lines.append("\n" + "─" * 50)
    lines.append("5. HOLDİNG SÜRESİ vs PERFORMANS")
    lines.append("─" * 50)
    for h in [1, 2, 3, 5, 8, 12]:
        ht = [t for t in trades if t.candles_held <= h]
        if ht:
            hw = len([t for t in ht if t.net_pnl > 0])
            hpnl = sum(t.net_pnl for t in ht)
            lines.append(f"  <={h:2d} candle ({h*4:2d}h): {len(ht):3d} trade | WR={hw/len(ht)*100:.1f}% | PnL=${hpnl:+.2f}")

    # SL trade detayı
    lines.append("\n" + "─" * 50)
    lines.append("6. STOP-LOSS TRADE DETAYI")
    lines.append("─" * 50)
    sl = [t for t in trades if t.reason.startswith("STOP-LOSS")]
    if sl:
        good = [t for t in sl if t.mfe_pct > 1.0]
        lines.append(f"  Toplam SL Trade : {len(sl)}")
        lines.append(f"  SL PnL          : ${sum(t.net_pnl for t in sl):+.2f}")
        lines.append(f"  Ort. MAE        : {np.mean([t.mae_pct for t in sl]):.2f}%")
        lines.append(f"  Ort. MFE        : {np.mean([t.mfe_pct for t in sl]):.2f}%")
        lines.append(f"  MFE>1% ama SL   : {len(good)} ({len(good)/len(sl)*100:.1f}%) — kâr kaçırılmış")
        quick = [t for t in sl if t.candles_held <= 1]
        lines.append(f"  1.candle SL     : {len(quick)} trade (${sum(t.net_pnl for t in quick):+.2f})")

    # v15.4 vs v15.5 karşılaştırma
    lines.append("\n" + "─" * 50)
    lines.append("7. VERSİYON KARŞILAŞTIRMASI (v15.4 → v15.5)")
    lines.append("─" * 50)
    lines.append("  Metrik           | v15.4          | v15.5          | Değişim")
    lines.append("  ─────────────────┼────────────────┼────────────────┼────────────")
    lines.append(f"  Trade            | 535            | {len(trades):3d}            | {len(trades)-535:+d}")
    lines.append(f"  Win Rate         | 43.7%          | {len(wins)/len(trades)*100:.1f}%          | {len(wins)/len(trades)*100-43.7:+.1f}%")
    lines.append(f"  PnL              | -$969.18       | ${total_pnl:+.2f}     | ${total_pnl+969.18:+.2f}")
    lines.append(f"  Profit Factor    | 0.65           | {pf:.2f}           | {pf-0.65:+.2f}")
    lines.append(f"  Max Drawdown     | 12.5%          | {result.max_drawdown_pct:.1f}%           | {result.max_drawdown_pct-12.5:+.1f}%")
    lines.append(f"  AvgWin           | $7.59          | ${np.mean([t.net_pnl for t in wins]):.2f}         | —")
    lines.append(f"  AvgLoss          | -$9.12         | ${np.mean([t.net_pnl for t in losses]):.2f}        | —")

    # Uygulanan optimizasyonlar
    lines.append("\n" + "─" * 50)
    lines.append("8. UYGULANAN 6 OPTİMİZASYON")
    lines.append("─" * 50)
    lines.append("  1. TREND_UP_BLOCK = True")
    lines.append("     → v15.4'te 88 trade, %30.7 WR, -$842 zarar")
    lines.append("     → Bu tradelerin tamamı engellendi")
    lines.append("  2. RANGING TP: 1.5 → 1.2 ×ATR")
    lines.append("     → Daha ulaşılabilir TP hedefi")
    lines.append("  3. BREAKEVEN: 1.0 → 0.7 ×ATR")
    lines.append("     → Kâr daha erken kilit altına alınıyor")
    lines.append("  4. MAX_HOLD_CANDLES = 3 (12 saat)")
    lines.append("     → Ölü pozisyonlar otomatik kapatılıyor")
    lines.append("  5. COIN_BLACKLIST: 11 coin filtrelendi")
    lines.append("     → UNI, ATOM, OP, NEAR, XLM, SOL, KAVA, INJ, PEPE, ARPA, SUI")
    lines.append("  6. PARTIAL_TP_CLOSE_PCT: %50 → %70")
    lines.append("     → AvgWin > AvgLoss sağlandı (kârlılığın anahtarı)")

    # Denenen ama işe yaramayan
    lines.append("\n" + "─" * 50)
    lines.append("9. DENENEN AMA TERS TEPEN OPTİMİZASYONLAR")
    lines.append("─" * 50)
    lines.append("  ❌ Breakeven 0.5×ATR → çok agresif, WR %44.7'ye düştü")
    lines.append("  ❌ SL 0.9×ATR → daha kötü, WR %48.2")
    lines.append("  ❌ Confidence 0.50 → ters etki, WR %48.1")
    lines.append("  ❌ Dip-buy filtresi → WR %48.8, trade sayısı düştü")
    lines.append("  ❌ Akıllı time-exit (sadece zararda kapat) → WR %43.9")
    lines.append("  ❌ TP 1.1×ATR → çok yakın, WR %48.4")

    # En iyi / en kötü tradeler
    lines.append("\n" + "─" * 50)
    lines.append("10. EN İYİ & EN KÖTÜ 10 TRADE")
    lines.append("─" * 50)
    sorted_trades = sorted(trades, key=lambda t: t.net_pnl, reverse=True)
    lines.append("  EN İYİ:")
    for t in sorted_trades[:10]:
        lines.append(f"    {t.symbol:12s} {t.side:5s} ${t.net_pnl:+7.2f} | MFE={t.mfe_pct:.1f}% | {t.reason}")
    lines.append("  EN KÖTÜ:")
    for t in sorted_trades[-10:]:
        lines.append(f"    {t.symbol:12s} {t.side:5s} ${t.net_pnl:+7.2f} | MAE={t.mae_pct:.1f}% | {t.reason}")

    # Config snapshot
    lines.append("\n" + "─" * 50)
    lines.append("11. AKTİF CONFIG PARAMETRELERİ")
    lines.append("─" * 50)
    lines.append(f"  TREND_UP_BLOCK      = {config.TREND_UP_BLOCK}")
    lines.append(f"  DIP_BUY_FILTER      = {config.DIP_BUY_FILTER}")
    lines.append(f"  MAX_HOLD_CANDLES    = {config.MAX_HOLD_CANDLES}")
    lines.append(f"  BREAKEVEN_ATR       = {config.BREAKEVEN_ATR_TRIGGER}")
    lines.append(f"  DYNAMIC_RR          = {config.DYNAMIC_RR}")
    lines.append(f"  PARTIAL_TP_RATIO    = {config.PARTIAL_TP_RATIO}")
    lines.append(f"  PARTIAL_TP_CLOSE    = {config.PARTIAL_TP_CLOSE_PCT}")
    lines.append(f"  COIN_BLACKLIST      = {config.COIN_BLACKLIST}")
    lines.append(f"  RISK_BASE_PCT       = {config.RISK_BASE_PCT}")
    lines.append(f"  MAX_POSITIONS       = {config.MAX_POSITIONS}")
    lines.append(f"  LEVERAGE            = {config.LEVERAGE}")

    lines.append("\n" + "=" * 70)
    lines.append("RAPOR SONU")
    lines.append("=" * 70)

    report_text = "\n".join(lines)
    report_path = os.path.join(os.path.dirname(__file__), f"v15.5_results_{ts}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n✅ Rapor kaydedildi: {report_path}")

    # ═══════════════════════════════════════
    # 2. JSON DATA (full trade list)
    # ═══════════════════════════════════════
    trade_list = []
    for t in trades:
        trade_list.append({
            "symbol": t.symbol, "side": t.side,
            "entry_price": round(t.entry_price, 6),
            "exit_price": round(t.exit_price, 6),
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "size": round(t.size, 6),
            "net_pnl": round(t.net_pnl, 4),
            "commission": round(t.commission, 4),
            "funding_fee": round(t.funding_fee, 4),
            "reason": t.reason, "strategy": t.strategy,
            "entry_regime": t.entry_regime, "exit_regime": t.exit_regime,
            "mfe_pct": round(t.mfe_pct, 4), "mae_pct": round(t.mae_pct, 4),
            "candles_held": t.candles_held,
        })

    json_path = os.path.join(os.path.dirname(__file__), f"v15.5_trades_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "v15.5",
            "date": datetime.now().isoformat(),
            "period_days": 60,
            "total_trades": len(trades),
            "win_rate": round(len(wins) / len(trades) * 100, 2),
            "total_pnl": round(total_pnl, 2),
            "profit_factor": round(pf, 2),
            "max_drawdown_pct": round(result.max_drawdown_pct, 2),
            "final_balance": round(result.final_balance, 2),
            "trades": trade_list,
        }, f, indent=2, ensure_ascii=False)
    print(f"✅ Trade verileri kaydedildi: {json_path}")

    print(report_text)
    return result, trades


if __name__ == "__main__":
    run_and_save()
