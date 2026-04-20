// api/admin/subscribers.js
// Admin panel için abone listesi — sadece ADMIN_SECRET header ile erişilebilir.

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
const BOT_TOKEN   = process.env.TELEGRAM_BOT_TOKEN;
const GROUP_ID    = process.env.TELEGRAM_GROUP_ID;
const ADMIN_CHAT  = process.env.TELEGRAM_ADMIN_CHAT_ID;

function isAuthorized(req) {
    return req.headers['x-admin-secret'] === process.env.ADMIN_SECRET;
}

async function kickUser(telegramUserId) {
    if (!GROUP_ID || !telegramUserId) return false;
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/banChatMember`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: GROUP_ID, user_id: telegramUserId, revoke_messages: false }),
    });
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/unbanChatMember`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: GROUP_ID, user_id: telegramUserId, only_if_banned: true }),
    });
    return true;
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Secret');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (!isAuthorized(req))       return res.status(401).json({ error: 'Unauthorized' });

    // ── GET: abone listesi + istatistikler ────────────────────────────
    if (req.method === 'GET') {
        const { data: subscribers, error } = await supabase
            .from('subscribers')
            .select('id, email, telegram_username, telegram_user_id, country, plan, subscription_status, subscription_start, subscription_end, last_payment_at, warning_count, created_at')
            .order('created_at', { ascending: false });

        if (error) return res.status(500).json({ error: error.message });

        const total   = subscribers.length;
        const active  = subscribers.filter(u => u.subscription_status === 'active').length;
        const pending = subscribers.filter(u => u.subscription_status === 'pending').length;
        const expired = subscribers.filter(u => u.subscription_status === 'expired').length;
        const banned  = subscribers.filter(u => u.subscription_status === 'banned').length;

        const mrr = subscribers
            .filter(u => u.subscription_status === 'active')
            .reduce((sum, u) => sum + (u.plan === 'monthly' ? 55 : u.plan === 'quarterly' ? 45 : 35), 0);

        return res.status(200).json({
            stats: { total, active, pending, expired, banned, mrr },
            subscribers,
        });
    }

    // ── PATCH: kullanıcıya aksiyon uygula ─────────────────────────────
    if (req.method === 'PATCH') {
        const { id, action, note } = req.body || {};
        if (!id || !action) return res.status(400).json({ error: 'id ve action gerekli' });

        const { data: user } = await supabase.from('subscribers').select('*').eq('id', id).single();
        if (!user) return res.status(404).json({ error: 'Kullanıcı bulunamadı' });

        let update = { updated_at: new Date().toISOString() };
        let violationAction = null;

        switch (action) {
            case 'activate':
                update.subscription_status = 'active';
                update.subscription_start  = new Date().toISOString();
                update.subscription_end    = new Date(Date.now() + 30 * 86400_000).toISOString();
                break;
            case 'extend_30':
                const base = new Date(Math.max(Date.now(), new Date(user.subscription_end || Date.now()).getTime()));
                update.subscription_end = new Date(base.getTime() + 30 * 86400_000).toISOString();
                break;
            case 'cancel':
                update.subscription_status = 'cancelled';
                if (user.telegram_user_id) await kickUser(user.telegram_user_id);
                break;
            case 'ban':
                update.subscription_status = 'banned';
                if (user.telegram_user_id) await kickUser(user.telegram_user_id);
                violationAction = 'ban';
                break;
            case 'warn':
                update.warning_count = (user.warning_count || 0) + 1;
                violationAction = 'warning';
                // 3 uyarıda otomatik ban
                if (update.warning_count >= 3) {
                    update.subscription_status = 'banned';
                    if (user.telegram_user_id) await kickUser(user.telegram_user_id);
                    violationAction = 'ban';
                }
                break;
            default:
                return res.status(400).json({ error: 'Geçersiz aksiyon' });
        }

        if (note) update.notes = note;

        await supabase.from('subscribers').update(update).eq('id', id);

        // İhlal logu
        if (violationAction) {
            await supabase.from('violations').insert({
                subscriber_id:  id,
                violation_type: 'admin_action',
                description:    note || action,
                action_taken:   violationAction,
            });
        }

        // Admin bildirimi
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: ADMIN_CHAT,
                text: `⚡ Admin Aksiyonu\n👤 @${user.telegram_username || user.email}\n🔧 ${action.toUpperCase()}${note ? '\n📝 ' + note : ''}`,
            }),
        }).catch(() => {});

        return res.status(200).json({ ok: true, action, updated: update });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
