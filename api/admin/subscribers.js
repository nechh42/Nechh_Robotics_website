// api/admin/subscribers.js
// Node built-in https modülü kullanır — npm paketi yok.

const https = require('https');

const SB_HOST = 'beuajrnifarxewnwsmml.supabase.co';
const SB_KEY  = process.env.SUPABASE_SERVICE_KEY;
const BOT     = process.env.TELEGRAM_BOT_TOKEN;
const GROUP   = process.env.TELEGRAM_GROUP_ID;
const ADMIN   = process.env.TELEGRAM_ADMIN_CHAT_ID;

// ── HTTPS yardımcısı ──────────────────────────────────────────────────
function httpsReq(options, body) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
                catch(e) { resolve({ status: res.statusCode, body: data }); }
            });
        });
        req.on('error', reject);
        if (body) req.write(body);
        req.end();
    });
}

function sbOpts(method, path, extra) {
    return { hostname: SB_HOST, path: '/rest/v1/' + path, method, headers: Object.assign({ 'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY, 'Content-Type': 'application/json', 'Prefer': 'return=representation' }, extra || {}) };
}

async function sbGet(path) {
    const r = await httpsReq(sbOpts('GET', path));
    return Array.isArray(r.body) ? r.body : [];
}

async function sbGetOne(path) {
    const r = await httpsReq(sbOpts('GET', path, { 'Accept': 'application/vnd.pgrst.object+json' }));
    if (r.status === 406 || r.status === 404) return null;
    return (r.body && !r.body.code) ? r.body : null;
}

async function sbPatch(path, body) {
    const s = JSON.stringify(body);
    const o = sbOpts('PATCH', path);
    o.headers['Content-Length'] = Buffer.byteLength(s);
    await httpsReq(o, s);
}

async function sbInsert(table, body) {
    const s = JSON.stringify(body);
    const o = sbOpts('POST', table);
    o.headers['Content-Length'] = Buffer.byteLength(s);
    await httpsReq(o, s);
}

function tgSend(chatId, text) {
    if (!BOT || !chatId) return Promise.resolve();
    const s = JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' });
    return httpsReq({ hostname: 'api.telegram.org', path: '/bot' + BOT + '/sendMessage', method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(s) } }, s).catch(function(){});
}

async function kickUser(uid) {
    if (!GROUP || !uid) return;
    const s1 = JSON.stringify({ chat_id: GROUP, user_id: uid, revoke_messages: false });
    await httpsReq({ hostname: 'api.telegram.org', path: '/bot' + BOT + '/banChatMember', method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(s1) } }, s1).catch(function(){});
    const s2 = JSON.stringify({ chat_id: GROUP, user_id: uid, only_if_banned: true });
    await httpsReq({ hostname: 'api.telegram.org', path: '/bot' + BOT + '/unbanChatMember', method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(s2) } }, s2).catch(function(){});
}

module.exports = async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, PATCH, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Secret');
    if (req.method === 'OPTIONS') return res.status(200).end();
    if (req.headers['x-admin-secret'] !== process.env.ADMIN_SECRET) return res.status(401).json({ error: 'Unauthorized' });

    try {
        if (req.method === 'GET') {
            const subs = await sbGet('subscribers?select=id,email,telegram_username,telegram_user_id,country,plan,subscription_status,subscription_start,subscription_end,last_payment_at,warning_count,created_at&order=created_at.desc');
            const total   = subs.length;
            const active  = subs.filter(function(u){ return u.subscription_status === 'active'; }).length;
            const pending = subs.filter(function(u){ return u.subscription_status === 'pending'; }).length;
            const expired = subs.filter(function(u){ return u.subscription_status === 'expired'; }).length;
            const banned  = subs.filter(function(u){ return u.subscription_status === 'banned'; }).length;
            const mrr     = subs.filter(function(u){ return u.subscription_status === 'active'; })
                .reduce(function(s, u){ return s + (u.plan === 'quarterly' ? 45 : u.plan === 'annual' ? 35 : 55); }, 0);
            return res.status(200).json({ stats: { total, active, pending, expired, banned, mrr }, subscribers: subs });
        }

        if (req.method === 'PATCH') {
            var _b = req.body || {};
            var id = _b.id, action = _b.action, note = _b.note;
            if (!id || !action) return res.status(400).json({ error: 'id ve action gerekli' });

            var user = await sbGetOne('subscribers?id=eq.' + encodeURIComponent(id) + '&select=*');
            if (!user) return res.status(404).json({ error: 'Kullanıcı bulunamadı' });

            var update = { updated_at: new Date().toISOString() };
            var vAction = null;

            if (action === 'activate') {
                update.subscription_status = 'active';
                update.subscription_start  = new Date().toISOString();
                update.subscription_end    = new Date(Date.now() + 30 * 86400000).toISOString();
            } else if (action === 'extend_30') {
                var base = Math.max(Date.now(), new Date(user.subscription_end || Date.now()).getTime());
                update.subscription_end = new Date(base + 30 * 86400000).toISOString();
            } else if (action === 'cancel') {
                update.subscription_status = 'cancelled';
                if (user.telegram_user_id) await kickUser(user.telegram_user_id);
            } else if (action === 'ban') {
                update.subscription_status = 'banned';
                if (user.telegram_user_id) await kickUser(user.telegram_user_id);
                vAction = 'ban';
            } else if (action === 'warn') {
                update.warning_count = (user.warning_count || 0) + 1;
                vAction = 'warning';
                if (update.warning_count >= 3) {
                    update.subscription_status = 'banned';
                    if (user.telegram_user_id) await kickUser(user.telegram_user_id);
                    vAction = 'ban';
                }
            } else {
                return res.status(400).json({ error: 'Gecersiz aksiyon' });
            }

            if (note) update.notes = note;
            await sbPatch('subscribers?id=eq.' + encodeURIComponent(id), update);
            if (vAction) await sbInsert('violations', { subscriber_id: id, violation_type: 'admin_action', description: note || action, action_taken: vAction });
            await tgSend(ADMIN, 'Admin: ' + (user.telegram_username || user.email) + ' -> ' + action);
            return res.status(200).json({ ok: true });
        }

        return res.status(405).json({ error: 'Method not allowed' });
    } catch (err) {
        return res.status(500).json({ error: err.message });
    }
};

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

    try {
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
            case 'extend_30': {
                const base = new Date(Math.max(Date.now(), new Date(user.subscription_end || Date.now()).getTime()));
                update.subscription_end = new Date(base.getTime() + 30 * 86400_000).toISOString();
                break;
            }
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
    } catch(err) {
        return res.status(500).json({ error: err.message, stack: err.stack });
    }
}
