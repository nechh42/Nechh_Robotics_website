// api/register.js — npm paketi yok, saf fetch (Node 18 built-in)

const SB_URL     = process.env.SUPABASE_URL;
const SB_KEY     = process.env.SUPABASE_SERVICE_KEY;
const BOT_TOKEN  = process.env.TELEGRAM_BOT_TOKEN;
const ADMIN_CHAT = process.env.TELEGRAM_ADMIN_CHAT_ID;
const RESEND_KEY = process.env.RESEND_API_KEY;

function sbHeaders() {
    return { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'Content-Type': 'application/json', 'Prefer': 'return=representation' };
}

async function sbGetOne(query) {
    const r = await fetch(`${SB_URL}/rest/v1/subscribers?${query}&limit=1`, {
        headers: { ...sbHeaders(), 'Accept': 'application/vnd.pgrst.object+json' }
    });
    if (r.status === 406 || r.status === 404) return null;
    const d = await r.json();
    return d.code ? null : d;
}

async function sbInsert(body) {
    const r = await fetch(`${SB_URL}/rest/v1/subscribers`, { method: 'POST', headers: sbHeaders(), body: JSON.stringify(body) });
    if (!r.ok) { const e = await r.json(); throw new Error(e.message || e.details || 'Insert failed'); }
    return r.json();
}

async function sbPatch(id, body) {
    await fetch(`${SB_URL}/rest/v1/subscribers?id=eq.${encodeURIComponent(id)}`, { method: 'PATCH', headers: sbHeaders(), body: JSON.stringify(body) });
}

async function sendAdminAlert(text) {
    if (!ADMIN_CHAT || !BOT_TOKEN) return;
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: ADMIN_CHAT, text, parse_mode: 'HTML' }),
    }).catch(() => {});
}

async function sendWelcomeEmail(to, telegram) {
    if (!RESEND_KEY) return;
    await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${RESEND_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
            from: 'Nechh Robotics <noreply@nechh-robotics.com>',
            to: [to],
            subject: '✅ Registration received — Nechh Robotics',
            html: `<h2>Welcome to Nechh Robotics!</h2>
                   <p>Your registration is received. Complete your subscription to get access:</p>
                   <p><a href="https://nechh-robotics-website.vercel.app/pricing.html">Choose a plan →</a></p>
                   <hr>
                   <p style="color:#999;font-size:12px">
                     Telegram: ${telegram || '—'}<br>
                     This service provides market analysis only, not financial advice.
                   </p>`,
        }),
    }).catch(() => {});
}

module.exports = async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    const {
        email,
        telegram_username,
        country,
        plan = 'monthly',
        accepted_terms = false,
    } = req.body || {};

    // Basit doğrulama
    if (!email || !email.includes('@')) {
        return res.status(400).json({ error: 'Geçersiz email adresi.' });
    }
    if (!accepted_terms) {
        return res.status(400).json({ error: 'Kullanım koşullarını kabul etmelisiniz.' });
    }

    try {
        const existing = await sbGetOne(`email=eq.${encodeURIComponent(email.toLowerCase().trim())}&select=id,subscription_status`);

        if (existing) {
            if (existing.subscription_status === 'active') {
                return res.status(409).json({ error: 'Bu email zaten aktif bir aboneliğe sahip.' });
            }
            await sbPatch(existing.id, { telegram_username: telegram_username || null, country: country || null, plan, updated_at: new Date().toISOString() });
            return res.status(200).json({ ok: true, status: 'updated', message: 'Kaydınız güncellendi.' });
        }

        await sbInsert({
            email: email.toLowerCase().trim(),
            telegram_username: telegram_username ? telegram_username.replace('@', '') : null,
            country: country || null,
            plan,
            subscription_status: 'pending',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });

        await Promise.allSettled([
            sendWelcomeEmail(email, telegram_username),
            sendAdminAlert(
                `🆕 <b>Yeni Kayıt</b>\n` +
                `📧 ${email}\n` +
                `📱 @${telegram_username || '—'}\n` +
                `🌍 ${country || '—'}\n` +
                `📦 Plan: ${plan}\n` +
                `⏳ Durum: Ödeme bekleniyor`
            ),
        ]);

        return res.status(201).json({ ok: true, status: 'pending', message: 'Kayıt başarılı. Ödeme tamamlandığında erişiminiz aktif edilecek.' });

    } catch (err) {
        console.error('[REGISTER] Hata:', err);
        return res.status(500).json({ error: 'Sunucu hatası. Lütfen tekrar deneyin.' });
    }
}
