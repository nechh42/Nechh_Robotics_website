"""
oos_test.py — Out-of-Sample & Walk-Forward Test
=================================================
v16.1 parametrelerinin overfitting kontrolü.

Testler:
  1. IN-SAMPLE (son 60 gün) — bilinen baseline
  2. OUT-OF-SAMPLE (60-120 gün önce) — HİÇ görmediği veri
  3. EXTENDED (180 gün) — uzun vadeli dayanıklılık

Kullanım:
  python -m backtest.oos_test
  python -m backtest.oos_test --walk-forward
"""

import sys
import os
import json
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from backtest.backtest_v3 import BacktestV3, BTResult, save_results

logger = logging.getLogger(__name__)


def fetch_klines_range(symbol: str, interval: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Fetch historical klines between specific dates.
    start_date, end_date: "YYYY-MM-DD" format
    """
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ms = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

    all_data = []
    current = start_ms

    while current < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "endTime": end_ms,
            "limit": 1000,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            all_data.extend(data)
            current = data[-1][0] + 1
            if len(data) < 1000:
                break
        except Exception as e:
            logger.error(f"Fetch error {symbol}: {e}")
            break

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades_count",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def run_backtest_with_data(data_map: Dict[str, pd.DataFrame], label: str,
                           initial_balance: float = 10000.0) -> BTResult:
    """
    Run BacktestV3 engine with pre-fetched data (date-range specific).
    Replicates BacktestV3.run() logic but uses provided data.
    """
    from strategies.regime import detect_regime
    from strategies.indicators import calc_atr, calc_rsi
    from engine.voting import combine_signals
    from strategies.rsi_reversion import RSIReversionStrategy
    from strategies.momentum import MomentumStrategy
    from strategies.vwap_reversion import VWAPReversionStrategy
    from strategies.edge_discovery import EdgeDiscoveryStrategy

    bt = BacktestV3(initial_balance=initial_balance)

    # Find common time range
    all_times = set()
    for sym, df in data_map.items():
        all_times.update(df["open_time"].tolist())
    sorted_times = sorted(all_times)

    total_steps = len(sorted_times)
    print(f"\n  [{label}] {total_steps} candle, {len(data_map)} sembol")

    # Walk forward
    for t_idx, timestamp in enumerate(sorted_times):
        if t_idx % 50 == 0:
            print(f"    İlerleme: {t_idx}/{total_steps} ({t_idx*100//max(total_steps,1)}%)", flush=True)
        dt = datetime.fromtimestamp(timestamp / 1000)
        if bt._current_day != dt.date():
            bt._daily_trades = 0
            bt._daily_loss = 0.0
            bt._current_day = dt.date()

        for sym in list(data_map.keys()):
            df = data_map[sym]
            mask = df["open_time"] <= timestamp
            df_window = df[mask].tail(config.CANDLE_HISTORY_COUNT).reset_index(drop=True)

            if len(df_window) < 50:
                continue

            price = df_window["close"].iloc[-1]
            high = df_window["high"].iloc[-1]
            low = df_window["low"].iloc[-1]
            ts_str = str(df_window["timestamp"].iloc[-1])

            if sym in bt.positions:
                bt._update_mfe_mae(sym, high, low)

            if sym in bt.positions:
                bt._check_exits(sym, price, high, low, ts_str, df_window)

            if sym in bt.positions:
                bt._funding_counter += 1
                if bt._funding_counter >= 2:
                    bt._apply_funding(sym, price)
                    bt._funding_counter = 0

            if sym not in bt.positions:
                bt._evaluate_entry(sym, df_window, price, ts_str)

        equity = bt._calc_equity(data_map, timestamp)
        bt.equity_curve.append(equity)

    # Close remaining
    for sym in list(bt.positions.keys()):
        if sym in data_map:
            df = data_map[sym]
            last_price = df["close"].iloc[-1]
            last_time = str(df["timestamp"].iloc[-1])
            last_regime = detect_regime(df.tail(100).reset_index(drop=True))
            bt._close_position(sym, last_price, last_time, "END_OF_DATA", last_regime)

    result = BTResult(period=label, symbols_tested=list(data_map.keys()))
    result = bt._calculate_results(result)
    return result


def fetch_all_symbols(symbols: List[str], interval: str,
                      start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    """Fetch data for all symbols in a date range"""
    data_map = {}
    for sym in symbols:
        print(f"  {sym}...", end=" ", flush=True)
        df = fetch_klines_range(sym, interval, start_date, end_date)
        if df is not None and len(df) >= 50:
            data_map[sym] = df
            print(f"{len(df)} candles ✓")
        else:
            print("SKIP")
    return data_map


def run_oos_test():
    """
    Out-of-Sample Test:
    - In-Sample: Son 60 gün (bilinen baseline)
    - OOS-1: 60-120 gün önce (hiç görmediği veri)
    - OOS-2: 120-180 gün önce (daha eski veri)
    - Extended: Son 180 gün (uzun vadeli)
    """
    symbols = config.SYMBOLS
    now = datetime.now()

    periods = {
        "IN-SAMPLE (son 60 gün)": {
            "start": (now - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
        },
        "OOS-1 (60-120 gün önce)": {
            "start": (now - timedelta(days=120)).strftime("%Y-%m-%d"),
            "end": (now - timedelta(days=60)).strftime("%Y-%m-%d"),
        },
        "OOS-2 (120-180 gün önce)": {
            "start": (now - timedelta(days=180)).strftime("%Y-%m-%d"),
            "end": (now - timedelta(days=120)).strftime("%Y-%m-%d"),
        },
    }

    print("=" * 70)
    print("WAR MACHINE — OUT-OF-SAMPLE TEST")
    print("=" * 70)
    print(f"Tarih: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Config: v16.1 parametreleri SABİT (hiçbir şey değiştirilmez)")
    print(f"Sembol: {len(symbols)} coin")
    print(f"Interval: 4h")
    print("=" * 70)

    results = {}

    for label, period in periods.items():
        print(f"\n{'─' * 70}")
        print(f"  TEST: {label}")
        print(f"  Tarih: {period['start']} → {period['end']}")
        print(f"{'─' * 70}")

        data_map = fetch_all_symbols(symbols, "4h", period["start"], period["end"])

        if not data_map:
            print(f"  ⚠️ Veri yok, atlanıyor")
            continue

        result = run_backtest_with_data(data_map, label)
        results[label] = result

    # ═══════════════════════════════════════════════════
    # KARŞILAŞTIRMA TABLOSU
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("OUT-OF-SAMPLE KARŞILAŞTIRMA")
    print("=" * 70)

    header = f"  {'Periyot':<30s} │ {'Trade':>5s} │ {'WR':>6s} │ {'PnL':>10s} │ {'PF':>5s} │ {'MaxDD':>6s} │ {'AvgW':>6s} │ {'AvgL':>6s}"
    print(header)
    print("  " + "─" * len(header))

    for label, r in results.items():
        short_label = label.split("(")[0].strip()
        print(f"  {short_label:<30s} │ {r.total_trades:>5d} │ "
              f"{r.win_rate:>5.1f}% │ ${r.total_pnl:>+9.2f} │ "
              f"{r.profit_factor:>5.2f} │ {r.max_drawdown_pct:>5.1f}% │ "
              f"${r.avg_win:>5.2f} │ ${r.avg_loss:>5.2f}")

    # ═══════════════════════════════════════════════════
    # OVERFİTTİNG TEŞHİSİ
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("OVERFİTTİNG TEŞHİSİ")
    print("=" * 70)

    is_label = "IN-SAMPLE (son 60 gün)"
    oos1_label = "OOS-1 (60-120 gün önce)"

    if is_label in results and oos1_label in results:
        is_r = results[is_label]
        oos_r = results[oos1_label]

        print(f"\n  In-Sample PF:       {is_r.profit_factor:.2f}")
        print(f"  Out-of-Sample PF:   {oos_r.profit_factor:.2f}")

        if is_r.profit_factor > 0:
            degradation = (1 - oos_r.profit_factor / is_r.profit_factor) * 100
            print(f"  Degradation:        {degradation:+.1f}%")

        print()
        if oos_r.profit_factor >= 1.2:
            print("  ✅ SONUÇ: OVERFİTTİNG YOK — Sistem sağlam!")
            print("     OOS PF ≥ 1.2 → Parametreler genelleştirme yapabiliyor")
            verdict = "PASS"
        elif oos_r.profit_factor >= 1.0:
            print("  ⚠️ SONUÇ: HAFİF OVERFİTTİNG — Dikkatli ol")
            print("     OOS PF 1.0-1.2 → Hafif overfitting, ama hâlâ kârlı")
            print("     Öneri: Walk-forward analiz yap, parametre sayısını azalt")
            verdict = "WARNING"
        else:
            print("  ❌ SONUÇ: AĞIR OVERFİTTİNG — DUR!")
            print("     OOS PF < 1.0 → Parametreler sadece in-sample'a uydurulmuş")
            print("     Öneri: Daha basit strateji, daha az filtre, geniş coin listesi")
            verdict = "FAIL"
    else:
        verdict = "INCOMPLETE"

    # ═══════════════════════════════════════════════════
    # REGIME KARŞILAŞTIRMA
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("REGIME BAZLI KARŞILAŞTIRMA")
    print("=" * 70)

    for label, r in results.items():
        short_label = label.split("(")[0].strip()
        if r.regime_stats:
            print(f"\n  {short_label}:")
            for regime, stats in r.regime_stats.items():
                if regime == "exit_reasons":
                    continue
                print(f"    {regime:12s}: {stats['trades']:3d} trade, "
                      f"WR={stats['win_rate']:5.1f}%, PnL=${stats['pnl']:+.2f}")

    # ═══════════════════════════════════════════════════
    # EXIT REASON KARŞILAŞTIRMA
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("EXIT REASON KARŞILAŞTIRMA")
    print("=" * 70)

    for label, r in results.items():
        short_label = label.split("(")[0].strip()
        exits = r.regime_stats.get("exit_reasons", {})
        if exits:
            print(f"\n  {short_label}:")
            for reason, data in sorted(exits.items()):
                print(f"    {reason:20s}: {data['count']:3d} trade, PnL=${data['pnl']:+.2f}")

    # ═══════════════════════════════════════════════════
    # DOSYAYA KAYDET
    # ═══════════════════════════════════════════════════

    report = {
        "test_date": now.strftime("%Y-%m-%d %H:%M"),
        "verdict": verdict,
        "config_version": "v16.1",
        "results": {},
    }

    for label, r in results.items():
        report["results"][label] = {
            "trades": r.total_trades,
            "win_rate": round(r.win_rate, 1),
            "pnl": round(r.total_pnl, 2),
            "profit_factor": round(r.profit_factor, 2),
            "max_drawdown_pct": round(r.max_drawdown_pct, 1),
            "sharpe": round(r.sharpe, 2),
            "avg_win": round(r.avg_win, 2),
            "avg_loss": round(r.avg_loss, 2),
            "avg_hold_candles": round(r.avg_hold_candles, 1),
        }

    report_path = "backtest/oos_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Rapor kaydedildi: {report_path}")

    return results, verdict


def run_walk_forward():
    """
    Walk-Forward Analysis:
    Son 180 günü 30-günlük pencerelerle test et.
    Her pencere: Train (60 gün) → Test (30 gün)
    
    Walk-Forward Efficiency = Avg(Test_PnL) / Avg(Train_PnL) × 100
    WFE > 50% → Sistem sağlam
    """
    symbols = config.SYMBOLS
    now = datetime.now()

    print("=" * 70)
    print("WAR MACHINE — WALK-FORWARD ANALİZ")
    print("=" * 70)
    print(f"Yöntem: 60-gün train + 30-gün test, 30-gün kayma")
    print(f"Parametreler: v16.1 SABİT (optimizasyon yapılmıyor)")
    print(f"Sembol: {len(symbols)} coin")
    print("=" * 70)

    # Define windows: 180 days total, sliding 30 days
    # Window 1: Train(day-180 to day-120) → Test(day-120 to day-90)
    # Window 2: Train(day-150 to day-90)  → Test(day-90 to day-60)
    # Window 3: Train(day-120 to day-60)  → Test(day-60 to day-30)
    # Window 4: Train(day-90 to day-30)   → Test(day-30 to day-0)

    windows = []
    for i in range(4):
        shift = (3 - i) * 30  # 90, 60, 30, 0
        train_start = now - timedelta(days=shift + 120)
        train_end = now - timedelta(days=shift + 60)
        test_start = train_end
        test_end = now - timedelta(days=shift)
        windows.append({
            "label": f"Pencere {i+1}",
            "train_start": train_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
        })

    train_results = []
    test_results = []

    for w in windows:
        print(f"\n{'═' * 70}")
        print(f"  {w['label']}")
        print(f"  Train: {w['train_start']} → {w['train_end']}")
        print(f"  Test:  {w['test_start']} → {w['test_end']}")
        print(f"{'═' * 70}")

        # Fetch train data
        print(f"\n  📥 Train verisi çekiliyor...")
        train_data = fetch_all_symbols(symbols, "4h", w["train_start"], w["train_end"])

        # Fetch test data (need extra 10 days for warmup indicators)
        print(f"\n  📥 Test verisi çekiliyor...")
        warmup_start = (datetime.strptime(w["test_start"], "%Y-%m-%d") - timedelta(days=15)).strftime("%Y-%m-%d")
        test_data = fetch_all_symbols(symbols, "4h", warmup_start, w["test_end"])

        if not train_data or not test_data:
            print("  ⚠️ Yetersiz veri, atlanıyor")
            continue

        # Run train
        print(f"\n  🔄 Train çalıştırılıyor...")
        train_r = run_backtest_with_data(train_data, f"Train-{w['label']}")
        train_results.append(train_r)

        # Run test
        print(f"\n  🔄 Test çalıştırılıyor...")
        test_r = run_backtest_with_data(test_data, f"Test-{w['label']}")
        test_results.append(test_r)

        print(f"\n  Train: {train_r.total_trades} trade, WR={train_r.win_rate:.1f}%, "
              f"PnL=${train_r.total_pnl:+.2f}, PF={train_r.profit_factor:.2f}")
        print(f"  Test:  {test_r.total_trades} trade, WR={test_r.win_rate:.1f}%, "
              f"PnL=${test_r.total_pnl:+.2f}, PF={test_r.profit_factor:.2f}")

    # ═══════════════════════════════════════════════════
    # WALK-FORWARD SONUÇ
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("WALK-FORWARD SONUÇLARI")
    print("=" * 70)

    header = f"  {'Pencere':<12s} │ {'Train PnL':>10s} │ {'Test PnL':>10s} │ {'Train PF':>8s} │ {'Test PF':>8s} │ {'Efficiency':>10s}"
    print(header)
    print("  " + "─" * len(header))

    wfe_values = []
    for i, (tr, te) in enumerate(zip(train_results, test_results)):
        if tr.total_pnl != 0:
            eff = (te.total_pnl / abs(tr.total_pnl)) * 100
        else:
            eff = 0
        wfe_values.append(eff)

        print(f"  Pencere {i+1:<4d} │ ${tr.total_pnl:>+9.2f} │ ${te.total_pnl:>+9.2f} │ "
              f"{tr.profit_factor:>8.2f} │ {te.profit_factor:>8.2f} │ {eff:>9.1f}%")

    # Overall WFE
    avg_train_pnl = np.mean([r.total_pnl for r in train_results]) if train_results else 0
    avg_test_pnl = np.mean([r.total_pnl for r in test_results]) if test_results else 0
    avg_train_pf = np.mean([r.profit_factor for r in train_results]) if train_results else 0
    avg_test_pf = np.mean([r.profit_factor for r in test_results]) if test_results else 0

    if avg_train_pnl != 0:
        overall_wfe = (avg_test_pnl / abs(avg_train_pnl)) * 100
    else:
        overall_wfe = 0

    print(f"  {'─' * 70}")
    print(f"  {'ORTALAMA':<12s} │ ${avg_train_pnl:>+9.2f} │ ${avg_test_pnl:>+9.2f} │ "
          f"{avg_train_pf:>8.2f} │ {avg_test_pf:>8.2f} │ {overall_wfe:>9.1f}%")

    print(f"\n  Walk-Forward Efficiency (WFE): {overall_wfe:.1f}%")
    print(f"  Ortalama Train PF: {avg_train_pf:.2f}")
    print(f"  Ortalama Test PF:  {avg_test_pf:.2f}")

    if overall_wfe >= 50:
        print(f"\n  ✅ WFE ≥ %50 → SİSTEM SAĞLAM! Parametreler genelleştirme yapıyor.")
        wf_verdict = "PASS"
    elif overall_wfe >= 25:
        print(f"\n  ⚠️ WFE %25-50 → ORTA — Parametre hassasiyeti var ama çalışabilir")
        wf_verdict = "WARNING"
    else:
        print(f"\n  ❌ WFE < %25 → OVERFİTTİNG — Parametreler sadece train veriye uydurulmuş")
        wf_verdict = "FAIL"

    # Consistency check: how many test windows are profitable?
    profitable_tests = sum(1 for r in test_results if r.total_pnl > 0)
    total_tests = len(test_results)
    print(f"\n  Kârlı test penceresi: {profitable_tests}/{total_tests}")
    if profitable_tests == total_tests:
        print("  ✅ TÜM pencereler kârlı — çok güçlü sinyal!")
    elif profitable_tests >= total_tests * 0.75:
        print("  ✅ Çoğu pencere kârlı — iyi sinyal")
    elif profitable_tests >= total_tests * 0.5:
        print("  ⚠️ Yarısı kârlı — dikkatli ol")
    else:
        print("  ❌ Çoğu pencere zararlı — sistem güvenilmez")

    # Save report
    wf_report = {
        "test_date": now.strftime("%Y-%m-%d %H:%M"),
        "verdict": wf_verdict,
        "overall_wfe": round(overall_wfe, 1),
        "avg_train_pf": round(avg_train_pf, 2),
        "avg_test_pf": round(avg_test_pf, 2),
        "profitable_test_windows": f"{profitable_tests}/{total_tests}",
        "windows": [],
    }

    for i, (tr, te) in enumerate(zip(train_results, test_results)):
        wf_report["windows"].append({
            "window": i + 1,
            "train_trades": tr.total_trades,
            "train_pnl": round(tr.total_pnl, 2),
            "train_pf": round(tr.profit_factor, 2),
            "train_wr": round(tr.win_rate, 1),
            "test_trades": te.total_trades,
            "test_pnl": round(te.total_pnl, 2),
            "test_pf": round(te.profit_factor, 2),
            "test_wr": round(te.win_rate, 1),
        })

    report_path = "backtest/walk_forward_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(wf_report, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Rapor kaydedildi: {report_path}")

    return wf_report


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="War Machine OOS & Walk-Forward Test")
    parser.add_argument("--walk-forward", action="store_true", help="Walk-Forward Analiz")
    parser.add_argument("--oos-only", action="store_true", help="Sadece Out-of-Sample Test")
    args = parser.parse_args()

    if args.walk_forward:
        run_walk_forward()
    elif args.oos_only:
        run_oos_test()
    else:
        # Default: both
        print("\n" + "█" * 70)
        print("  BÖLÜM 1: OUT-OF-SAMPLE TEST")
        print("█" * 70)
        results, oos_verdict = run_oos_test()

        print("\n" + "█" * 70)
        print("  BÖLÜM 2: WALK-FORWARD ANALİZ")
        print("█" * 70)
        wf_report = run_walk_forward()

        # Final summary
        print("\n" + "█" * 70)
        print("  GENEL SONUÇ")
        print("█" * 70)
        print(f"\n  Out-of-Sample:  {oos_verdict}")
        print(f"  Walk-Forward:   {wf_report['verdict']}")
        print(f"  WFE:            {wf_report['overall_wfe']:.1f}%")

        if oos_verdict == "PASS" and wf_report["verdict"] == "PASS":
            print("\n  ✅✅ SİSTEM SAĞLAM — Live geçiş hazırlığına başlanabilir!")
        elif oos_verdict == "FAIL" or wf_report["verdict"] == "FAIL":
            print("\n  ❌❌ OVERFİTTİNG TESPİT EDİLDİ — Sistemi gözden geçir!")
        else:
            print("\n  ⚠️ DİKKATLİ İLERLE — Paper trade sonuçlarını mutlaka bekle")
