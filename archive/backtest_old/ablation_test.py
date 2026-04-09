"""
ablation_test.py — Bileşen Ablation Testi
============================================
v16.1'de hangi bileşenin overfitting'e neden olduğunu tespit eder.

Her bileşeni TEK TEK kapatıp OOS performansını ölçer.
OOS İYİLEŞEN bileşen → overfitted demektir.

Kullanım:
  python -m backtest.ablation_test
"""

import sys
import os
import json
import copy
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from backtest.oos_test import fetch_all_symbols, run_backtest_with_data

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# TEST CONFIGURATIONS
# ═══════════════════════════════════════════════════════

def apply_config_override(overrides: Dict[str, Any]):
    """Apply config overrides (monkey-patch config module)"""
    for key, value in overrides.items():
        setattr(config, key, value)


def get_baseline_config() -> Dict[str, Any]:
    """Capture current v16.1 config values"""
    return {
        "COIN_BLACKLIST": list(config.COIN_BLACKLIST),
        "SMART_EXIT_ENABLED": config.SMART_EXIT_ENABLED,
        "MIN_VOLUME_RATIO": config.MIN_VOLUME_RATIO,
        "DYNAMIC_RR": copy.deepcopy(config.DYNAMIC_RR),
        "MAX_HOLD_CANDLES": config.MAX_HOLD_CANDLES,
        "TREND_UP_BLOCK": config.TREND_UP_BLOCK,
        "BREAKEVEN_ATR_TRIGGER": config.BREAKEVEN_ATR_TRIGGER,
        "PARTIAL_TP_CLOSE_PCT": config.PARTIAL_TP_CLOSE_PCT,
        "PARTIAL_TP_ENABLED": config.PARTIAL_TP_ENABLED,
        "PARTIAL_TP_RATIO": config.PARTIAL_TP_RATIO,
    }


def restore_config(baseline: Dict[str, Any]):
    """Restore config to baseline values"""
    apply_config_override(baseline)


# Test configurations: each removes/changes one component
TEST_CONFIGS = {
    "BASE": {
        "desc": "v16.1 aynen (referans)",
        "overrides": {},  # No changes
    },
    "T1_NO_BLACKLIST": {
        "desc": "Blacklist KAPALI (tüm 29 coin)",
        "overrides": {"COIN_BLACKLIST": []},
    },
    "T2_NO_SMART_EXIT": {
        "desc": "Smart Exit KAPALI",
        "overrides": {"SMART_EXIT_ENABLED": False},
    },
    "T3_NO_VOL_FILTER": {
        "desc": "Volume Filter KAPALI",
        "overrides": {"MIN_VOLUME_RATIO": 0},
    },
    "T4_WIDER_RR": {
        "desc": "R:R RANGING sl:1.0→1.5, tp:1.2→2.0",
        "overrides": {
            "DYNAMIC_RR": {
                "TREND_UP":   {"sl": 1.5, "tp": 4.0},
                "TREND_DOWN": {"sl": 1.5, "tp": 4.0},
                "RANGING":    {"sl": 1.5, "tp": 2.0},
                "VOLATILE":   {"sl": 1.5, "tp": 3.0},
            }
        },
    },
    "T5_MAX_HOLD_4": {
        "desc": "MAX_HOLD 2→4 candle (16h)",
        "overrides": {"MAX_HOLD_CANDLES": 4},
    },
    "T6_NO_TREND_BLOCK": {
        "desc": "TREND_UP_BLOCK KAPALI",
        "overrides": {"TREND_UP_BLOCK": False},
    },
    "T7_BE_1ATR": {
        "desc": "Breakeven trigger 0.7→1.0 ATR",
        "overrides": {"BREAKEVEN_ATR_TRIGGER": 1.0},
    },
    "T8_COMBINED": {
        "desc": "Tüm overfitted bileşenler kapalı (final)",
        "overrides": {},  # Will be filled after individual tests
    },
}


def run_ablation_test():
    """Run ablation test: each config on OOS-1 and OOS-2"""
    now = datetime.now()

    # Periods: OOS-1 and OOS-2 (skip IS — we know it's good)
    periods = {
        "OOS-1": {
            "start": (now - timedelta(days=120)).strftime("%Y-%m-%d"),
            "end": (now - timedelta(days=60)).strftime("%Y-%m-%d"),
        },
        "OOS-2": {
            "start": (now - timedelta(days=180)).strftime("%Y-%m-%d"),
            "end": (now - timedelta(days=120)).strftime("%Y-%m-%d"),
        },
    }

    print("=" * 70)
    print("WAR MACHINE — BİLEŞEN ABLATION TESTİ")
    print("=" * 70)
    print(f"Tarih: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"AMAÇ: Hangi bileşen overfitting'e neden oluyor?")
    print(f"YÖNTEM: Her bileşeni tek tek kapat, OOS performansı ölç")
    print(f"KRİTER: OOS iyileşiyorsa → o bileşen overfitted")
    print("=" * 70)

    # Pre-fetch ALL data once (29 coins, both periods)
    # This saves massive time vs re-fetching per test
    print("\n📊 Veri indiriliyor (tüm coinler, tüm periyotlar)...")
    all_data = {}
    for period_name, period in periods.items():
        print(f"\n  === {period_name}: {period['start']} → {period['end']} ===")
        all_data[period_name] = fetch_all_symbols(
            config.SYMBOLS, "4h", period["start"], period["end"]
        )

    # Save baseline config
    baseline = get_baseline_config()

    # Results storage
    all_results = {}
    test_order = ["BASE", "T1_NO_BLACKLIST", "T2_NO_SMART_EXIT",
                   "T3_NO_VOL_FILTER", "T4_WIDER_RR", "T5_MAX_HOLD_4",
                   "T6_NO_TREND_BLOCK", "T7_BE_1ATR"]

    for test_name in test_order:
        test_cfg = TEST_CONFIGS[test_name]
        print(f"\n{'━' * 70}")
        print(f"  TEST: {test_name} — {test_cfg['desc']}")
        print(f"{'━' * 70}")

        # Restore baseline first, then apply overrides
        restore_config(baseline)
        if test_cfg["overrides"]:
            apply_config_override(test_cfg["overrides"])

        test_results = {}
        for period_name, data_map in all_data.items():
            # For T1 (no blacklist), use all data
            # For others, filter by current COIN_BLACKLIST
            active_blacklist = getattr(config, 'COIN_BLACKLIST', [])
            if active_blacklist:
                filtered_data = {s: d for s, d in data_map.items()
                               if s not in active_blacklist}
            else:
                filtered_data = data_map

            label = f"{test_name}_{period_name}"
            result = run_backtest_with_data(filtered_data, label)
            test_results[period_name] = {
                "trades": result.total_trades,
                "win_rate": round(result.win_rate, 1),
                "pnl": round(result.total_pnl, 2),
                "profit_factor": round(result.profit_factor, 2),
                "max_drawdown_pct": round(result.max_drawdown_pct, 1),
                "avg_win": round(result.avg_win, 2),
                "avg_loss": round(result.avg_loss, 2),
            }

        # Calculate average OOS PF
        pfs = [v["profit_factor"] for v in test_results.values()]
        avg_pf = sum(pfs) / len(pfs) if pfs else 0

        all_results[test_name] = {
            "desc": test_cfg["desc"],
            "periods": test_results,
            "avg_oos_pf": round(avg_pf, 2),
        }

        print(f"\n  → {test_name} OOS ortalama PF: {avg_pf:.2f}")

    # Restore config
    restore_config(baseline)

    # ═══════════════════════════════════════════════════
    # Now run T8_COMBINED with best improvements
    # ═══════════════════════════════════════════════════

    base_pf = all_results["BASE"]["avg_oos_pf"]
    improvements = {}
    for test_name, result in all_results.items():
        if test_name == "BASE":
            continue
        delta = result["avg_oos_pf"] - base_pf
        improvements[test_name] = delta

    # Combine all that IMPROVED OOS PF
    combined_overrides = {}
    combined_desc = []
    for test_name, delta in improvements.items():
        if delta > 0:  # OOS improved
            combined_overrides.update(TEST_CONFIGS[test_name]["overrides"])
            combined_desc.append(f"{test_name}(+{delta:.2f})")

    if combined_overrides:
        print(f"\n{'━' * 70}")
        print(f"  TEST: T8_COMBINED — {', '.join(combined_desc)}")
        print(f"{'━' * 70}")

        restore_config(baseline)
        apply_config_override(combined_overrides)

        test_results = {}
        for period_name, data_map in all_data.items():
            active_blacklist = getattr(config, 'COIN_BLACKLIST', [])
            if active_blacklist:
                filtered_data = {s: d for s, d in data_map.items()
                               if s not in active_blacklist}
            else:
                filtered_data = data_map

            label = f"T8_COMBINED_{period_name}"
            result = run_backtest_with_data(filtered_data, label)
            test_results[period_name] = {
                "trades": result.total_trades,
                "win_rate": round(result.win_rate, 1),
                "pnl": round(result.total_pnl, 2),
                "profit_factor": round(result.profit_factor, 2),
                "max_drawdown_pct": round(result.max_drawdown_pct, 1),
                "avg_win": round(result.avg_win, 2),
                "avg_loss": round(result.avg_loss, 2),
            }

        pfs = [v["profit_factor"] for v in test_results.values()]
        avg_pf = sum(pfs) / len(pfs) if pfs else 0

        all_results["T8_COMBINED"] = {
            "desc": f"Combined: {', '.join(combined_desc)}",
            "periods": test_results,
            "avg_oos_pf": round(avg_pf, 2),
        }

    restore_config(baseline)

    # ═══════════════════════════════════════════════════
    # SONUÇ TABLOSU
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("ABLATION TEST SONUÇLARI")
    print("=" * 70)
    print(f"\n  {'Test':<20s} │ {'Açıklama':<32s} │ {'OOS-1 PF':>8s} │ {'OOS-2 PF':>8s} │ {'Avg PF':>7s} │ {'Δ':>6s} │ Etki")
    print("  " + "─" * 105)

    for test_name in list(test_order) + (["T8_COMBINED"] if "T8_COMBINED" in all_results else []):
        if test_name not in all_results:
            continue
        r = all_results[test_name]
        oos1_pf = r["periods"].get("OOS-1", {}).get("profit_factor", 0)
        oos2_pf = r["periods"].get("OOS-2", {}).get("profit_factor", 0)
        avg_pf = r["avg_oos_pf"]
        delta = avg_pf - base_pf if test_name != "BASE" else 0

        if delta > 0.05:
            effect = "✅ İYİLEŞTİ"
        elif delta > -0.05:
            effect = "➖ NÖTR"
        else:
            effect = "❌ KÖTÜLEŞ"

        if test_name == "BASE":
            effect = "REFERANS"

        desc_short = r["desc"][:32]
        print(f"  {test_name:<20s} │ {desc_short:<32s} │ {oos1_pf:>8.2f} │ {oos2_pf:>8.2f} │ {avg_pf:>7.2f} │ {delta:>+5.2f} │ {effect}")

    # ═══════════════════════════════════════════════════
    # TEŞHİS
    # ═══════════════════════════════════════════════════

    print("\n" + "=" * 70)
    print("OVERFİTTİNG TEŞHİSİ")
    print("=" * 70)

    overfitted = []
    beneficial = []
    neutral = []

    for test_name, delta in improvements.items():
        if delta > 0.05:
            overfitted.append((test_name, delta))
            print(f"\n  ❌ {test_name}: OOS +{delta:.2f} PF → Bu bileşen OVERFİTTED!")
            print(f"     → {TEST_CONFIGS[test_name]['desc']}")
        elif delta > -0.05:
            neutral.append((test_name, delta))
        else:
            beneficial.append((test_name, delta))
            print(f"\n  ✅ {test_name}: OOS {delta:+.2f} PF → Bu bileşen YARDIMCI")
            print(f"     → {TEST_CONFIGS[test_name]['desc']}")

    if overfitted:
        print(f"\n  📋 OVERFİTTED BİLEŞENLER ({len(overfitted)}):")
        for name, delta in sorted(overfitted, key=lambda x: -x[1]):
            print(f"     • {name}: +{delta:.2f} (kaldırılmalı)")

    if "T8_COMBINED" in all_results:
        combined_pf = all_results["T8_COMBINED"]["avg_oos_pf"]
        print(f"\n  🔧 KOMBİNE SONUÇ (overfitted olanlar kapalı):")
        print(f"     BASE OOS PF:     {base_pf:.2f}")
        print(f"     COMBINED OOS PF: {combined_pf:.2f}")
        improvement = ((combined_pf / max(base_pf, 0.01)) - 1) * 100
        print(f"     İyileşme:        {improvement:+.1f}%")

        if combined_pf >= 1.0:
            print(f"\n  ✅ KURTARMA BAŞARILI → OOS PF ≥ 1.0 — v17 adayı!")
        elif combined_pf >= 0.9:
            print(f"\n  ⚠️ KURTARMA KISMI → OOS PF 0.9-1.0 — ek iyileştirme gerekli")
        else:
            print(f"\n  ❌ KURTARMA BAŞARISIZ → Temel strateji değişikliği gerekli")

    # ═══════════════════════════════════════════════════
    # DOSYAYA KAYDET
    # ═══════════════════════════════════════════════════

    report = {
        "test_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "ablation_test",
        "baseline_avg_oos_pf": base_pf,
        "tests": all_results,
        "overfitted_components": [name for name, _ in overfitted],
        "improvements": {k: round(v, 3) for k, v in improvements.items()},
    }

    report_path = "backtest/ablation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Rapor kaydedildi: {report_path}")

    return all_results


if __name__ == "__main__":
    run_ablation_test()
