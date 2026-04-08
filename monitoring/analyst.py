"""
analyst.py - Otonom Analiz Ajanı
===================================
Periyodik olarak signal_log verisini analiz eder ve
Telegram'dan içgörü raporları gönderir.

Swarm mimarisinin İLK ajanıdır:
  - Bağımsız çalışır (orchestrator'dan trade kararı almaz)
  - Sadece GÖZLEM + RAPOR yapar
  - Her 6 saatte bir Telegram'a içgörü gönderir
  - Anomali tespit ederse HEMEN uyarı verir

Raporlar:
  1. Sinyal İstatistikleri: Kaç sinyal üretildi, kaçı trade oldu, kaçı engellendi
  2. Strateji Performansı: Her stratejinin isabet oranı ve kârlılığı
  3. Regime Analizi: Hangi rejimde para kazanıyoruz/kaybediyoruz
  4. Engelleme Analizi: En çok ne engel oluyor
  5. Öneriler: "VOLATILE'da trade açma, RSI ağırlığını düşür" gibi
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict

import config
from persistence.signal_logger import SignalLogger
from persistence.database import Database
from monitoring.telegram import telegram

logger = logging.getLogger(__name__)

ANALYST_INTERVAL_HOURS = 6


class Analyst:
    """Otonom analiz ajanı — veri toplar, analiz eder, rapor verir"""

    def __init__(self, signal_logger: SignalLogger, db: Database):
        self.sl = signal_logger
        self.db = db

    def generate_report(self) -> str:
        """Tüm verileri analiz et, Telegram raporu üret"""
        lines = ["🤖 *ANALYST RAPORU*\n"]

        # 1. Sinyal istatistikleri (son 6 saat)
        stats = self.sl.get_stats(hours=6)
        total = stats.get("total", 0)
        decisions = stats.get("decisions", {})

        lines.append("📊 *Son 6 Saat — Sinyal Özeti*")
        lines.append(f"  Toplam değerlendirme: {total}")

        if total > 0:
            traded = decisions.get("TRADE_OPENED", 0)
            no_signal = decisions.get("NO_SIGNAL", 0)
            blocked_risk = decisions.get("BLOCKED_RISK", 0)
            blocked_volume = decisions.get("BLOCKED_LOW_VOLUME", 0)
            blocked_bl = decisions.get("BLOCKED_BLACKLIST", 0)
            blocked_trend = decisions.get("BLOCKED_TREND_UP", 0)
            blocked_corr = decisions.get("BLOCKED_CORRELATION", 0)
            mtf_pending = decisions.get("MTF_PENDING", 0)

            lines.append(f"  ✅ Trade açılan: {traded}")
            lines.append(f"  ⏳ MTF bekleyen: {mtf_pending}")
            lines.append(f"  ❌ Sinyal yok: {no_signal}")

            blocked_total = blocked_risk + blocked_volume + blocked_bl + blocked_trend + blocked_corr
            if blocked_total > 0:
                lines.append(f"  🚫 Engellenen: {blocked_total}")
                if blocked_risk > 0:
                    lines.append(f"    → Risk: {blocked_risk}")
                if blocked_volume > 0:
                    lines.append(f"    → Düşük hacim: {blocked_volume}")
                if blocked_bl > 0:
                    lines.append(f"    → Blacklist: {blocked_bl}")
                if blocked_trend > 0:
                    lines.append(f"    → Trend Up: {blocked_trend}")
                if blocked_corr > 0:
                    lines.append(f"    → Korelasyon: {blocked_corr}")

            # Conversion rate
            if total > 0:
                conv_rate = traded / total * 100
                lines.append(f"  📈 Dönüşüm oranı: %{conv_rate:.1f}")

        lines.append("")

        # 2. Strateji performansı (tüm zamanlar)
        accuracy = self.sl.get_strategy_accuracy(hours=168)
        if accuracy:
            lines.append("🎯 *Strateji Başarı Oranları (7 gün)*")
            for strat, data in sorted(accuracy.items(), key=lambda x: x[1].get("win_rate", 0), reverse=True):
                emoji = "🟢" if data["win_rate"] >= 50 else "🔴"
                lines.append(
                    f"  {emoji} {strat}: %{data['win_rate']:.0f} WR "
                    f"({data['wins']}/{data['signals']} trade, "
                    f"avg conf={data['avg_confidence']:.2f})"
                )
            lines.append("")

        # 3. Regime analizi
        regime_perf = self.sl.get_regime_performance(hours=168)
        if regime_perf:
            lines.append("🌍 *Regime Performansı (7 gün)*")
            for regime, data in regime_perf.items():
                emoji = "🟢" if data["total_pnl"] >= 0 else "🔴"
                lines.append(
                    f"  {emoji} {regime}: %{data['win_rate']:.0f} WR, "
                    f"${data['total_pnl']:.2f} PnL "
                    f"({data['closed']} trade)"
                )
            lines.append("")

        # 4. Öneriler
        recommendations = self._generate_recommendations(accuracy, regime_perf, decisions if total > 0 else {})
        if recommendations:
            lines.append("💡 *Öneriler*")
            for rec in recommendations:
                lines.append(f"  → {rec}")
            lines.append("")

        # 5. Adaptive weights durumu
        lines.append("⚖️ *Öğrenilmiş Ağırlıklar*")
        try:
            # DB'den mevcut ağırlıkları oku
            from engine.adaptive_weights import AdaptiveWeights
            aw = AdaptiveWeights(db=self.db)
            aw_stats = aw.get_stats()
            if aw_stats["total_trades"] > 0:
                for regime, rdata in aw_stats["regimes"].items():
                    weights_str = " ".join(f"{k}={v:.0%}" for k, v in rdata["weights"].items())
                    lines.append(f"  {regime}: {weights_str} ({rdata['trades']} trade)")
            else:
                lines.append("  Henüz yeterli veri yok (min 10 trade/regime)")
        except Exception:
            lines.append("  Veri okunamadı")

        return "\n".join(lines)

    def _generate_recommendations(self, accuracy: Dict, regime_perf: Dict, decisions: Dict) -> list:
        """Veriden otomatik öneri üret"""
        recs = []

        # Kötü strateji uyarısı
        for strat, data in accuracy.items():
            if data["signals"] >= 5 and data["win_rate"] < 35:
                recs.append(f"⚠️ {strat} stratejisi çok kötü (%{data['win_rate']:.0f} WR) — ağırlık düşürülmeli")
            elif data["signals"] >= 5 and data["win_rate"] >= 65:
                recs.append(f"✅ {strat} stratejisi çok iyi (%{data['win_rate']:.0f} WR) — ağırlık artırılabilir")

        # Kötü regime uyarısı
        for regime, data in regime_perf.items():
            if data["closed"] >= 3 and data["win_rate"] < 30:
                recs.append(f"🔴 {regime} rejiminde sürekli kayıp (%{data['win_rate']:.0f}) — bu rejimi engelle!")
            elif data["closed"] >= 3 and data["total_pnl"] < -10:
                recs.append(f"🔴 {regime} rejiminde ${abs(data['total_pnl']):.2f} kayıp — dikkat!")

        # Çok fazla engelleme
        blocked_risk = decisions.get("BLOCKED_RISK", 0)
        total_signals = sum(decisions.values()) if decisions else 0
        if total_signals > 10 and blocked_risk > total_signals * 0.5:
            recs.append("⚠️ Sinyallerin %50+'ı risk tarafından engelleniyor — parametreleri gözden geçir")

        # Conversion çok düşük
        traded = decisions.get("TRADE_OPENED", 0)
        if total_signals > 20 and traded == 0:
            recs.append("🔴 20+ değerlendirme ama 0 trade — filtreler çok agresif")

        if not recs:
            recs.append("Yeterli veri biriktikçe öneriler burada görünecek")

        return recs

    def check_anomalies(self) -> str:
        """Anlık anomali kontrolü — sorun varsa HEMEN Telegram'a gönder"""
        alerts = []

        # Son 1 saatte hiç değerlendirme yapılmamışsa → engine sorunlu olabilir
        stats = self.sl.get_stats(hours=1)
        if stats["total"] == 0:
            # İlk 1 saat tolerans (henüz candle close olmamış olabilir)
            stats_24h = self.sl.get_stats(hours=24)
            if stats_24h["total"] > 0:
                alerts.append("⚠️ Son 1 saatte hiç sinyal değerlendirmesi yok — engine kontrol et!")

        # Art arda kayıp kontrolü
        try:
            from persistence.database import Database
            trades = self.db.get_trades(limit=5)
            if len(trades) >= 5:
                all_loss = all(t["net_pnl"] <= 0 for t in trades)
                if all_loss:
                    total_loss = sum(t["net_pnl"] for t in trades)
                    alerts.append(f"🔴 Art arda 5 KAYIP! Toplam: ${total_loss:.2f} — sistem gözden geçirilmeli")
        except Exception:
            pass

        if alerts:
            return "🚨 *ANOMALİ TESPİT*\n" + "\n".join(alerts)
        return ""


async def analyst_loop(orchestrator):
    """Ana analiz döngüsü — 6 saatte bir rapor gönder, her saat anomali kontrol"""
    analyst = Analyst(orchestrator.signal_logger, orchestrator.db)
    cycle = 0

    while True:
        try:
            await asyncio.sleep(3600)  # Her saat çalış
            cycle += 1

            # Her saat: anomali kontrolü
            anomaly = analyst.check_anomalies()
            if anomaly:
                await telegram.send(anomaly)
                logger.warning(f"[ANALYST] Anomali tespit edildi ve bildirildi")

            # Her 6 saatte: detaylı rapor
            if cycle % ANALYST_INTERVAL_HOURS == 0:
                report = analyst.generate_report()
                await telegram.send(report)
                logger.info(f"[ANALYST] 6 saatlik rapor gönderildi")

        except Exception as e:
            logger.error(f"[ANALYST] Loop error: {e}")
            await asyncio.sleep(60)
