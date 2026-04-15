"""
NECHH ROBOTICS — formatter.py
Bağımsız mesaj formatlayıcı modül.
Mevcut telegram.py'a hiç dokunmaz.

Kullanım:
    from monitoring.formatter import fmt
    msg = fmt.trade_open(...)
"""

from datetime import datetime
from typing import Optional


class NechhFormatter:
    """Profesyonel Telegram HTML mesaj şablonları."""

    BRAND = "NECHH ROBOTICS"
    TAGLINE = "SİSTEM KONUŞUR • ŞANS DEĞİL"

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
        filled = int((value / max_val) * length) if max_val else 0
        filled = max(0, min(length, filled))
        return "█" * filled + "░" * (length - filled)

    @staticmethod
    def _divider() -> str:
        return "─" * 32

    # ── TRADE AÇILIŞ ──────────────────────────────────────

    def trade_open(
        self, symbol: str, side: str, entry: float, size: float,
        leverage: int = 1, tp: Optional[float] = None,
        sl: Optional[float] = None, market: str = "FUTURES",
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

    # ── TRADE KAPANIŞ ─────────────────────────────────────

    def trade_close(
        self, symbol: str, side: str, entry: float, exit_price: float,
        pnl: float, pnl_pct: float, duration: str, market: str = "FUTURES",
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

    # ── HEALTH RAPORU ─────────────────────────────────────

    def health_report(
        self, uptime: str, ticks: int, balance: float, equity: float,
        pnl: float, total_trades: int, wins: int, losses: int,
        win_rate: float, max_dd: float, open_positions: list,
        sentiment: Optional[float] = None, mode: str = "PAPERTRADE",
    ) -> str:
        mode_icon = "📋" if mode == "PAPERTRADE" else "🔴"
        pnl_icon = self._pnl_icon(pnl)
        sign = "+" if pnl >= 0 else ""
        wr_bar = self._bar(win_rate, 100, 10)

        if open_positions:
            pos_lines = ""
            for p in open_positions:
                p_icon = "🟢" if p.get("side") == "LONG" else "🔴"
                p_pnl = p.get("pnl", 0)
                p_sign = "+" if p_pnl >= 0 else ""
                pos_lines += f"  {p_icon} <code>{p['symbol']}</code>  {p_sign}${p_pnl:.2f}\n"
        else:
            pos_lines = "  <i>Açık pozisyon yok</i>\n"

        if sentiment is not None and sentiment >= 0:
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

    # ── HAFTALIK RAPOR ────────────────────────────────────

    def weekly_report(
        self, total_trades: int = 0, wins: int = 0, losses: int = 0,
        win_rate: float = 0, pnl: float = 0, max_dd: float = 0,
        best_trade: str = "—", worst_trade: str = "—",
        week_no: int = 0, gross_pnl: float = 0,
        balance_start: float = 0, balance_end: float = 0,
        mode: str = "PAPERTRADE",
    ) -> str:
        net_pnl = pnl if pnl else (balance_end - balance_start if balance_start else 0)
        sign = "+" if net_pnl >= 0 else ""
        result_icon = "✅" if net_pnl >= 0 else "⚠️"

        # best_trade / worst_trade: dict veya string kabul et
        if isinstance(best_trade, dict):
            best_str = f"#{best_trade['symbol']}  +${best_trade['pnl']:.2f}"
        else:
            best_str = str(best_trade)
        if isinstance(worst_trade, dict):
            worst_str = f"#{worst_trade['symbol']}  ${worst_trade['pnl']:.2f}"
        else:
            worst_str = str(worst_trade)

        msg = (
            f"<b>📊 HAFTALIK RAPOR</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"<b>🤖 {self.BRAND}</b>  •  <i>{mode}</i>\n\n"
            f"<b>İŞLEM ÖZETİ</b>\n"
            f"<b>📋 Toplam:</b>  <code>{total_trades}</code>\n"
            f"<b>✅ Kazanan:</b> <code>{wins}</code>\n"
            f"<b>❌ Kaybeden:</b><code>{losses}</code>\n"
            f"<b>🏆 Win Rate:</b><code>{win_rate:.1f}%</code>\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<b>PERFORMANS</b>\n"
            f"<b>💰 Net PnL:</b>  <code>{sign}${net_pnl:.2f}</code>  {result_icon}\n"
            f"<b>📉 Max DD:</b>   <code>{max_dd:.2f}%</code>\n\n"
            f"<b>🥇 En İyi:</b>  <code>{best_str}</code>\n"
            f"<b>🥴 En Kötü:</b> <code>{worst_str}</code>\n\n"
            f"<code>{self._divider()}</code>\n"
            f"✅ <i>Şeffaflık: Tüm işlemler kaydedilmiştir</i>\n"
            f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
            f"<i>{self.TAGLINE}</i>"
        )
        return msg

    # ── SİSTEM UYARISI ────────────────────────────────────

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

    # ── LİKİDASYON UYARISI ───────────────────────────────

    def liquidation_spike(
        self, symbol: str, risk_level: str = "MEDIUM",
        liq_price: float = 0, current_price: float = 0,
        distance_pct: float = 0,
        total_liq_usd: float = 0, long_liq: float = 0,
        short_liq: float = 0, dominant: str = "",
    ) -> str:
        risk_emoji = {"LOW": "🟡", "MEDIUM": "🟠", "HIGH": "🔴", "CRITICAL": "🚨"}
        icon = risk_emoji.get(risk_level, "⚠️")
        recommendations = {
            "LOW": "✅ Normal izleme",
            "MEDIUM": "⚠️ Stop loss kontrol edin",
            "HIGH": "🛑 Pozisyon boyutunu düşürün",
            "CRITICAL": "⛔ ACİL ÇIKIŞ ÖNERİLİR",
        }
        msg = (
            f"{icon} <b>LİKİDASYON UYARISI — #{symbol}</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"<b>Risk:</b>  <code>{risk_level}</code>\n"
        )
        if liq_price > 0:
            msg += f"<b>Liq Fiyat:</b> <code>${liq_price:,.4f}</code>\n"
        if current_price > 0:
            msg += f"<b>Fiyat:</b>     <code>${current_price:,.4f}</code>\n"
        if distance_pct != 0:
            msg += f"<b>Mesafe:</b>    <code>{distance_pct:+.2f}%</code>\n"
        if total_liq_usd > 0:
            msg += (
                f"\n<b>💥 Toplam:</b>  <code>${total_liq_usd:,.0f}</code>\n"
                f"<b>🟢 Long:</b>   <code>${long_liq:,.0f}</code>\n"
                f"<b>🔴 Short:</b>  <code>${short_liq:,.0f}</code>\n"
            )
        msg += (
            f"\n<b>Tavsiye:</b> <i>{recommendations.get(risk_level, 'İzleme')}</i>\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg

    # ── TOP 3 COIN SİNYALİ ───────────────────────────────

    def top_coins_signal(self, coins: list = None, coin: str = "",
                          pattern: str = "", win_rate: float = 0,
                          signal_reason: str = "", confidence: float = 0) -> str:
        # Tekli coin çağrısı (telegram.py uyumluluğu)
        if coin and not coins:
            emoji = "✨" if confidence >= 0.8 else "🌟"
            msg = (
                f"{emoji} <b>EDGE SİNYALİ — #{coin}</b>\n"
                f"<code>{self._divider()}</code>\n\n"
                f"<b>Pattern:</b>   <code>{pattern}</code>\n"
                f"<b>Win Rate:</b>  <code>{win_rate:.1%}</code>\n"
                f"<b>Güven:</b>     <code>{confidence:.0%}</code>\n"
                f"\n<b>Sebep:</b> <i>{signal_reason}</i>\n\n"
                f"<code>{self._divider()}</code>\n"
                f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>\n"
                f"<i>🕐 {self._now()}</i>"
            )
            return msg
        # Çoklu coin listesi
        coins = coins or []
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

    # ── STARTUP ───────────────────────────────────────────

    def startup(self, version: str = "v1.0", mode: str = "PAPERTRADE",
                 balance: float = 0, symbols: int = 0, strategy: str = "") -> str:
        mode_icon = "📋" if mode in ("PAPERTRADE", "PAPER") else "🔴 LIVE"
        msg = (
            f"🟢 <b>WAR MACHINE BAŞLADI</b>\n"
            f"<code>{self._divider()}</code>\n\n"
            f"<b>🤖 {self.BRAND}</b>\n"
            f"<b>⚙️ Versiyon:</b>  <code>{version}</code>\n"
            f"<b>📊 Mod:</b>       {mode_icon}\n"
        )
        if balance > 0:
            msg += f"<b>💰 Bakiye:</b>    <code>${balance:,.2f}</code>\n"
        if symbols > 0:
            msg += f"<b>🪙 Coinler:</b>   <code>{symbols}</code>\n"
        if strategy:
            msg += f"<b>🎯 Strateji:</b>  <code>{strategy}</code>\n"
        msg += (
            f"\n<i>Sistem aktif. Piyasa taranıyor...</i>\n\n"
            f"<code>{self._divider()}</code>\n"
            f"<i>{self.TAGLINE}</i>\n"
            f"<i>🕐 {self._now()}</i>"
        )
        return msg


# Singleton
fmt = NechhFormatter()
