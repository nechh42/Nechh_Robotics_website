// /api/nechh-data.js
// Vercel API endpoint — trades.json'dan gerçek verileri sunar.
// nechh_integration.js ve diğer frontend bileşenleri tarafından kullanılır.

import { readFileSync } from 'fs';
import { join } from 'path';

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=120');

    try {
        const tradesPath = join(process.cwd(), 'trades.json');
        const raw = readFileSync(tradesPath, 'utf-8');
        const data = JSON.parse(raw);

        const s = data.summary || {};
        const mode = data.meta?.mode || 'PAPERTRADE';

        // nechh_integration.js'in beklediği format
        const response = {
            timestamp: data.meta?.last_updated || new Date().toISOString(),
            status: "active",
            mode: mode,
            system_uptime_hours: 0,
            symbols_count: 12,
            website_data: {
                system_status: {
                    status: "OPERATIONAL",
                    last_update: data.meta?.last_updated || new Date().toISOString(),
                    active_symbols: 12,
                    uptime: "—",
                    mode: mode
                },
                quick_cards: [
                    { symbol: "TOTAL", signal: "🟢", change: String(s.total_trades || 0), label: "Total Setups" },
                    { symbol: "WR", signal: s.win_rate >= 50 ? "🟢" : "🔴", change: (s.win_rate || 0) + "%", label: "Win Rate" },
                    { symbol: "RR", signal: "🟢", change: String(s.avg_rr || 0), label: "Avg RR" },
                    { symbol: "DD", signal: (s.max_drawdown || 0) < 3 ? "🟢" : "🔴", change: (s.max_drawdown || 0) + "%", label: "Max DD" }
                ]
            },
            summary: s,
            trades: data.trades || []
        };

        res.status(200).json(response);
    } catch (e) {
        // trades.json okunamazsa boş veri dön
        res.status(200).json({
            timestamp: new Date().toISOString(),
            status: "active",
            mode: "PAPERTRADE",
            website_data: {
                system_status: { status: "OPERATIONAL", last_update: new Date().toISOString(), active_symbols: 0, uptime: "—", mode: "PAPERTRADE" },
                quick_cards: []
            },
            summary: { total_trades: 0, wins: 0, losses: 0, win_rate: 0, avg_rr: 0, total_pnl: 0, max_drawdown: 0, balance_start: 10000, balance_current: 10000 },
            trades: []
        });
    }
}
