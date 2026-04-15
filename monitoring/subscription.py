"""
NECHH ROBOTICS — subscription.py
Supabase + NOWPayments ile kripto ödeme ve abonelik yönetimi.
Kurulum: pip install requests supabase
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

log = logging.getLogger("subscription")

# ── YAPILANDIRMA ──────────────────────────────────────────────────────────────

NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

NOW_API = "https://api.nowpayments.io/v1"
HEADERS = {"x-api-key": NOWPAYMENTS_API_KEY, "Content-Type": "application/json"}

# Lazy init — Supabase yoksa hata vermesin
_db = None


def _get_db():
    global _db
    if _db is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            log.error("SUPABASE_URL veya SUPABASE_KEY tanımlı değil")
            return None
        try:
            from supabase import create_client
            _db = create_client(SUPABASE_URL, SUPABASE_KEY)
        except ImportError:
            log.error("supabase kütüphanesi kurulu değil: pip install supabase")
            return None
    return _db


# ── PLANLAR ───────────────────────────────────────────────────────────────────

PLANS = {
    "pro": {
        "name": "PRO",
        "price_usd": 29,
        "days": 30,
        "channel_id": os.getenv("TELEGRAM_PRO_CHANNEL_ID", ""),
        "desc": "Tüm sinyaller + Günlük analiz",
    },
    "vip": {
        "name": "VIP",
        "price_usd": 59,
        "days": 30,
        "channel_id": os.getenv("TELEGRAM_VIP_CHANNEL_ID", ""),
        "desc": "PRO + Derin coin analizleri",
    },
}

# ── SUPABASE TABLO YAPISI (SQL — bir kez Supabase dashboard'dan çalıştır) ────
#
# create table users (
#   id bigserial primary key,
#   telegram_id bigint unique not null,
#   username text,
#   created_at timestamptz default now()
# );
#
# create table subscriptions (
#   id bigserial primary key,
#   telegram_id bigint references users(telegram_id),
#   plan text not null,
#   start_date timestamptz default now(),
#   end_date timestamptz not null,
#   status text default 'active',
#   channel_id text
# );
#
# create table payments (
#   id bigserial primary key,
#   telegram_id bigint,
#   plan text,
#   amount_usd numeric,
#   payment_id text unique,
#   pay_address text,
#   pay_currency text,
#   status text default 'waiting',
#   created_at timestamptz default now()
# );

# ── KULLANICI İŞLEMLERİ ───────────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, username: str = "") -> dict:
    db = _get_db()
    if not db:
        return {"telegram_id": telegram_id, "username": username}
    res = db.table("users").select("*").eq("telegram_id", telegram_id).execute()
    if res.data:
        return res.data[0]
    db.table("users").insert({"telegram_id": telegram_id, "username": username}).execute()
    return {"telegram_id": telegram_id, "username": username}


def get_active_subscription(telegram_id: int):
    db = _get_db()
    if not db:
        return None
    res = (
        db.table("subscriptions")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("status", "active")
        .gte("end_date", datetime.utcnow().isoformat())
        .order("end_date", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def create_subscription(telegram_id: int, plan: str) -> dict:
    db = _get_db()
    if not db:
        return {}
    p = PLANS[plan]
    end = datetime.utcnow() + timedelta(days=p["days"])
    data = {
        "telegram_id": telegram_id,
        "plan": plan,
        "end_date": end.isoformat(),
        "status": "active",
        "channel_id": p["channel_id"],
    }
    res = db.table("subscriptions").insert(data).execute()
    return res.data[0] if res.data else data


def expire_subscriptions():
    db = _get_db()
    if not db:
        return []
    now = datetime.utcnow().isoformat()
    res = (
        db.table("subscriptions")
        .select("*")
        .eq("status", "active")
        .lt("end_date", now)
        .execute()
    )
    expired = res.data or []
    for sub in expired:
        db.table("subscriptions").update({"status": "expired"}).eq("id", sub["id"]).execute()
        log.info(f"Süresi doldu: {sub['telegram_id']} — {sub['plan']}")
    return expired


def get_expiring_soon(days: int = 3) -> list:
    db = _get_db()
    if not db:
        return []
    now = datetime.utcnow()
    threshold = (now + timedelta(days=days)).isoformat()
    res = (
        db.table("subscriptions")
        .select("*")
        .eq("status", "active")
        .lte("end_date", threshold)
        .gte("end_date", now.isoformat())
        .execute()
    )
    return res.data or []


# ── NOWPAYMENTS ───────────────────────────────────────────────────────────────

def create_payment(telegram_id: int, plan: str, currency: str = "USDTBSC"):
    if not NOWPAYMENTS_API_KEY:
        log.error("NOWPAYMENTS_API_KEY tanımlı değil")
        return None
    db = _get_db()
    p = PLANS[plan]
    try:
        r = requests.post(
            f"{NOW_API}/payment",
            headers=HEADERS,
            json={
                "price_amount": p["price_usd"],
                "price_currency": "usd",
                "pay_currency": currency.lower(),
                "order_id": f"{telegram_id}_{plan}_{int(datetime.utcnow().timestamp())}",
                "order_description": f"Nechh Robotics {p['name']} — 30 gün",
            },
            timeout=10,
        )
        data = r.json()
        if "payment_id" not in data:
            log.error(f"NOWPayments hata: {data}")
            return None

        if db:
            db.table("payments").insert({
                "telegram_id": telegram_id,
                "plan": plan,
                "amount_usd": p["price_usd"],
                "payment_id": str(data["payment_id"]),
                "pay_address": data["pay_address"],
                "pay_currency": currency,
                "status": "waiting",
            }).execute()

        return {
            "payment_id": data["payment_id"],
            "pay_address": data["pay_address"],
            "pay_amount": data["pay_amount"],
            "currency": currency,
        }
    except Exception as e:
        log.error(f"create_payment hata: {e}")
        return None


def check_payment_status(payment_id: str) -> str:
    if not NOWPAYMENTS_API_KEY:
        return "unknown"
    try:
        r = requests.get(f"{NOW_API}/payment/{payment_id}", headers=HEADERS, timeout=10)
        return r.json().get("payment_status", "unknown")
    except Exception as e:
        log.error(f"check_payment hata: {e}")
        return "unknown"


def handle_webhook(data: dict) -> bool:
    """NOWPayments IPN webhook handler."""
    payment_id = str(data.get("payment_id", ""))
    status = data.get("payment_status", "")

    if status not in ("confirmed", "finished"):
        return False

    db = _get_db()
    if not db:
        return False

    res = db.table("payments").select("*").eq("payment_id", payment_id).execute()
    if not res.data:
        log.warning(f"Webhook: payment_id bulunamadı: {payment_id}")
        return False

    pay = res.data[0]
    db.table("payments").update({"status": "confirmed"}).eq("payment_id", payment_id).execute()
    create_subscription(pay["telegram_id"], pay["plan"])
    log.info(f"Abonelik oluşturuldu: {pay['telegram_id']} — {pay['plan']}")
    return True


def format_plan_message() -> str:
    msg = "💎 <b>NECHH ROBOTICS — ABONELİK PLANLARI</b>\n"
    msg += f"<code>{'─' * 32}</code>\n\n"
    for key, p in PLANS.items():
        msg += (
            f"<b>{p['name']}</b> — <code>${p['price_usd']}/ay</code>\n"
            f"<i>{p['desc']}</i>\n\n"
        )
    msg += (
        f"<code>{'─' * 32}</code>\n"
        f"Ödeme için coin seçin.\n"
        f"<i>USDT (BEP20/TRC20), BTC, ETH kabul edilir.</i>\n\n"
        f"<i>⚠️ Bu bir yatırım tavsiyesi değildir.</i>"
    )
    return msg
