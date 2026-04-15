"""
NECHH ROBOTICS — webhook_server.py
NOWPayments IPN webhook alıcısı.
Kurulum: pip install fastapi uvicorn
Çalıştır: uvicorn webhook_server:app --host 0.0.0.0 --port 8000
Railway/Render'a deploy et → URL'yi NOWPayments IPN alanına gir.
"""

from fastapi import FastAPI, Request, HTTPException
from subscription import handle_webhook
import logging

log = logging.getLogger("webhook")
app = FastAPI()


@app.get("/")
def root():
    return {"status": "Nechh Robotics webhook aktif"}


@app.post("/webhook/nowpayments")
async def nowpayments_ipn(request: Request):
    """NOWPayments IPN endpoint — ödeme onayı buraya gelir"""
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
