"""
NECHH ROBOTICS — formatter_v2.py
Mesaj disiplinine tam uyumlu. Trade dili YOK.
Dil: İngilizce ana, Türkçe parantez açıklama.
"""

from datetime import datetime
from typing import Optional

FOOTER = (
    "\n\n💡 Market observation for educational purposes.\n"
    "⚖️ This is analysis, not financial advice.\n"
    "💡 Security: NECHH never DMs users.\n\n"
    "🔹 Nechh | Algorithmic Market Analysis-CRYPTO\n"
    "   https://nechh-robotics-website.vercel.app"
)

DIV = "━" * 30

def _now():
    return datetime.utcnow().strftime("%d.%m.%Y  %H:%M UTC")

def _bar(val, mx=100, n=10):
    f = max(0, min(n, int((val/mx)*n))) if mx else 0
    return "█"*f + "░"*(n-f)


# ── 1. SETUP ACTIVATED (Pozisyon Açıldı) ─────────────────────────────────────
def setup_activated(
    symbol: str,
    structure: str,        # "Liquidity Sweep" / "Breakout Retest" vs.
    session: str,          # "NY" / "London" / "Asia"
    entry_zone_low: float,
    entry_zone_high: float,
    invalidation: float,
    target: float,
    leverage: int = 1,
    market: str = "FUTURES",
) -> str:
    lev = f"\nLeverage (Kaldıraç): {leverage}x" if leverage > 1 else ""
    mkt = "⚡ FUTURES" if market == "FUTURES" else "🪙 SPOT"

    return (
        f"🧠 SETUP ACTIVATED | {symbol}\n"
        f"{DIV}\n\n"
        f"Market: {mkt}\n"
        f"Structure (Yapı): {structure}\n"
        f"Session (Seans): {session}{lev}\n\n"
        f"Entry Zone (Giriş Bölgesi): {entry_zone_low:,.2f} – {entry_zone_high:,.2f}\n"
        f"Invalidation (İptal Seviyesi): {invalidation:,.2f}\n"
        f"Target Mapping (Hedef): {target:,.2f}\n\n"
        f"Structured execution model.\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 2. EXECUTION CLOSED (Pozisyon Kapandı) ───────────────────────────────────
def execution_closed(
    symbol: str,
    outcome: str,          # "Target Reached" / "Invalidated"
    rr: float,             # Risk/Reward — PnL değil
    session: str,
    note: str = "Model respected structural projection.",
) -> str:
    icon = "✅" if "Target" in outcome else "❌"

    return (
        f"📊 EXECUTION CLOSED | {symbol}\n"
        f"{DIV}\n\n"
        f"Outcome (Sonuç): {outcome} {icon}\n"
        f"RR (Risk/Ödül): {rr:.1f}\n"
        f"Session (Seans): {session}\n\n"
        f"{note}\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 3. FIRSAT AVCISI / OPPORTUNITY ALERT ─────────────────────────────────────
def opportunity_alert(
    symbol: str,
    change_pct: float,
    volume: str,           # "14575.0K" formatında string
    note: str = "",
) -> str:
    direction = "📈" if change_pct >= 0 else "📉"
    sign = "+" if change_pct >= 0 else ""

    return (
        f"🦅 OPPORTUNITY DETECTED | {symbol}\n"
        f"(Fırsat Tespit Edildi)\n"
        f"{DIV}\n\n"
        f"Change (Değişim): {direction} {sign}{change_pct:.1f}%\n"
        f"Volume (Hacim): {volume}\n"
        f"{f'Note: {note}' if note else ''}\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 4. MARKET RADAR (Saat başı borsa taraması) ───────────────────────────────
def market_radar(coins: list) -> str:
    """
    coins: [
      {
        "symbol": "BTCUSDT",
        "structure": "NEUTRAL",  # BULLISH / BEARISH / NEUTRAL
        "liq_high": 69500.0,
        "liq_low": 67200.0,
        "inefficiency_zones": 2,
        "pool_clusters": 7,
        "note": "Liquidity accumulation observed."
      }
    ]
    """
    blocks = ""
    for c in coins:
        struct = c.get("structure", "NEUTRAL")
        struct_icon = "🟢" if struct == "BULLISH" else "🔴" if struct == "BEARISH" else "⚪"

        blocks += (
            f"🧠 MARKET RADAR | {c['symbol']}\n\n"
            f"Structure (Yapı): {struct_icon} {struct}\n"
            f"Liquidity Pool High: {c.get('liq_high', 0):,.2f}\n"
            f"Liquidity Pool Low:  {c.get('liq_low', 0):,.2f}\n\n"
            f"📈 Activity Metrics (Aktivite):\n"
            f"• Inefficiency Zones: {c.get('inefficiency_zones', 0)}\n"
            f"• Pool Clusters: {c.get('pool_clusters', 0)}\n\n"
            f"{c.get('note', 'Price moving within balance area.')}\n\n"
            f"⚠️ No buy/sell signals. (Al/Sat sinyali yok.)\n"
            f"⚠️ No targets. (Hedef yok.)\n\n"
            f"{'─'*20}\n\n"
        )

    return (
        f"📡 NECHH RADAR | DEEP ANALYSIS\n"
        f"{DIV}\n\n"
        f"{blocks}"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 5. RADAR EVENT / AI ANALİZ (09:00, 12:00, 20:00) ────────────────────────
def radar_event(
    symbol: str,
    analysis_text: str,    # Ollama'dan gelen metin
    quote: str = "Markets may appear chaotic, but beneath the surface lies mathematical order.",
) -> str:
    return (
        f"🌍 RADAR EVENT | {symbol}\n"
        f"🔍 TYPE: MARKET DISCOVERY\n"
        f"📅 {_now()}\n"
        f"{DIV}\n\n"
        f"NECHH Says (NECHH Diyor ki):\n"
        f'"{quote}"\n\n'
        f"{DIV}\n\n"
        f"{analysis_text}\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 6. DAILY SUMMARY (Her gün 20:00) ─────────────────────────────────────────
def daily_summary(
    total_setups: int,
    wins: int,
    losses: int,
    avg_rr: float,
    market_condition: str,  # "Trending" / "Volatile" / "Ranging"
    note: str = "Discipline over emotion.",
) -> str:
    no_setup = total_setups == 0

    body = (
        f"No setups executed today.\n"
        f"System monitored. No valid structure formed.\n"
        if no_setup else
        f"Total Setups (Toplam): {total_setups}\n"
        f"Wins (Kazanan): {wins}\n"
        f"Losses (Kaybeden): {losses}\n"
        f"Average RR (Ort. Risk/Ödül): {avg_rr:.1f}\n\n"
        f"Market Condition (Piyasa Durumu): {market_condition}\n"
    )

    return (
        f"📈 DAILY EXECUTION SUMMARY\n"
        f"(Günlük Özet)\n"
        f"{DIV}\n\n"
        f"{body}\n"
        f"{note}\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 7. WEEKLY REPORT (Pazar 18:00) ───────────────────────────────────────────
def weekly_report(
    week_no: int,
    total_trades: int,
    wins: int,
    losses: int,
    win_rate: float,
    avg_rr: float,
    dominant_structure: str,
    ai_analysis: str = "",
    mode: str = "PAPERTRADE",
) -> str:
    return (
        f"📅 WEEKLY PERFORMANCE REPORT\n"
        f"(Haftalık Performans Raporu)\n"
        f"Week #{week_no} | {mode}\n"
        f"{DIV}\n\n"
        f"Total Trades (Toplam İşlem): {total_trades}\n"
        f"Win Rate (Başarı Oranı): {win_rate:.1f}%\n"
        f"Wins / Losses: {wins} / {losses}\n"
        f"Average RR (Ort. Risk/Ödül): {avg_rr:.1f}\n\n"
        f"Dominant Structure (Baskın Yapı):\n"
        f"{dominant_structure}\n\n"
        f"{f'Market Analysis:{chr(10)}{ai_analysis}{chr(10)}{chr(10)}' if ai_analysis else ''}"
        f"Controlled execution maintained.\n"
        f"(Disiplinli uygulama korundu.)\n"
        f"{DIV}\n"
        f"🕐 {_now()}"
        f"{FOOTER}"
    )


# ── 8. WAR MACHINE HEALTH (iç kullanım / admin) ──────────────────────────────
def health_report(
    uptime: str,
    ticks: int,
    balance: float,
    equity: float,
    pnl: float,
    wins: int,
    losses: int,
    win_rate: float,
    max_dd: float,
    sentiment: Optional[float] = None,
    mode: str = "PAPERTRADE",
) -> str:
    sign = "+" if pnl >= 0 else ""
    icon = "🟢" if pnl >= 0 else "🔴"
    sent_line = (
        f"🧠 Sentiment: [{_bar(sentiment)}] {sentiment:.0f}\n"
        if sentiment is not None else
        "🧠 Sentiment: Connecting...\n"
    )
    return (
        f"📊 WAR MACHINE HEALTH | {mode}\n"
        f"{DIV}\n\n"
        f"⏱ Uptime: {uptime}\n"
        f"🔁 Ticks: {ticks:,}\n\n"
        f"💼 Balance: ${balance:,.2f}\n"
        f"📈 Equity:  ${equity:,.2f}\n"
        f"{icon} PnL: {sign}${pnl:.2f}\n\n"
        f"{DIV}\n"
        f"W: {wins}  L: {losses}  WR: {win_rate:.1f}%\n"
        f"Max DD: {max_dd:.2f}%\n\n"
        f"{sent_line}"
        f"{DIV}\n"
        f"✅ Transparency: All executions logged.\n"
        f"🕐 {_now()}"
    )


# ── 9. MARKETING (Ayda max 2) ─────────────────────────────────────────────────
def access_reminder() -> str:
    return (
        f"🔒 PRIVATE ACCESS REVIEW OPEN\n"
        f"{DIV}\n\n"
        f"Limited structured access available.\n"
        f"Manual approval required.\n\n"
        f"Apply via website:\n"
        f"https://nechh-robotics-website.vercel.app\n"
        f"{DIV}"
        f"{FOOTER}"
    )


# ── TEST ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(setup_activated(
        "BTCUSDT", "Liquidity Sweep (Likidite Süpürmesi)",
        "NY", 69100, 69200, 68900, 69750, leverage=3
    ))
    print("\n" + "="*50 + "\n")
    print(execution_closed("BTCUSDT", "Target Reached", 1.8, "NY"))
    print("\n" + "="*50 + "\n")
    print(daily_summary(3, 2, 1, 1.5, "Volatile Trend"))
    print("\n" + "="*50 + "\n")
    print(market_radar([
        {"symbol":"BTCUSDT","structure":"NEUTRAL",
         "liq_high":69500,"liq_low":67200,
         "inefficiency_zones":2,"pool_clusters":7},
        {"symbol":"ETHUSDT","structure":"BULLISH",
         "liq_high":2152,"liq_low":1989,
         "inefficiency_zones":0,"pool_clusters":5},
    ]))
