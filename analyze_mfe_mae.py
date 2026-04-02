"""
MFE/MAE Analysis - Quant Approach
==================================
Analyzes Max Favorable Excursion (MFE) and Max Adverse Excursion (MAE)
to determine if TP/SL are optimally placed.

MFE: How far did the trade go in your favor?
MAE: How far did the trade go against you?

Key insights:
- If MFE < TP frequently → TP too far
- If MAE < SL frequently → SL too tight
- If MFE >> TP → leaving money on table
"""

import sqlite3
from datetime import datetime
from typing import List, Dict

def analyze_mfe_mae():
    """Analyze MFE/MAE from closed trades"""
    
    conn = sqlite3.connect("data/war_machine.db")
    cursor = conn.cursor()
    
    # Get all closed trades with MFE/MAE
    cursor.execute("""
        SELECT symbol, side, entry_price, exit_price, 
               gross_pnl, net_pnl, mfe, mae, reason, strategy
        FROM trades
        ORDER BY exit_time DESC
    """)
    
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        print("No trades yet. Need at least 10 trades for meaningful analysis.")
        return
    
    print(f"\n{'='*70}")
    print(f"MFE/MAE ANALYSIS - {len(trades)} trades")
    print(f"{'='*70}\n")
    
    # Separate winners and losers
    winners = [t for t in trades if t[5] > 0]  # net_pnl > 0
    losers = [t for t in trades if t[5] <= 0]
    
    print(f"📊 TRADE BREAKDOWN")
    print(f"  Winners: {len(winners)}")
    print(f"  Losers: {len(losers)}")
    print(f"  Win Rate: {len(winners)/len(trades)*100:.1f}%\n")
    
    # MFE Analysis (Winners)
    if winners:
        print(f"✅ WINNERS - MFE Analysis")
        print(f"  (How far did winning trades go in profit?)\n")
        
        mfe_values = [t[6] * 100 for t in winners if t[6] > 0]  # Convert to %
        if mfe_values:
            avg_mfe = sum(mfe_values) / len(mfe_values)
            max_mfe = max(mfe_values)
            min_mfe = min(mfe_values)
            
            print(f"  Avg MFE: {avg_mfe:.2f}%")
            print(f"  Max MFE: {max_mfe:.2f}%")
            print(f"  Min MFE: {min_mfe:.2f}%")
            
            # Compare to current TP (8%)
            current_tp = 8.0
            hit_tp = sum(1 for mfe in mfe_values if mfe >= current_tp)
            print(f"\n  Current TP: {current_tp}%")
            print(f"  Trades that reached TP: {hit_tp}/{len(mfe_values)} ({hit_tp/len(mfe_values)*100:.1f}%)")
            
            if avg_mfe < current_tp * 0.7:
                print(f"  ⚠️  WARNING: Avg MFE < 70% of TP → TP might be too far")
            elif avg_mfe > current_tp * 1.3:
                print(f"  💡 OPPORTUNITY: Avg MFE > 130% of TP → Consider increasing TP")
            else:
                print(f"  ✅ TP placement looks reasonable")
        print()
    
    # MAE Analysis (Losers)
    if losers:
        print(f"❌ LOSERS - MAE Analysis")
        print(f"  (How far did losing trades go against you?)\n")
        
        mae_values = [abs(t[7]) * 100 for t in losers if t[7] < 0]  # Convert to %, abs value
        if mae_values:
            avg_mae = sum(mae_values) / len(mae_values)
            max_mae = max(mae_values)
            min_mae = min(mae_values)
            
            print(f"  Avg MAE: {avg_mae:.2f}%")
            print(f"  Max MAE: {max_mae:.2f}%")
            print(f"  Min MAE: {min_mae:.2f}%")
            
            # Compare to current SL (2.5%)
            current_sl = 2.5
            hit_sl = sum(1 for mae in mae_values if mae >= current_sl)
            print(f"\n  Current SL: {current_sl}%")
            print(f"  Trades that hit SL: {hit_sl}/{len(mae_values)} ({hit_sl/len(mae_values)*100:.1f}%)")
            
            if avg_mae < current_sl * 0.5:
                print(f"  💡 OPPORTUNITY: Avg MAE < 50% of SL → SL might be too wide")
            elif avg_mae > current_sl * 0.9:
                print(f"  ⚠️  WARNING: Avg MAE > 90% of SL → Most trades hitting SL (noise?)")
            else:
                print(f"  ✅ SL placement looks reasonable")
        print()
    
    # Exit reason breakdown
    print(f"📋 EXIT REASON BREAKDOWN\n")
    reasons = {}
    for t in trades:
        reason = t[8]
        reasons[reason] = reasons.get(reason, 0) + 1
    
    for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(trades) * 100
        print(f"  {reason}: {count} ({pct:.1f}%)")
    
    print(f"\n{'='*70}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS\n")
    
    if len(trades) < 30:
        print(f"  ⚠️  Sample size: {len(trades)} trades (need 30+ for reliable analysis)")
    
    if winners and mfe_values:
        tp_hit_rate = hit_tp / len(mfe_values) * 100
        if tp_hit_rate < 20:
            print(f"  🔴 TP hit rate {tp_hit_rate:.1f}% < 20% → Consider lowering TP")
        elif tp_hit_rate > 50:
            print(f"  🟢 TP hit rate {tp_hit_rate:.1f}% > 50% → TP working well")
    
    if losers and mae_values:
        sl_hit_rate = hit_sl / len(mae_values) * 100
        if sl_hit_rate > 80:
            print(f"  🔴 SL hit rate {sl_hit_rate:.1f}% > 80% → SL might be too tight (noise)")
        elif sl_hit_rate < 40:
            print(f"  🟢 SL hit rate {sl_hit_rate:.1f}% < 40% → SL placement good")
    
    print()

if __name__ == "__main__":
    analyze_mfe_mae()
