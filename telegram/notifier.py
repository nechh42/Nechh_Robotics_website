import time
from telegram import Bot
from templates import position_opened_message, hourly_summary, safety_warning, scam_warning

BOT_TOKEN = "TELEGRAM_BOT_TOKENIN"
CHAT_ID = "CHAT_ID"

bot = Bot(token=BOT_TOKEN)

LAST_SUMMARY_TIME = 0
SUMMARY_INTERVAL = 60 * 60  # 1 saat
MAX_COINS = 5


def send_message(text):
    bot.send_message(chat_id=CHAT_ID, text=text)


def send_position_opened(data):
    msg = position_opened_message(data)
    send_message(msg)


def send_hourly_summary(coins):
    global LAST_SUMMARY_TIME
    now = time.time()
    if now - LAST_SUMMARY_TIME >= SUMMARY_INTERVAL:
        send_message(hourly_summary(coins))
        send_message(safety_warning())
        send_scam_warning()
        LAST_SUMMARY_TIME = now


# Saat başı scam uyarısı gönderme fonksiyonu
def send_scam_warning():
    send_message(scam_warning())
