"""
NECHH ROBOTICS — trades_updater.py
Mevcut botun her trade kapandığında bu dosyayı çağırır.
trades.json'u günceller → performance.html otomatik yenilenir.

Kullanım (mevcut botundan):
    from trades_updater import log_trade, update_summary
"""

import json
import os
from datetime import datetime, timezone

TRADES_FILE = "trades.json"


def _load() -> dict:
    if not os.path.exists(TRADES_FILE):
        return {"meta": {}, "summary": {}, "trades": []}
    with open(TRADES_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    data["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_trade(
    symbol: str,
    market: str,        # "FUTURES" / "SPOT"
    side: str,          # "LONG" / "SHORT"
    structure: str,     # "Liquidity Sweep" vs.
    session: str,       # "NY" / "London" / "Asia"
    entry: float,
    exit_price: float,
    invalidation: float,
    target: float,
    leverage: int,
    size: float,
    rr: float,
    outcome: str,       # "Target Reached" / "Invalidated"
    pnl: float,
    pnl_pct: float,
    duration_minutes: int,
    opened_at: str,     # ISO format
):
    """Yeni trade'i trades.json'a ekle ve summary'yi güncelle"""
    data = _load()
    trades = data.get("trades", [])

    # Yeni ID
    trade_id = f"T{len(trades)+1:03d}"

    trade = {
        "id": trade_id,
        "symbol": symbol,
        "market": market,
        "side": side,
        "structure": structure,
        "session": session,
        "entry": entry,
        "exit": exit_price,
        "invalidation": invalidation,
        "target": target,
        "leverage": leverage,
        "size": size,
        "rr": rr,
        "outcome": outcome,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "duration_minutes": duration_minutes,
        "opened_at": opened_at,
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }
    trades.append(trade)
    data["trades"] = trades
    data["summary"] = _recalc_summary(trades, data.get("summary", {}))
    _save(data)
    return trade_id


def _recalc_summary(trades: list, existing: dict) -> dict:
    if not trades:
        return existing

    wins   = [t for t in trades if t["outcome"] == "Target Reached"]
    losses = [t for t in trades if t["outcome"] == "Invalidated"]
    total  = len(trades)
    pnls   = [t["pnl"] for t in trades]
    rrs    = [t["rr"] for t in trades if t["rr"] > 0]

    # Max drawdown hesabı
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / (existing.get("balance_start", 10000) + peak) * 100
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / total * 100, 1) if total else 0,
        "avg_rr": round(sum(rrs) / len(rrs), 2) if rrs else 0,
        "total_pnl": round(sum(pnls), 2),
        "max_drawdown": round(max_dd, 2),
        "balance_start": existing.get("balance_start", 10000.00),
        "balance_current": round(
            existing.get("balance_start", 10000.00) + sum(pnls), 2
        ),
    }


def update_mode(mode: str):
    """PAPERTRADE → LIVE geçişinde çağır"""
    data = _load()
    data["meta"]["mode"] = mode
    _save(data)


# ── MEVCUT BOTUNA ENTEGRASYON ─────────────────────────────────────────────────
# Botunun trade kapanış kısmına şunu ekle:
#
# from trades_updater import log_trade
#
# log_trade(
#     symbol      = symbol,
#     market      = "FUTURES",
#     side        = side,
#     structure   = "Liquidity Sweep",   # botundan gelen yapı adı
#     session     = session,
#     entry       = entry_price,
#     exit_price  = close_price,
#     invalidation= sl_price,
#     target      = tp_price,
#     leverage    = leverage,
#     size        = position_size,
#     rr          = realized_rr,
#     outcome     = "Target Reached" if profit else "Invalidated",
#     pnl         = realized_pnl,
#     pnl_pct     = pnl_percentage,
#     duration_minutes = duration,
#     opened_at   = open_time.isoformat(),
# )


if __name__ == "__main__":
    # Test
    tid = log_trade(
        "BTCUSDT","FUTURES","LONG","Liquidity Sweep","NY",
        83420.5, 85100.0, 82000.0, 85000.0, 3, 0.012,
        1.8, "Target Reached", 20.16, 2.01, 262,
        "2026-04-15T09:14:00Z"
    )
    print(f"Kaydedildi: {tid}")
    data = _load()
    print(f"Summary: {data['summary']}")
