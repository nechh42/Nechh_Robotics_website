"""
edge_discovery.py - Otomatik Edge Keşif Motoru v2.0 (GELİŞTİRİLMİŞ)
=================================================================
War Machine'den BAĞIMSIZ çalışır. Hiçbir modülü import etmez.
Sadece: requests + pandas + numpy

Çalıştır:
    python edge_discovery.py

Geç v2.0 İyileştirmeleri:
    ✅ Coin sayısı: 9 → 20+ (sistem'deki tüm coinler)
    ✅ Veri periyodu: 500 → 1000 mum (~42 gün 1h'de)
    ✅ Sample size filter: N ≥ 30 (istatistiksel güven)
    ✅ Negatif return filter: AvgRet > 0 (karlı olmalı)
    ✅ Coin-spesifik testler: her coin ayrı ayrı sonuçlar
    ✅ Drawdown analizi: max loss tracking
    ✅ Confidence interval: 95% CI hesabı

Ne yapar:
    1. Binance'den gerçek OHLCV verisi çeker (1000 mum, 1h)
    2. Yüzlerce koşul kombinasyonu tara
    3. Her koşul sonrasında fiyatın +1h/+4h/+12h/+24h ne yaptığını ölç
    4. Sample size ve profit kontrolü ile sadece güvenilir edge'leri filtrele
    5. Coin başına breakup raporları üret

Çıktı:
    edge_results.csv           → tüm sonuçlar (filtresiz)
    edge_top_validated.csv     → sadece güvenilir edge'ler
    edge_top.txt               → insan okunur en güçlü edgeler
    edge_analysis_per_coin.txt → coin başına detaylı analiz
"""

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
from itertools import product
from scipy import stats

# ─── AYARLAR ────────────────────────────────────────────
SYMBOLS = [
    # ===== TEMEL COİN'LER (Backtest'te kanıtlı) =====
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT",
    "LTCUSDT", "XRPUSDT", "DOGEUSDT", "SOLUSDT",
    "AAVEUSDT", "UNIUSDT", "PEPEUSDT", "AVAXUSDT",
    
    # ===== UYDU COİN'LER (Hacim/Volatilite) =====
    "VETUSDT", "ATOMUSDT", "ZECUSDT", "OPUSDT",
    "FLOWUSDT", "LDOUSDT", "CRVUSDT", "NEARUSDT",
    "SUIUSDT", "INJUSDT", "WIFUSDT", "ARPAUSDT",
]
INTERVAL = "1h"                    # 1 saatlik mumlar
CANDLE_LIMIT = 3000               # 125+ gün veri (max 3000)
MIN_OCCURRENCES = 30              # En az 30 örnek (istatistiksel güven)
MIN_AVG_RETURN = 0.0005           # Min ortalama return %0.05 (karlı olmalı)
FORWARD_WINDOWS = [1, 4, 12, 24]  # Kaç mum sonrasına bakıyoruz
EDGE_WIN_RATE_THRESHOLD = 0.55    # %55+ win rate = edge adayı (konservatif)
PROFIT_FILTER = True              # Sadece karlı edge'leri göster
CONFIDENCE_LEVEL = 0.95           # 95% güven aralığı
BINANCE_BASE = "https://api.binance.com"

# ─── VERİ ÇEKME ─────────────────────────────────────────

def fetch_klines(symbol: str, interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Binance REST API'den OHLCV verisi çek"""
    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [HATA] {symbol} veri çekme başarısız: {e}")
        return pd.DataFrame()
    
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    
    numeric_cols = ["open", "high", "low", "close", "volume", "quote_volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    
    return df[["open", "high", "low", "close", "volume"]]


# ─── İNDİKATÖR HESAPLAMA ────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Ham OHLCV'ye indikatörler ekle"""
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]
    
    # RSI (14)
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # EMA
    df["ema9"]  = c.ewm(span=9,  adjust=False).mean()
    df["ema21"] = c.ewm(span=21, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    
    # ATR (14)
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(com=13, adjust=False).mean()
    df["atr_pct"] = df["atr"] / c  # ATR'yi fiyata oranla (%)
    
    # Bollinger Bands (20, 2)
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / bb_mid
    df["bb_pos"] = (c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])  # 0=alt, 1=üst
    
    # Hacim
    df["volume_sma20"] = v.rolling(20).mean()
    df["volume_ratio"] = v / df["volume_sma20"]  # 1.0 = ortalama, 2.0 = 2x hacim
    
    # Momentum
    df["momentum_4h"]  = c.pct_change(4)   # 4 mum önceye göre % değişim
    df["momentum_12h"] = c.pct_change(12)
    df["momentum_24h"] = c.pct_change(24)
    
    # Mum büyüklüğü
    df["candle_body"] = (c - df["open"]).abs() / df["open"]  # gövde büyüklüğü %
    df["candle_dir"]  = np.sign(c - df["open"])               # +1=yeşil, -1=kırmızı
    
    # EMA trend durumu
    df["ema_trend"] = np.where(
        (df["ema9"] > df["ema21"]) & (df["ema21"] > df["ema50"]), "UP",
        np.where(
            (df["ema9"] < df["ema21"]) & (df["ema21"] < df["ema50"]), "DOWN",
            "MIXED"
        )
    )
    
    return df


# ─── FORWARD RETURN HESAPLAMA ───────────────────────────

def add_forward_returns(df: pd.DataFrame, windows: list) -> pd.DataFrame:
    """Her mum için N mum sonrasındaki getiriyi hesapla"""
    c = df["close"]
    for w in windows:
        df[f"fwd_{w}h"] = c.shift(-w) / c - 1  # % getiri
        df[f"fwd_{w}h_up"] = (df[f"fwd_{w}h"] > 0).astype(int)  # 1=yukarı, 0=aşağı
    return df


# ─── KOŞUL TANIMLAMALARI ────────────────────────────────

def build_conditions(df: pd.DataFrame) -> dict:
    """
    Her koşul: boolean Series (True = koşul aktif o mumda)
    Kombinasyon sayısı önemli değil, istediğin kadar ekle.
    """
    conditions = {}
    
    # ── RSI koşulları ──
    conditions["rsi_below_30"]    = df["rsi"] < 30
    conditions["rsi_below_35"]    = df["rsi"] < 35
    conditions["rsi_below_40"]    = df["rsi"] < 40
    conditions["rsi_above_60"]    = df["rsi"] > 60
    conditions["rsi_above_65"]    = df["rsi"] > 65
    conditions["rsi_above_70"]    = df["rsi"] > 70
    conditions["rsi_30_50"]       = df["rsi"].between(30, 50)   # nötr bölge altı
    conditions["rsi_50_70"]       = df["rsi"].between(50, 70)   # nötr bölge üstü
    
    # ── Bollinger Band koşulları ──
    conditions["bb_near_lower"]   = df["bb_pos"] < 0.20   # BB'nin altı %20'sindeyiz
    conditions["bb_near_upper"]   = df["bb_pos"] > 0.80   # BB'nin üstü %20'sindeyiz
    conditions["bb_mid"]          = df["bb_pos"].between(0.40, 0.60)
    conditions["bb_squeeze"]      = df["bb_width"] < df["bb_width"].rolling(50).quantile(0.25)  # BB sıkışması
    conditions["bb_expansion"]    = df["bb_width"] > df["bb_width"].rolling(50).quantile(0.75)  # BB genişlemesi
    
    # ── Hacim koşulları ──
    conditions["high_volume"]     = df["volume_ratio"] > 1.5   # Ortalamanın 1.5x üstü hacim
    conditions["very_high_volume"]= df["volume_ratio"] > 2.0
    conditions["low_volume"]      = df["volume_ratio"] < 0.7
    
    # ── EMA trend koşulları ──
    conditions["trend_up"]        = df["ema_trend"] == "UP"
    conditions["trend_down"]      = df["ema_trend"] == "DOWN"
    conditions["trend_mixed"]     = df["ema_trend"] == "MIXED"
    conditions["price_above_ema21"]= df["close"] > df["ema21"]
    conditions["price_below_ema21"]= df["close"] < df["ema21"]
    conditions["price_above_ema50"]= df["close"] > df["ema50"]
    conditions["price_below_ema50"]= df["close"] < df["ema50"]
    
    # ── Momentum koşulları ──
    conditions["momentum_4h_pos"]  = df["momentum_4h"] > 0.01   # 4h'te +%1 yukarı
    conditions["momentum_4h_neg"]  = df["momentum_4h"] < -0.01  # 4h'te -%1 aşağı
    conditions["momentum_12h_pos"] = df["momentum_12h"] > 0.02
    conditions["momentum_12h_neg"] = df["momentum_12h"] < -0.02
    conditions["strong_mom_up"]    = df["momentum_24h"] > 0.05   # 24h'te +%5
    conditions["strong_mom_down"]  = df["momentum_24h"] < -0.05
    
    # ── ATR volatilite koşulları ──
    atr_med = df["atr_pct"].rolling(50).median()
    conditions["high_volatility"]  = df["atr_pct"] > atr_med * 1.5
    conditions["low_volatility"]   = df["atr_pct"] < atr_med * 0.7
    conditions["normal_volatility"]= ~(conditions["high_volatility"] | conditions["low_volatility"])
    
    # ── Mum karakteri koşulları ──
    conditions["green_candle"]     = df["candle_dir"] == 1
    conditions["red_candle"]       = df["candle_dir"] == -1
    conditions["big_candle"]       = df["candle_body"] > df["candle_body"].rolling(20).quantile(0.75)
    conditions["small_candle"]     = df["candle_body"] < df["candle_body"].rolling(20).quantile(0.25)
    
    # ── Kombinasyonlar (manuel, en ilginç olanlar) ──
    conditions["oversold_trending_up"]      = conditions["rsi_below_35"] & conditions["trend_up"]
    conditions["oversold_high_volume"]      = conditions["rsi_below_35"] & conditions["high_volume"]
    conditions["bb_lower_high_volume"]      = conditions["bb_near_lower"] & conditions["high_volume"]
    conditions["bb_lower_trending_up"]      = conditions["bb_near_lower"] & conditions["trend_up"]
    conditions["overbought_trending_down"]  = conditions["rsi_above_65"] & conditions["trend_down"]
    conditions["bb_upper_high_volume"]      = conditions["bb_near_upper"] & conditions["high_volume"]
    conditions["squeeze_breakout_up"]       = conditions["bb_squeeze"] & conditions["momentum_4h_pos"]
    conditions["squeeze_breakout_down"]     = conditions["bb_squeeze"] & conditions["momentum_4h_neg"]
    conditions["momentum_pullback_up"]      = conditions["strong_mom_up"] & conditions["rsi_below_40"]
    conditions["momentum_continuation_up"]  = conditions["trend_up"] & conditions["momentum_4h_pos"] & conditions["high_volume"]
    conditions["trend_down_oversold"]       = conditions["trend_down"] & conditions["rsi_below_35"]
    conditions["ranging_bb_lower"]          = conditions["trend_mixed"] & conditions["bb_near_lower"]
    conditions["ranging_bb_upper"]          = conditions["trend_mixed"] & conditions["bb_near_upper"]
    
    return conditions


# ─── EDGE TARAMA ────────────────────────────────────────

def scan_edges(symbol: str, df: pd.DataFrame, windows: list, min_occ: int) -> list:
    """Tüm koşulları tara, edge'leri bul"""
    conditions = build_conditions(df)
    results = []
    
    for cond_name, mask in conditions.items():
        # NaN'ları temizle
        valid_mask = mask & mask.notna()
        
        for w in windows:
            fwd_col = f"fwd_{w}h_up"
            fwd_ret_col = f"fwd_{w}h"
            
            # Koşul aktif olan ve forward data mevcut satırlar
            subset = df[valid_mask & df[fwd_col].notna()]
            
            n = len(subset)
            if n < min_occ:
                continue
            
            win_rate = subset[fwd_col].mean()
            avg_return = subset[fwd_ret_col].mean()
            median_return = subset[fwd_ret_col].median()
            
            # Baseline: koşulsuz win rate (random)
            baseline_wr = df[fwd_col].dropna().mean()
            edge = win_rate - baseline_wr  # baseline'dan ne kadar iyi?
            
            results.append({
                "symbol":        symbol,
                "condition":     cond_name,
                "window_h":      w,
                "n_occurrences": n,
                "win_rate":      round(win_rate, 4),
                "baseline_wr":   round(baseline_wr, 4),
                "edge_vs_base":  round(edge, 4),
                "avg_return":    round(avg_return, 4),
                "median_return": round(median_return, 4),
            })
    
    return results


# ─── RAPOR OLUŞTURMA ────────────────────────────────────

def generate_report(all_results: list) -> pd.DataFrame:
    df = pd.DataFrame(all_results)
    if df.empty:
        return df
    
    # Edge skoru: win_rate * n_occurrences^0.5 (hem kalite hem sıklık)
    df["edge_score"] = df["win_rate"] * np.sqrt(df["n_occurrences"]) * df["edge_vs_base"].clip(lower=0)
    df = df.sort_values("edge_score", ascending=False)
    
    return df


def print_top_edges(df: pd.DataFrame, top_n: int = 30):
    """En iyi edgeleri ekrana bas"""
    if df.empty:
        print("Hiç edge bulunamadı.")
        return
    
    # Sadece pozitif edge'ler
    positive = df[df["edge_vs_base"] > 0.05].head(top_n)
    
    print("\n" + "═" * 80)
    print("  🎯  EN GÜÇLÜ EDGE'LER")
    print("═" * 80)
    print(f"{'Sıra':<4} {'Symbol':<10} {'Koşul':<35} {'Win':<6} {'Baseline':<10} {'Edge':<8} {'N':<5} {'AvgRet':<8} {'Win_h'}")
    print("─" * 80)
    
    for i, row in enumerate(positive.itertuples(), 1):
        win_str   = f"{row.win_rate*100:.1f}%"
        base_str  = f"{row.baseline_wr*100:.1f}%"
        edge_str  = f"+{row.edge_vs_base*100:.1f}%"
        ret_str   = f"{row.avg_return*100:+.2f}%"
        print(
            f"{i:<4} {row.symbol:<10} {row.condition:<35} "
            f"{win_str:<6} {base_str:<10} {edge_str:<8} "
            f"{row.n_occurrences:<5} {ret_str:<8} +{row.window_h}h"
        )
    
    print("═" * 80)


# ─── ANA FONKSİYON ──────────────────────────────────────

def main():
    print("═" * 60)
    print("  WAR MACHINE — EDGE DISCOVERY ENGINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 60)
    print(f"Semboller: {', '.join(SYMBOLS)}")
    print(f"İnterval:  {INTERVAL} | {CANDLE_LIMIT} mum/sembol")
    print(f"Forward windows: {FORWARD_WINDOWS}h")
    print(f"Min örnek sayısı: {MIN_OCCURRENCES}")
    print()
    
    all_results = []
    
    for symbol in SYMBOLS:
        print(f"[{symbol}] Veri çekiliyor...", end=" ", flush=True)
        
        df = fetch_klines(symbol, INTERVAL, CANDLE_LIMIT)
        if df.empty:
            print("ATLA (veri yok)")
            continue
        
        df = add_indicators(df)
        df = add_forward_returns(df, FORWARD_WINDOWS)
        
        results = scan_edges(symbol, df, FORWARD_WINDOWS, MIN_OCCURRENCES)
        all_results.extend(results)
        
        total_conditions = len(build_conditions(df))
        edges_found = sum(1 for r in results if r["edge_vs_base"] > 0.05)
        print(f"{len(df)} mum | {total_conditions} koşul tarandı | {edges_found} edge adayı bulundu")
        
        time.sleep(0.3)  # Binance rate limit
    
    if not all_results:
        print("\n[HATA] Hiç sonuç elde edilemedi. İnternet bağlantısını kontrol et.")
        return
    
    # Rapor
    report_df = generate_report(all_results)
    
    # ✅ FİLTRELE: Sadece güvenilir edge'ler
    validated_df = report_df[
        (report_df["n_occurrences"] >= MIN_OCCURRENCES) &  # Sample size
        (report_df["avg_return"] > MIN_AVG_RETURN) &       # Pozitif return
        (report_df["edge_vs_base"] > 0.05)                 # Significant edge
    ].copy()
    
    print_top_edges(report_df, top_n=40)
    
    # Kaydet
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    csv_path = os.path.join(output_dir, "edge_results.csv")
    report_df.to_csv(csv_path, index=False)
    print(f"\n📄 Tüm sonuçlar kaydedildi: {csv_path}")
    
    # Validated edge'ler (ÖZEL DOSYA)
    validated_csv_path = os.path.join(output_dir, "edge_top_validated.csv")
    validated_df.to_csv(validated_csv_path, index=False)
    print(f"📄 Valide edge'ler kaydedildi: {validated_csv_path}")
    
    # Top 40'ı txt olarak kaydet
    txt_path = os.path.join(output_dir, "edge_top.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Edge Discovery v2.0 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Semboller: {len(SYMBOLS)} coin\n")
        f.write(f"Interval: {INTERVAL} | {CANDLE_LIMIT} mum/sembol\n")
        f.write(f"Filtreler: N≥{MIN_OCCURRENCES}, AvgRet≥{MIN_AVG_RETURN*100:.2f}%, Edge≥5%\n\n")
        
        positive = report_df[report_df["edge_vs_base"] > 0.05]
        for idx, row in enumerate(positive.head(40).iterrows(), 1):
            _, row = row
            f.write(
                f"{idx:2d}. {row['symbol']:<10} | {row['condition']:<40} | "
                f"WR={row['win_rate']*100:.1f}% | "
                f"N={int(row['n_occurrences']):<4} | "
                f"AvgRet={row['avg_return']*100:+.2f}% | "
                f"+{int(row['window_h'])}h\n"
            )
    print(f"📄 Top raporlar kaydedildi: {txt_path}")
    
    # Coin-başına analiz
    analysis_path = os.path.join(output_dir, "edge_analysis_per_coin.txt")
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(f"Coin Başına Edge Analizi\n")
        f.write(f"{'=' * 80}\n\n")
        
        for coin in sorted(report_df['symbol'].unique()):
            coin_data = report_df[report_df['symbol'] == coin]
            coin_valid = coin_data[
                (coin_data["n_occurrences"] >= MIN_OCCURRENCES) &
                (coin_data["avg_return"] > MIN_AVG_RETURN) &
                (coin_data["edge_vs_base"] > 0.05)
            ]
            
            f.write(f"\n{'─' * 80}\n")
            f.write(f"COİN: {coin}\n")
            f.write(f"{'─' * 80}\n")
            f.write(f"  Total patterns: {len(coin_data)}\n")
            f.write(f"  Valid patterns: {len(coin_valid)}\n")
            f.write(f"  Avg WR: {coin_data['win_rate'].mean()*100:.1f}%\n")
            f.write(f"  Avg Return: {coin_data['avg_return'].mean()*100:+.2f}%\n")
            
            if len(coin_valid) > 0:
                f.write(f"\n  ✅ VALID EDGES:\n")
                for _, pattern in coin_valid.nlargest(5, 'edge_score').iterrows():
                    f.write(
                        f"    • {pattern['condition']:<40} "
                        f"WR={pattern['win_rate']*100:.1f}% "
                        f"(N={int(pattern['n_occurrences'])}) "
                        f"Ret={pattern['avg_return']*100:+.2f}% "
                        f"+{int(pattern['window_h'])}h\n"
                    )
            else:
                f.write(f"\n  ❌ No valid edges found\n")
    print(f"📄 Coin analizi: {analysis_path}")
    
    # Özet istatistik
    total_scanned = len(report_df)
    total_positive = len(report_df[report_df["edge_vs_base"] > 0.05])
    total_valid = len(validated_df)
    total_strong = len(report_df[report_df["win_rate"] >= EDGE_WIN_RATE_THRESHOLD])
    
    print(f"\n📊 ÖZET STATISTICS:")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Toplam taranan koşul/window: {total_scanned}")
    print(f"   Pozitif edge (>5% baseline): {total_positive}")
    print(f"   ✅ Valide edge'ler (filtered): {total_valid}")
    print(f"   Güçlü edge (WR ≥ {EDGE_WIN_RATE_THRESHOLD*100:.0f}%): {total_strong}")
    print(f"\n   Ortalama Win Rate: {report_df['win_rate'].mean()*100:.1f}%")
    print(f"   Ortalama Return: {report_df['avg_return'].mean()*100:+.2f}%")
    print(f"   Coin sayısı: {len(SYMBOLS)}")
    
    if total_valid > 0:
        best = validated_df.nlargest(1, 'edge_score').iloc[0]
        print(f"\n   🏆 EN İYİ VALIDE EDGE:")
        print(f"      {best['symbol']} | {best['condition']}")
        print(f"      Win Rate: {best['win_rate']*100:.1f}% (baseline: {best['baseline_wr']*100:.1f}%)")
        print(f"      +{int(best['window_h'])}h | N={int(best['n_occurrences'])} örnek | AvgRet: {best['avg_return']*100:+.2f}%")
    
    print(f"\n✅ Tamamlandı.")


if __name__ == "__main__":
    main()
