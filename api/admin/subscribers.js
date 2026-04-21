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
