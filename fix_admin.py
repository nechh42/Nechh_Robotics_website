import os

html = '''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nechh Robotics - Admin Panel</title>
<style>
:root{--bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a26;--border:#2a2a3a;--text:#e0e0f0;--muted:#6b6b8a;--green:#00d4aa;--red:#ff4d6d;--blue:#4d9fff;--gold:#ffd166;--font:'Segoe UI',system-ui,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:13px}
#loginWrap{display:flex;align-items:center;justify-content:center;min-height:100vh}
#loginBox{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:40px;width:340px;text-align:center}
#loginBox h2{margin-bottom:20px;color:var(--blue);letter-spacing:2px}
#adminPass{width:100%;padding:10px;background:var(--bg3);border:1px solid var(--border);color:var(--text);border-radius:6px;font-family:var(--font);margin-bottom:12px}
#loginBtn{width:100%;padding:10px;background:var(--blue);color:#fff;border:none;border-radius:6px;cursor:pointer;font-family:var(--font);font-weight:bold}
#app{display:none;padding:20px;max-width:1300px;margin:0 auto}
nav{border-bottom:1px solid var(--border);padding:12px 0;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}
.nav-logo{color:var(--blue);font-weight:bold;letter-spacing:2px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.stat-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:16px;text-align:center}
.stat-card h3{font-size:28px;font-weight:bold;margin-bottom:4px}
.stat-card p{color:var(--muted);font-size:10px;letter-spacing:1px}
.controls{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center}
.controls input{padding:8px 12px;background:var(--bg2);border:1px solid var(--border);color:var(--text);border-radius:6px;font-family:var(--font);font-size:12px;width:200px}
.btn{padding:7px 14px;border:1px solid var(--border);background:var(--bg2);color:var(--text);border-radius:6px;cursor:pointer;font-family:var(--font);font-size:11px;letter-spacing:1px}
.btn:hover{border-color:var(--blue);color:var(--blue)}
.btn-green{border-color:var(--green);color:var(--green)}
.btn-red{border-color:var(--red);color:var(--red)}
.table-wrap{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:10px 12px;text-align:left;color:var(--muted);font-size:10px;letter-spacing:1px;border-bottom:1px solid var(--border)}
td{padding:9px 12px;font-size:12px;border-bottom:1px solid rgba(42,42,58,0.5);vertical-align:middle}
tr:hover td{background:rgba(77,159,255,0.03)}
.badge{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:bold;border:1px solid}
.badge-active{color:var(--green);border-color:var(--green);background:rgba(0,212,170,0.08)}
.badge-pending{color:var(--gold);border-color:var(--gold);background:rgba(255,209,102,0.08)}
.badge-expired{color:var(--red);border-color:var(--red);background:rgba(255,77,109,0.08)}
.badge-banned{color:var(--muted);border-color:var(--muted);background:rgba(107,107,138,0.08)}
.action-btns{display:flex;gap:4px;flex-wrap:wrap}
.action-btns button{padding:3px 7px;font-size:10px;border-radius:4px;border:1px solid;cursor:pointer;background:transparent;font-family:var(--font)}
</style>
</head>
<body>

<div id="loginWrap">
  <div id="loginBox">
    <h2>&#9889; ADMIN</h2>
    <input id="adminPass" type="password" placeholder="Admin sifresi" autocomplete="off">
    <button id="loginBtn" onclick="doLogin()">GIRIS YAP</button>
    <p id="loginErr" style="color:var(--red);margin-top:10px;font-size:11px"></p>
  </div>
</div>

<div id="app">
  <nav>
    <span class="nav-logo">NECHH ROBOTICS &#8211; ADMIN</span>
    <div style="display:flex;gap:8px">
      <button class="btn" onclick="loadData()">&#8595; Yenile</button>
      <button class="btn" onclick="exportCSV()">&#8595; CSV</button>
      <button class="btn btn-red" onclick="logout()">Cikis</button>
    </div>
  </nav>

  <div class="stats">
    <div class="stat-card"><h3 id="s-total" class="blue">&#8211;</h3><p>TOPLAM UYE</p></div>
    <div class="stat-card"><h3 id="s-active" style="color:var(--green)">&#8211;</h3><p>AKTIF</p></div>
    <div class="stat-card"><h3 id="s-pending" style="color:var(--gold)">&#8211;</h3><p>ODEME BEKLEYEN</p></div>
    <div class="stat-card"><h3 id="s-expired" style="color:var(--red)">&#8211;</h3><p>SURESI DOLMUS</p></div>
    <div class="stat-card"><h3 id="s-mrr" style="color:var(--green)">&#8211;</h3><p>AYLIK GELIR</p></div>
  </div>

  <div class="controls">
    <input id="searchInput" type="text" placeholder="Email veya Telegram ara..." oninput="filterTable()">
    <select id="filterStatus" onchange="filterTable()" style="padding:8px;background:var(--bg2);border:1px solid var(--border);color:var(--text);border-radius:6px;font-family:var(--font)">
      <option value="">Tum durumlar</option>
      <option value="active">Aktif</option>
      <option value="pending">Odeme Bekleyen</option>
      <option value="expired">Suresi Dolmus</option>
      <option value="banned">Banli</option>
    </select>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>EMAIL</th><th>TELEGRAM</th><th>PLAN</th><th>DURUM</th>
          <th>BITIS TARIHI</th><th>UYARI</th><th>KAYIT</th><th>AKSIYON</th>
        </tr>
      </thead>
      <tbody id="usersTbody"></tbody>
    </table>
  </div>
</div>

<script>
let ADMIN_SECRET = '';
let ALL_USERS = [];

function doLogin() {
  const pass = document.getElementById('adminPass').value;
  if (!pass) return;
  ADMIN_SECRET = pass;
  loadData();
}

function logout() {
  ADMIN_SECRET = '';
  document.getElementById('app').style.display = 'none';
  document.getElementById('loginWrap').style.display = 'flex';
  document.getElementById('adminPass').value = '';
}

async function loadData() {
  try {
    const r = await fetch('/api/admin/subscribers', {
      headers: { 'X-Admin-Secret': ADMIN_SECRET }
    });
    if (r.status === 401) {
      document.getElementById('loginErr').textContent = 'Yanlis sifre.';
      return;
    }
    const data = await r.json();
    document.getElementById('loginErr').textContent = '';
    document.getElementById('loginWrap').style.display = 'none';
    document.getElementById('app').style.display = 'block';

    const s = data.stats;
    document.getElementById('s-total').textContent  = s.total;
    document.getElementById('s-active').textContent = s.active;
    document.getElementById('s-pending').textContent= s.pending;
    document.getElementById('s-expired').textContent= s.expired + (s.banned ? ' (+'+s.banned+' ban)' : '');
    document.getElementById('s-mrr').textContent    = '$' + s.mrr;

    ALL_USERS = data.subscribers || [];
    renderTable(ALL_USERS);
  } catch(e) {
    document.getElementById('loginErr').textContent = 'Baglanti hatasi: ' + e.message;
  }
}

function renderTable(users) {
  const tbody = document.getElementById('usersTbody');
  if (!users.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">Kayit yok</td></tr>';
    return;
  }
  tbody.innerHTML = users.map(u => {
    const end  = u.subscription_end ? new Date(u.subscription_end).toLocaleDateString('tr-TR') : '&#8211;';
    const reg  = new Date(u.created_at).toLocaleDateString('tr-TR');
    const daysLeft = u.subscription_end
      ? Math.ceil((new Date(u.subscription_end) - Date.now()) / 86400_000)
      : null;
    const endDisplay = daysLeft !== null
      ? `${end} <span style="color:${daysLeft<0?'var(--red)':daysLeft<5?'var(--gold)':'var(--muted)'};">(${daysLeft<0?'suresi doldu':daysLeft+'g'})</span>`
      : '&#8211;';

    return `<tr data-email="${u.email}" data-tg="${u.telegram_username||''}" data-status="${u.subscription_status}">
      <td>${u.email}</td>
      <td>${u.telegram_username ? '@'+u.telegram_username : '&#8211;'}</td>
      <td style="color:var(--muted)">${u.plan||'&#8211;'}</td>
      <td><span class="badge badge-${u.subscription_status}">${u.subscription_status.toUpperCase()}</span></td>
      <td>${endDisplay}</td>
      <td style="color:${(u.warning_count||0)>0?'var(--gold)':'var(--muted)'}">${u.warning_count||0}/3</td>
      <td style="color:var(--muted)">${reg}</td>
      <td><div class="action-btns">
        <button onclick="action('${u.id}','activate')" style="color:var(--green);border-color:var(--green)">&#10004; Aktif</button>
        <button onclick="action('${u.id}','extend_30')" style="color:var(--blue);border-color:var(--blue)">+30g</button>
        <button onclick="action('${u.id}','warn')" style="color:var(--gold);border-color:var(--gold)">&#9888; Uyar</button>
        <button onclick="action('${u.id}','ban')" style="color:var(--red);border-color:var(--red)">&#128308; Ban</button>
      </div></td>
    </tr>`;
  }).join('');
}

async function action(id, act) {
  const labels = { activate:'Aktif et', extend_30:'+30 gun ekle', warn:'Uyari gonder', ban:'BANLA', cancel:'Iptal et' };
  if (!confirm((labels[act] || act) + '?')) return;
  const note = (act === 'warn' || act === 'ban') ? prompt('Sebep (opsiyonel):') : null;
  const r = await fetch('/api/admin/subscribers', {
    method: 'PATCH',
    headers: { 'Content-Type':'application/json', 'X-Admin-Secret': ADMIN_SECRET },
    body: JSON.stringify({ id, action: act, note }),
  });
  const d = await r.json();
  if (d.ok) { await loadData(); }
  else alert('Hata: ' + d.error);
}

function filterTable() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const st = document.getElementById('filterStatus').value;
  const filtered = ALL_USERS.filter(u =>
    (!q || u.email.toLowerCase().includes(q) || (u.telegram_username||'').toLowerCase().includes(q)) &&
    (!st || u.subscription_status === st)
  );
  renderTable(filtered);
}

function exportCSV() {
  const cols = ['email','telegram_username','plan','subscription_status','subscription_end','warning_count','created_at'];
  const rows = [cols.join(','), ...ALL_USERS.map(u => cols.map(c => JSON.stringify(u[c]??'')).join(','))];
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([rows.join('\\n')], {type:'text/csv'}));
  a.download = 'nechh_subscribers_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}

document.getElementById('adminPass').addEventListener('keydown', e => { if(e.key==='Enter') doLogin(); });
setInterval(() => { if (ADMIN_SECRET) loadData(); }, 60000);
</script>
<script src="assets/js/legal-modal.js" defer></script>
</body>
</html>
'''

with open('website_repo/admin.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('admin.html fixed.')
