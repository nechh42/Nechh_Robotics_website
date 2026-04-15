"""
NECHH ROBOTICS — bot_manager.py
Kurulum: pip install python-telegram-bot==20.7
Çalıştır: python bot_manager.py
Mevcut botuna DOKUNMAZ — tamamen ayrı process.
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from subscription import (
    get_or_create_user, get_active_subscription,
    create_payment, check_payment_status,
    expire_subscriptions, get_expiring_soon,
    format_plan_message, PLANS
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot_manager")

BOT_TOKEN    = "BURAYA_BOT_TOKEN"      # @BotFather'dan al
ADMIN_IDS    = [123456789]             # Senin Telegram ID'n

# ── KOMUTLAR ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or "")

    msg = (
        f"👋 Merhaba <b>{user.first_name}</b>!\n\n"
        f"🤖 <b>NECHH ROBOTICS</b>'e hoş geldin.\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>\n\n"
        f"Algoritmik kripto trading sistemi — 7/24 çalışıyor.\n\n"
        f"<b>Komutlar:</b>\n"
        f"/abone — Abonelik planları\n"
        f"/durum — Abonelik durumun\n"
        f"/hakkinda — Sistem hakkında\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_abone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("PRO — $29/ay", callback_data="plan_pro"),
            InlineKeyboardButton("VIP — $59/ay", callback_data="plan_vip"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        format_plan_message(),
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def cmd_durum(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sub = get_active_subscription(user.id)

    if sub:
        end = sub["end_date"][:10]
        msg = (
            f"✅ <b>Aktif Abonelik</b>\n\n"
            f"<b>Plan:</b> <code>{sub['plan'].upper()}</code>\n"
            f"<b>Bitiş:</b> <code>{end}</code>\n\n"
            f"Yenilemek için /abone yazabilirsin."
        )
    else:
        msg = (
            f"❌ <b>Aktif abonelik yok.</b>\n\n"
            f"Abone olmak için /abone yaz."
        )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_hakkinda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"🤖 <b>NECHH ROBOTICS</b>\n\n"
        f"Algoritmik kripto trading sistemi.\n"
        f"• Spot & Futures işlemleri\n"
        f"• 7/24 otomatik çalışır\n"
        f"• Strateji odaklı, şansa dayanmaz\n"
        f"• Tüm işlemler şeffaf paylaşılır\n\n"
        f"<i>⚠️ Paylaşılan sinyaller yatırım tavsiyesi değildir.\n"
        f"Kripto yatırımları risk içerir.</i>\n\n"
        f"<i>SİSTEM KONUŞUR • ŞANS DEĞİL</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ── CALLBACK: PLAN SEÇİMİ ─────────────────────────────────────────────────────

async def callback_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = query.data.replace("plan_", "")   # "pro" veya "vip"

    keyboard = [
        [
            InlineKeyboardButton("USDT (BEP20)", callback_data=f"pay_{plan}_USDTBSC"),
            InlineKeyboardButton("USDT (TRC20)", callback_data=f"pay_{plan}_USDTTRC20"),
        ],
        [
            InlineKeyboardButton("BTC",           callback_data=f"pay_{plan}_BTC"),
            InlineKeyboardButton("ETH",           callback_data=f"pay_{plan}_ETH"),
        ],
    ]
    p = PLANS[plan]
    await query.edit_message_text(
        f"💳 <b>{p['name']} Plan — ${p['price_usd']}/ay</b>\n\n"
        f"Ödeme yöntemi seç:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def callback_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, plan, currency = query.data.split("_", 2)   # pay_pro_USDTBSC

    user = update.effective_user
    await query.edit_message_text("⏳ Ödeme adresi oluşturuluyor...", parse_mode="HTML")

    payment = create_payment(user.id, plan, currency)

    if not payment:
        await query.edit_message_text(
            "❌ Ödeme oluşturulamadı. Lütfen tekrar dene veya admin ile iletişime geç.",
            parse_mode="HTML",
        )
        return

    p = PLANS[plan]
    msg = (
        f"💳 <b>{p['name']} Plan — Ödeme Detayları</b>\n"
        f"<code>{'─'*32}</code>\n\n"
        f"<b>Tutar:</b>   <code>{payment['pay_amount']} {currency}</code>\n"
        f"<b>Adres:</b>\n<code>{payment['pay_address']}</code>\n\n"
        f"<code>{'─'*32}</code>\n"
        f"⚠️ Sadece <b>{currency}</b> gönder!\n"
        f"Ödeme onaylandıktan sonra otomatik erişim verilir.\n\n"
        f"Ödeme ID: <code>{payment['payment_id']}</code>\n"
        f"<i>Sorun için: /destek</i>"
    )
    # Ödeme takibini başlat
    ctx.job_queue.run_repeating(
        check_payment_job,
        interval=120,   # 2 dakikada bir kontrol
        first=60,
        data={"payment_id": str(payment["payment_id"]), "telegram_id": user.id, "plan": plan},
        name=str(payment["payment_id"]),
    )
    await query.edit_message_text(msg, parse_mode="HTML")


# ── ÖDEME TAKİP JOB ───────────────────────────────────────────────────────────

async def check_payment_job(ctx: ContextTypes.DEFAULT_TYPE):
    job    = ctx.job
    data   = job.data
    status = check_payment_status(data["payment_id"])

    if status in ("confirmed", "finished"):
        from subscription import create_subscription, PLANS
        sub = create_subscription(data["telegram_id"], data["plan"])
        p   = PLANS[data["plan"]]

        # Kanal davet linki gönder
        try:
            link = await ctx.bot.create_chat_invite_link(
                chat_id=p["channel_id"],
                member_limit=1,
                expire_date=None,
            )
            msg = (
                f"✅ <b>Ödeme Onaylandı!</b>\n\n"
                f"<b>Plan:</b> <code>{p['name']}</code>\n"
                f"<b>Bitiş:</b> <code>{sub['end_date'][:10]}</code>\n\n"
                f"👇 Kanala katıl:\n{link.invite_link}\n\n"
                f"<i>Link tek kullanımlıktır. Kimseyle paylaşma.</i>"
            )
            await ctx.bot.send_message(data["telegram_id"], msg, parse_mode="HTML")
        except Exception as e:
            log.error(f"Davet linki hatası: {e}")
        job.schedule_removal()

    elif status in ("failed", "expired"):
        await ctx.bot.send_message(
            data["telegram_id"],
            "❌ Ödeme başarısız veya süresi doldu. Tekrar denemek için /abone yaz.",
            parse_mode="HTML",
        )
        job.schedule_removal()


# ── GÜNLÜK BAKIM: KİCK + HATIRLATMA ─────────────────────────────────────────

async def daily_maintenance(ctx: ContextTypes.DEFAULT_TYPE):
    """Her gün çalışır — scheduler job olarak ekle"""
    # Süresi dolanları kick et
    expired = expire_subscriptions()
    for sub in expired:
        try:
            await ctx.bot.ban_chat_member(sub["channel_id"], sub["telegram_id"])
            await ctx.bot.unban_chat_member(sub["channel_id"], sub["telegram_id"])
            await ctx.bot.send_message(
                sub["telegram_id"],
                f"⏰ <b>Aboneliğin sona erdi.</b>\n\nYenilemek için /abone yaz.",
                parse_mode="HTML",
            )
        except Exception as e:
            log.error(f"Kick hatası {sub['telegram_id']}: {e}")

    # 3 gün içinde dolacaklara hatırlatma
    soon = get_expiring_soon(days=3)
    for sub in soon:
        try:
            await ctx.bot.send_message(
                sub["telegram_id"],
                f"⚠️ <b>Aboneliğin {sub['end_date'][:10]} tarihinde sona eriyor.</b>\n\n"
                f"Yenilemek için /abone yaz.",
                parse_mode="HTML",
            )
        except Exception as e:
            log.error(f"Hatırlatma hatası {sub['telegram_id']}: {e}")


# ── ADMIN KOMUTLARI ───────────────────────────────────────────────────────────

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    from supabase import create_client
    import os
    # Basit istatistik
    msg = (
        f"🔧 <b>ADMIN PANEL</b>\n\n"
        f"/admin_users — Aktif aboneler\n"
        f"/admin_payments — Son ödemeler\n"
        f"/admin_broadcast — Tüm abonelere mesaj\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ── UYGULAMA BAŞLAT ───────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("abone",     cmd_abone))
    app.add_handler(CommandHandler("durum",     cmd_durum))
    app.add_handler(CommandHandler("hakkinda",  cmd_hakkinda))
    app.add_handler(CommandHandler("admin",     cmd_admin))

    # Callback
    app.add_handler(CallbackQueryHandler(callback_plan, pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(callback_pay,  pattern="^pay_"))

    # Günlük bakım: her gün 00:05 UTC
    app.job_queue.run_daily(daily_maintenance, time=__import__("datetime").time(0, 5))

    log.info("Bot başladı...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
