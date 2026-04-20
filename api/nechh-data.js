// /api/nechh-data.js
// trades.json (bot kapatıldığında güncellenir) + website_data.json (15 dk'da bir güncellenir)
// İki kaynağı birleştirip sunar.

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

function readJSON(path) {
    if (!existsSync(path)) return null;
    try { return JSON.parse(readFileSync(path, 'utf-8')); } catch { return null; }
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    res.setHeader('Cache-Control', 'no-store, max-age=0');

    const trades   = readJSON(join(process.cwd(), 'trades.json'));
    const liveData = readJSON(join(process.cwd(), 'data', 'website_data.json'));

    const s    = trades?.summary   || {};
    const mode = trades?.meta?.mode || liveData?.website_data?.system_status?.mode || 'PAPERTRADE';
    const live = liveData?.website_data || {};

    // quick_cards: canlı fiyat verisi varsa ondan, yoksa trades istatistiklerinden
    const quick_cards = live.quick_cards?.length > 0
        ? live.quick_cards
        : [
            { symbol: "SETUPS", signal: "🟢", change: String(s.total_trades || 0), label: "Total Setups" },
            { symbol: "WIN%",   signal: (s.win_rate||0) >= 50 ? "🟢" : "🔴", change: (s.win_rate||0) + "%", label: "Win Rate" },
            { symbol: "RR",     signal: "🟢", change: String(s.avg_rr || 0), label: "Avg RR" },
            { symbol: "DD",     signal: (s.max_drawdown||0) < 5 ? "🟢" : "🔴", change: (s.max_drawdown||0) + "%", label: "Max DD" },
          ];

    const response = {
        timestamp: trades?.meta?.last_updated || new Date().toISOString(),
        status: "active",
        mode: mode,
        // Gerçek bot metrikleri (canlı veri yoksa trades istatistikleri)
        system_uptime_hours: live?.system_status?.uptime || "—",
        symbols_count: live?.system_status?.active_symbols || 3,
        website_data: {
            system_status: {
                status: "OPERATIONAL",
                last_update: live?.system_status?.last_update || trades?.meta?.last_updated || new Date().toISOString(),
                active_symbols: live?.system_status?.active_symbols || 3,
                uptime: live?.system_status?.uptime || "—",
                mode: mode,
            },
            quick_cards,
            performance: live?.performance || {
                total_trades: s.total_trades || 0,
                wins:         s.wins || 0,
                losses:       s.losses || 0,
                win_rate:     s.win_rate || 0,
                total_pnl:    s.total_pnl || 0,
                balance:      s.balance_current || 10000,
                max_dd_pct:   s.max_drawdown || 0,
            },
            open_positions: live?.open_positions || [],
            recent_trades:  live?.recent_trades  || [],
        },
        // Performance sayfası için tam trades verisi
        summary: s,
        trades: trades?.trades || [],
    };

    res.status(200).json(response);
}
