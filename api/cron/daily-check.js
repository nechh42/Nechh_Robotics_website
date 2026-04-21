// api/cron/daily-check.js
// Vercel Cron Job — her gün 09:00 UTC çalışır.
// Görevler:
//   1. Aboneliği biten kullanıcıları deaktive et + Telegram'dan çıkar
//   2. 5 gün / 1 gün kalan kullanıcılara email gönder
//   3. Ödeme bekleyenlere 3. günde hatırlatma yap
//   4. Admin'e günlük özet Telegram mesajı gönder

const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_KEY  // service key (admin yetkisi)
);

const BOT_TOKEN   = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_CHAT  = process.env.TELEGRAM_ADMIN_CHAT_ID;
const GROUP_ID    = process.env.TELEGRAM_GROUP_ID;
const RESEND_KEY  = process.env.RESEND_API_KEY;

// ── Yardımcı Fonksiyonlar ─────────────────────────────────────────────────────

async function sendTelegram(chatId, text) {
    const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' }),
    });
    return r.json();
}

async function kickFromGroup(telegramId) {
    if (!GROUP_ID || !telegramId) return;
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/banChatMember`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: GROUP_ID, user_id: telegramId, revoke_messages: false }),
    });
    // Hemen unban et (sadece atma, kalıcı ban değil)
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/unbanChatMember`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: GROUP_ID, user_id: telegramId, only_if_banned: true }),
    });
}

async function sendEmail(to, templateType, templateData = {}) {
    if (!RESEND_KEY || !to) return;

    const templates = {
        reminder_5d: {
            subject: '⏰ Your Nechh Robotics subscription expires in 5 days',
            html: `<h2>Subscription Reminder</h2>
                   <p>Your subscription expires on <strong>${templateData.expires}</strong>.</p>
                   <p>Renew now to keep your access: <a href="https://nechh-robotics-website.vercel.app/pricing.html">Renew →</a></p>`,
        },
        reminder_1d: {
            subject: '🚨 Last day! Your subscription expires tomorrow',
            html: `<h2>Final Reminder</h2>
                   <p>Your subscription expires <strong>tomorrow (${templateData.expires})</strong>.</p>
                   <p><a href="https://nechh-robotics-website.vercel.app/pricing.html">Renew now →</a></p>`,
        },
        expired: {
            subject: '❌ Your Nechh Robotics subscription has ended',
            html: `<h2>Subscription Expired</h2>
                   <p>Your access has been deactivated. You have been removed from the Telegram group.</p>
                   <p>Resubscribe anytime: <a href="https://nechh-robotics-website.vercel.app/pricing.html">Rejoin →</a></p>`,
        },
        payment_reminder: {
            subject: '💳 Payment pending — complete your Nechh Robotics registration',
            html: `<h2>Complete Your Registration</h2>
                   <p>Your account was created but payment has not been received yet.</p>
                   <p><a href="https://nechh-robotics-website.vercel.app/pricing.html">Complete payment →</a></p>`,
        },
    };

    const tpl = templates[templateType];
    if (!tpl) return;

    await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${RESEND_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
            from: 'Nechh Robotics <noreply@nechh-robotics.com>',
            to: [to],
            subject: tpl.subject,
            html: tpl.html,
        }),
    });
}

// ── Ana Kontrol Fonksiyonları ─────────────────────────────────────────────────

async function checkExpiredSubscriptions() {
    const now = new Date().toISOString();

    // Aboneliği biten aktif kullanıcılar
    const { data: expired } = await supabase
        .from('subscribers')
        .select('id, email, telegram_username, telegram_user_id, subscription_end')
        .eq('subscription_status', 'active')
        .lt('subscription_end', now);

    if (!expired?.length) return 0;

    for (const user of expired) {
        // 1. DB'yi güncelle
        await supabase.from('subscribers')
            .update({ subscription_status: 'expired', updated_at: now })
            .eq('id', user.id);

        // 2. Telegram grubundan çıkar
        if (user.telegram_user_id) {
            await kickFromGroup(user.telegram_user_id);
        }

        // 3. Email gönder
        await sendEmail(user.email, 'expired', { expires: user.subscription_end?.slice(0, 10) });

        // 4. Kullanıcıya DM (opsiyonel — bot kullanıcıyla daha önce konuşmuşsa çalışır)
        if (user.telegram_user_id) {
            await sendTelegram(user.telegram_user_id,
                '❌ Your Nechh Robotics subscription has expired. You have been removed from the group.\n\n' +
                'Resubscribe: https://nechh-robotics-website.vercel.app/pricing.html'
            ).catch(() => {});
        }
    }

    return expired.length;
}

async function sendExpiryReminders() {
    const now = new Date();
    const in5d = new Date(now.getTime() + 5 * 86400_000).toISOString().slice(0, 10);
    const in1d = new Date(now.getTime() + 1 * 86400_000).toISOString().slice(0, 10);

    let reminded = 0;

    // 5 gün kalan
    const { data: remind5 } = await supabase.from('subscribers')
        .select('id, email, telegram_user_id, subscription_end')
        .eq('subscription_status', 'active')
        .like('subscription_end', `${in5d}%`);

    for (const u of (remind5 || [])) {
        await sendEmail(u.email, 'reminder_5d', { expires: in5d });
        if (u.telegram_user_id) {
            await sendTelegram(u.telegram_user_id,
                `⏰ Your Nechh Robotics subscription expires in 5 days (${in5d}).\nRenew: https://nechh-robotics-website.vercel.app/pricing.html`
            ).catch(() => {});
        }
        reminded++;
    }

    // 1 gün kalan
    const { data: remind1 } = await supabase.from('subscribers')
        .select('id, email, telegram_user_id, subscription_end')
        .eq('subscription_status', 'active')
        .like('subscription_end', `${in1d}%`);

    for (const u of (remind1 || [])) {
        await sendEmail(u.email, 'reminder_1d', { expires: in1d });
        if (u.telegram_user_id) {
            await sendTelegram(u.telegram_user_id,
                `🚨 Last day! Your subscription expires TOMORROW (${in1d}).\nRenew now: https://nechh-robotics-website.vercel.app/pricing.html`
            ).catch(() => {});
        }
        reminded++;
    }

    return reminded;
}

async function chasePendingPayments() {
    const threeDaysAgo = new Date(Date.now() - 3 * 86400_000).toISOString();

    // 3+ gündür pending olan kullanıcılar (ama daha önce hatırlatma yapılmamış)
    const { data: pending } = await supabase.from('subscribers')
        .select('id, email, telegram_user_id, last_payment_reminder_at, created_at')
        .eq('subscription_status', 'pending')
        .lt('created_at', threeDaysAgo)
        .or('last_payment_reminder_at.is.null,last_payment_reminder_at.lt.' + threeDaysAgo);

    for (const u of (pending || [])) {
        await sendEmail(u.email, 'payment_reminder');
        await supabase.from('subscribers')
            .update({ last_payment_reminder_at: new Date().toISOString() })
            .eq('id', u.id);
    }

    return pending?.length || 0;
}

async function sendAdminSummary(stats) {
    if (!ADMIN_CHAT) return;

    const { total, active, pending, expired_today, reminded, chased } = stats;

    const msg = `📊 <b>NECHH ROBOTICS — Günlük Özet</b>
━━━━━━━━━━━━━━━━━━━━━━━━
👥 Toplam üye: ${total}
✅ Aktif: ${active}
⏳ Ödeme bekliyor: ${pending}
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 Bugün süresi doldu: ${expired_today} kişi (gruptan çıkarıldı)
📧 Hatırlatma gönderildi: ${reminded} kişi
💳 Ödeme takibi: ${chased} kişi
━━━━━━━━━━━━━━━━━━━━━━━━
💰 Tahmini gelir: $${active * 55}/ay
<i>Admin panel: https://nechh-robotics-website.vercel.app/admin.html</i>`;

    await sendTelegram(ADMIN_CHAT, msg);
}

// ── Handler ───────────────────────────────────────────────────────────────────

module.exports = async function handler(req, res) {
    // Vercel Cron güvenlik başlığı
    if (req.headers['authorization'] !== `Bearer ${process.env.CRON_SECRET}`) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
        // Toplam istatistik
        const { count: total }  = await supabase.from('subscribers').select('*', { count: 'exact', head: true });
        const { count: active } = await supabase.from('subscribers').select('*', { count: 'exact', head: true }).eq('subscription_status', 'active');
        const { count: pending } = await supabase.from('subscribers').select('*', { count: 'exact', head: true }).eq('subscription_status', 'pending');

        const [expired_today, reminded, chased] = await Promise.all([
            checkExpiredSubscriptions(),
            sendExpiryReminders(),
            chasePendingPayments(),
        ]);

        const stats = { total: total || 0, active: active || 0, pending: pending || 0, expired_today, reminded, chased };
        await sendAdminSummary(stats);

        return res.status(200).json({ ok: true, ...stats });
    } catch (err) {
        console.error('[CRON] daily-check hatası:', err);
        // Admin'e hata bildir
        await sendTelegram(ADMIN_CHAT, `🚨 CRON HATA: ${err.message}`).catch(() => {});
        return res.status(500).json({ error: err.message });
    }
}
