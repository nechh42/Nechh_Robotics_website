"""
NECHH ROBOTICS — webhook_server.py
NOWPayments IPN webhook alıcısı.
Çalıştır: uvicorn monitoring.webhook_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from monitoring.subscription import handle_webhook

log = logging.getLogger("webhook")
app = FastAPI(title="Nechh Robotics Webhook")


@app.get("/")
def root():
    return {"status": "Nechh Robotics webhook aktif"}


@app.post("/webhook/nowpayments")
async def nowpayments_ipn(request: Request):
    """NOWPayments IPN endpoint — ödeme onayı buraya gelir."""
    try:
        data = await request.json()
        log.info(f"Webhook geldi: {data.get('payment_id')} — {data.get('payment_status')}")
        success = handle_webhook(data)
        return {"ok": success}
    except Exception as e:
        log.error(f"Webhook hata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
