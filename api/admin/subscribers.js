// api/admin/subscribers.js — npm paketi yok, saf fetch (Node 18 built-in)

const SB_URL = process.env.SUPABASE_URL;
const SB_KEY = process.env.SUPABASE_SERVICE_KEY;
const BOT_TOKEN  = process.env.TELEGRAM_BOT_TOKEN;
const GROUP_ID   = process.env.TELEGRAM_GROUP_ID;
const ADMIN_CHAT = process.env.TELEGRAM_ADMIN_CHAT_ID;

// ── Supabase REST yardımcıları ─────────────────────────────────────────
function sbHeaders() {
    return { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'Content-Type': 'application/json', 'Prefer': 'return=representation' };
}

async function sbGet(table, query = '') {
    const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { headers: sbHeaders() });
    const data = await r.json();
    return { data: Array.isArray(data) ? data : [], error: data.error || null };
}

async function sbGetOne(table, query = '') {
    const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}&limit=1`, { headers: { ...sbHeaders(), 'Accept': 'application/vnd.pgrst.object+json' } });
    if (r.status === 406 || r.status === 404) return { data: null };
    const data = await r.json();
    return { data: data.code ? null : data };
}

async function sbPatch(table, match, body) {
    const r = await fetch(`${SB_URL}/rest/v1/${table}?${match}`, { method: 'PATCH', headers: sbHeaders(), body: JSON.stringify(body) });
    return r.ok;
}

async function sbInsert(table, body) {
    const r = await fetch(`${SB_URL}/rest/v1/${table}`, { method: 'POST', headers: sbHeaders(), body: JSON.stringify(body) });
    return r.ok;
}

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

module.exports = async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Secret');

    if (req.method === 'OPTIONS') return res.status(200).end();
    if (!isAuthorized(req))       return res.status(401).json({ error: 'Unauthorized' });

    // ── GET: abone listesi + istatistikler ────────────────────────────
    if (req.method === 'GET') {
        const { data: subscribers, error } = await sbGet('subscribers',
            'select=id,email,telegram_username,telegram_user_id,country,plan,subscription_status,subscription_start,subscription_end,last_payment_at,warning_count,created_at&order=created_at.desc'
        );
        if (error) return res.status(500).json({ error });

        const total   = subscribers.length;
        const active  = subscribers.filter(u => u.subscription_status === 'active').length;
        const pending = subscribers.filter(u => u.subscription_status === 'pending').length;
        const expired = subscribers.filter(u => u.subscription_status === 'expired').length;
        const banned  = subscribers.filter(u => u.subscription_status === 'banned').length;
        const mrr     = subscribers.filter(u => u.subscription_status === 'active')
            .reduce((s, u) => s + (u.plan === 'monthly' ? 55 : u.plan === 'quarterly' ? 45 : 35), 0);

        return res.status(200).json({ stats: { total, active, pending, expired, banned, mrr }, subscribers });
    }

    // ── PATCH: kullanıcıya aksiyon uygula ─────────────────────────────
    if (req.method === 'PATCH') {
        const { id, action, note } = req.body || {};
        if (!id || !action) return res.status(400).json({ error: 'id ve action gerekli' });

        const { data: user } = await sbGetOne('subscribers', `id=eq.${encodeURIComponent(id)}&select=*`);
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

        await sbPatch('subscribers', `id=eq.${encodeURIComponent(id)}`, update);

        if (violationAction) {
            await sbInsert('violations', { subscriber_id: id, violation_type: 'admin_action', description: note || action, action_taken: violationAction });
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
