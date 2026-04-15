"""
╔══════════════════════════════════════════════════════╗
║         NECHH ROBOTICS — formatter.py                ║
║         Bağımsız mesaj formatlayıcı modül            ║
║         Mevcut telegram.py'a hiç dokunma!            ║
╚══════════════════════════════════════════════════════╝

KULLANIM:
    from formatter import fmt

    # Mevcut telegram.py'daki her metodun içinde:
    # Eski: msg = f"..."
    # Yeni: msg = fmt.trade_alert(...) şeklinde kullan
    # Ya da tamamen eski sistemi bırak, sadece yeni kanalda kullan.
"""

from datetime import datetime
from typing import Optional


class NechhFormatter:
    """
    Nechh Robotics için profesyonel Telegram HTML mesaj şablonları.
    Tüm metodlar string döndürür — send() sizin telegram.py'dan çağrılır.
    """

    BRAND = "NECHH ROBOTICS"
    TAGLINE = "SİSTEM KONUŞUR • ŞANS DEĞİL"

    # ─────────────────────────────────────────────
    # YARDIMCI FONKSİYONLAR
    # ─────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().strftime("%d.%m.%Y  %H:%M UTC")

    @staticmethod
    def _pnl_icon(pnl: float) -> str:
        if pnl > 0:
            return "🟢"
        elif pnl < 0:
            return "🔴"
        return "⚪"

    @staticmethod
    def _bar(value: float, max_val: float = 100, length: int = 10) -> str:
        """Basit progress bar: ████░░░░░░"""
        filled = int((value / max_val) * length) if max_val else 0
        filled = max(0, min(length, filled))
        return "█" * filled + "░" * (length - filled)

    @staticmethod
    def _divider() -> str:
        return "─" * 32

    # ─────────────────────────────────────────────
    # 1. TRADE AÇILIŞ / KAPANIŞ
    # ─────────────────────────────────────────────

    def trade_open(
        self,
        symbol: str,
        side: str,           # "LONG" / "SHORT"
        entry: float,
        size: float,
        leverage: int = 1,
        tp: Optional[float] = None,
        sl: Optional[float] = None,
        market: str = "FUTURES",  # "SPOT" / "FUTURES"
    ) -> str:

        side_icon = "🟢" if side.upper() == "LONG" else "🔴"
        market_icon = "⚡" if market == "FUTURES" else "🪙"

        msg = (
            f"<b>{market_icon} {market} • POZİSYON AÇILDI</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"{side_icon} <b>#{symbol}</b>  —  <b>{side.upper()}</b>\n\n"
            f"<b>📍 Entry:</b>  <code>${entry:,.4f}</code>\n"
            f"<b>📦 Size:</b>   <code>{size:.4f}</code>\n"
        )
        if leverage > 1:
            msg += f"<b>⚙️ Kaldıraç:</b> <code>{leverage}x</code>\n"
        if tp:
            msg += f"<b>🎯 TP:</b>     <code>${tp:,.4f}</code>\n"
        if sl:
            msg += f"<b>🛡️ SL:</b>     <code>${sl:,.4f}</code>\n"

        msg += (
            f"\n<code>{self._divider()}</code>\n"
            f"<i>🕐 {self._now()}</i>\n"
            f"<i>{self.TAGLINE}</i>"
        )
        return msg

    def trade_close(
        self,
        symbol: str,
        side: str,
        entry: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        duration: str,       # örn: "2s 14dk"
        market: str = "FUTURES",
    ) -> str:

        icon = self._pnl_icon(pnl)
        sign = "+" if pnl >= 0 else ""
        result_word = "KAR ✅" if pnl >= 0 else "ZARAR ❌"
        market_icon = "⚡" if market == "FUTURES" else "🪙"

        msg = (
            f"<b>{market_icon} {market} • POZİSYON KAPANDI</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"{icon} <b>#{symbol}</b>  —  <b>{side.upper()}</b>  •  {result_word}\n\n"
            f"<b>📍 Entry:</b>   <code>${entry:,.4f}</code>\n"
            f"<b>🏁 Exit:</b>    <code>${exit_price:,.4f}</code>\n"
            f"<b>💰 PnL:</b>     <code>{sign}${pnl:.2f}  ({sign}{pnl_pct:.2f}%)</code>\n"
            f"<b>⏱ Süre:</b>    <code>{duration}</code>\n"
            f"\n<code>{self._divider()}</code>\n"
            f"<i>🕐 {self._now()}</i>\n"
            f"<i>{self.TAGLINE}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 2. WAR MACHINE HEALTH RAPORU
    # ─────────────────────────────────────────────

    def health_report(
        self,
        uptime: str,
        ticks: int,
        balance: float,
        equity: float,
        pnl: float,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        max_dd: float,
        open_positions: list,    # [{"symbol": "BTC", "side": "LONG", "pnl": 12.3}]
        sentiment: Optional[float] = None,
        mode: str = "PAPERTRADE",  # "PAPERTRADE" / "LIVE"
    ) -> str:

        mode_icon = "📋" if mode == "PAPERTRADE" else "🔴"
        pnl_icon = self._pnl_icon(pnl)
        sign = "+" if pnl >= 0 else ""

        # Win rate bar
        wr_bar = self._bar(win_rate, 100, 10)

        # Pozisyonlar
        if open_positions:
            pos_lines = ""
            for p in open_positions:
                p_icon = "🟢" if p.get("side") == "LONG" else "🔴"
                p_pnl = p.get("pnl", 0)
                p_sign = "+" if p_pnl >= 0 else ""
                pos_lines += f"  {p_icon} <code>{p['symbol']}</code>  {p_sign}${p_pnl:.2f}\n"
        else:
            pos_lines = "  <i>Açık pozisyon yok</i>\n"

        # Sentiment
        if sentiment is not None:
            sent_label = (
                "Aşırı Korku 😱" if sentiment < 25 else
                "Korku 😰" if sentiment < 45 else
                "Nötr 😐" if sentiment < 55 else
                "Açgözlülük 😏" if sentiment < 75 else
                "Aşırı Açgözlülük 🤑"
            )
            sent_bar = self._bar(sentiment, 100, 10)
            sentiment_line = f"<b>🧠 Sentiment:</b>  <code>[{sent_bar}] {sentiment:.0f}  {sent_label}</code>\n"
        else:
            sentiment_line = "<b>🧠 Sentiment:</b>  <i>Bağlanıyor...</i>\n"

        msg = (
            f"<b>📊 WAR MACHINE HEALTH</b>  {mode_icon} <code>{mode}</code>\n"
            f"<code>{self._divider()}</code>\n\n"

            f"<b>⏱ Uptime:</b>    <code>{uptime}</code>\n"
            f"<b>🔁 Ticks:</b>    <code>{ticks:,}</code>\n\n"

            f"<b>💼 Balance:</b>  <code>${balance:,.2f}</code>\n"
            f"<b>📈 Equity:</b>   <code>${equity:,.2f}</code>\n"
            f"{pnl_icon} <b>PnL:</b>       <code>{sign}${pnl:.2f}</code>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"<b>🎯 Trades:</b>   <code>{total_trades}  (W:{wins}  L:{losses})</code>\n"
            f"<b>🏆 Win Rate:</b> <code>[{wr_bar}] {win_rate:.1f}%</code>\n"
            f"<b>📉 Max DD:</b>   <code>{max_dd:.1f}%</code>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"<b>📌 Pozisyonlar ({len(open_positions)}):</b>\n"
            f"{pos_lines}\n"

            f"{sentiment_line}\n"

            f"<code>{self._divider()}</code>\n"
            f"✅ <i>Şeffaflık: Tüm işlemler kaydedilmiştir</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 3. HAFTALIK PERFORMANS RAPORU
    # ─────────────────────────────────────────────

    def weekly_report(
        self,
        week_no: int,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        gross_pnl: float,
        best_trade: dict,   # {"symbol": "BTC", "pnl": 45.2}
        worst_trade: dict,  # {"symbol": "ETH", "pnl": -8.1}
        max_dd: float,
        balance_start: float,
        balance_end: float,
        mode: str = "PAPERTRADE",
    ) -> str:

        net_pnl = balance_end - balance_start
        net_pct = ((balance_end / balance_start) - 1) * 100 if balance_start else 0
        sign = "+" if net_pnl >= 0 else ""
        result_icon = "✅" if net_pnl >= 0 else "⚠️"

        msg = (
            f"<b>📊 HAFTALIK RAPOR — Hafta #{week_no}</b>\n"
            f"<code>{self._divider()}</code>\n\n"

            f"<b>🤖 {self.BRAND}</b>\n"
            f"<i>{mode}</i>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"<b>İŞLEM ÖZETİ</b>\n"
            f"<b>📋 Toplam:</b>  <code>{total_trades}</code>\n"
            f"<b>✅ Kazanan:</b> <code>{wins}</code>\n"
            f"<b>❌ Kaybeden:</b><code>{losses}</code>\n"
            f"<b>🏆 Win Rate:</b><code>{win_rate:.1f}%</code>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"<b>PERFORMANS</b>\n"
            f"<b>💰 Net PnL:</b>  <code>{sign}${net_pnl:.2f}  ({sign}{net_pct:.2f}%)</code>  {result_icon}\n"
            f"<b>📉 Max DD:</b>   <code>{max_dd:.2f}%</code>\n\n"

            f"<b>🥇 En İyi:</b>  <code>#{best_trade['symbol']}  +${best_trade['pnl']:.2f}</code>\n"
            f"<b>🥴 En Kötü:</b> <code>#{worst_trade['symbol']}  ${worst_trade['pnl']:.2f}</code>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"<b>BAKİYE</b>\n"
            f"<b>📌 Başlangıç:</b> <code>${balance_start:,.2f}</code>\n"
            f"<b>🏁 Bitiş:</b>     <code>${balance_end:,.2f}</code>\n\n"

            f"<code>{self._divider()}</code>\n"
            f"✅ <i>Şeffaflık: Tüm işlemler kaydedilmiştir</i>\n"
            f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
            f"<i>{self.TAGLINE}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 4. SİSTEM UYARILARI
    # ─────────────────────────────────────────────

    def system_alert(self, title: str, message: str, level: str = "WARNING") -> str:
        icons = {"WARNING": "⚠️", "CRITICAL": "🚨", "INFO": "ℹ️", "OK": "✅"}
        icon = icons.get(level, "⚠️")

        msg = (
            f"{icon} <b>SİSTEM — {title}</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"{message}\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 5. LİKİDASYON UYARISI
    # ─────────────────────────────────────────────

    def liquidation_spike(
        self,
        symbol: str,
        total_liq_usd: float,
        long_liq: float,
        short_liq: float,
        dominant: str,   # "LONG" / "SHORT"
    ) -> str:

        dom_icon = "🟢 LONG taraf" if dominant == "LONG" else "🔴 SHORT taraf"

        msg = (
            f"🚨 <b>LİKİDASYON DALGASI — #{symbol}</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"<b>💥 Toplam:</b>   <code>${total_liq_usd:,.0f}</code>\n"
            f"<b>🟢 Long liq:</b> <code>${long_liq:,.0f}</code>\n"
            f"<b>🔴 Short liq:</b><code>${short_liq:,.0f}</code>\n\n"
            f"<b>⚡ Baskın:</b>   {dom_icon}\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 6. TOP 3 COIN SİNYALİ
    # ─────────────────────────────────────────────

    def top_coins_signal(self, coins: list) -> str:
        """
        coins: [
            {"symbol": "BTC", "score": 87.2, "direction": "LONG", "reason": "..."},
            ...
        ]
        """
        medals = ["🥇", "🥈", "🥉"]
        lines = ""
        for i, c in enumerate(coins[:3]):
            medal = medals[i] if i < 3 else "•"
            dir_icon = "🟢" if c.get("direction") == "LONG" else "🔴"
            lines += (
                f"{medal} <b>#{c['symbol']}</b>  {dir_icon} {c.get('direction','')}  "
                f"<code>Score: {c.get('score', 0):.1f}</code>\n"
                f"   <i>{c.get('reason', '')}</i>\n\n"
            )

        msg = (
            f"✨ <b>EDGE SİNYALİ — TOP 3</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"{lines}"
            f"<code>{self._divider()}</code>\n"
            f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
            f"<i>{self.TAGLINE}</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg

    # ─────────────────────────────────────────────
    # 7. STARTUP
    # ─────────────────────────────────────────────

    def startup(self, version: str = "v1.0", mode: str = "PAPERTRADE") -> str:
        mode_icon = "📋" if mode == "PAPERTRADE" else "🔴 LIVE"
        msg = (
            f"🟢 <b>WAR MACHINE BAŞLADI</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"<b>🤖 {self.BRAND}</b>\n"
            f"<b>⚙️ Versiyon:</b>  <code>{version}</code>\n"
            f"<b>📊 Mod:</b>       {mode_icon}\n\n"
            f"<i>Sistem aktif. Piyasa taranıyor...</i>\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<i>{self.TAGLINE}</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg


# ─────────────────────────────────────────────
# SINGLETON — import ettiğinde hazır gelir
# ─────────────────────────────────────────────
fmt = NechhFormatter()


# ─────────────────────────────────────────────
# KULLANIM ÖRNEKLERİ (çalıştırılabilir test)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("TRADE AÇILIŞ:")
    print(fmt.trade_open("BTCUSDT", "LONG", 83420.5, 0.012, leverage=10, tp=85000, sl=82000))

    print("\n" + "=" * 50)
    print("TRADE KAPANIŞ:")
    print(fmt.trade_close("BTCUSDT", "LONG", 83420.5, 85100.0, 20.16, 2.01, "4s 22dk"))

    print("\n" + "=" * 50)
    print("HEALTH RAPORU:")
    print(fmt.health_report(
        uptime="2 days, 11:17:36",
        ticks=1_825_879,
        balance=10_028.34,
        equity=10_028.34,
        pnl=28.34,
        total_trades=18,
        wins=5,
        losses=13,
        win_rate=27.8,
        max_dd=0.3,
        open_positions=[],
        sentiment=42,
        mode="PAPERTRADE",
    ))

    print("\n" + "=" * 50)
    print("HAFTALIK RAPOR:")
    print(fmt.weekly_report(
        week_no=1,
        total_trades=18,
        wins=5,
        losses=13,
        win_rate=27.8,
        gross_pnl=28.34,
        best_trade={"symbol": "ETHUSDT", "pnl": 14.2},
        worst_trade={"symbol": "SOLUSDT", "pnl": -3.1},
        max_dd=0.3,
        balance_start=10_000.0,
        balance_end=10_028.34,
        mode="PAPERTRADE",
    ))
