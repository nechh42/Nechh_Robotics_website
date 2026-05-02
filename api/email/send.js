// api/email/send.js — Nechh Robotics Email API (Resend)
// Vercel Serverless Function
// Env var: RESEND_API_KEY (set in Vercel dashboard)

const FROM_ADDRESS = 'Nechh Robotics <hello@nechhrobotics.com>';
const SITE_URL = 'https://nechh-robotics-website.vercel.app';

function getWelcomeHtml(email) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to Nechh Robotics</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 20px">
    <tr><td>
      <table width="600" cellpadding="0" cellspacing="0" align="center" style="background:#fff;border-radius:12px;overflow:hidden;max-width:600px;width:100%">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af,#2563eb);padding:40px 48px;text-align:center">
            <div style="font-size:28px;font-weight:800;color:#fff;letter-spacing:-0.5px">Nechh Robotics</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-top:6px;letter-spacing:2px;text-transform:uppercase">Algorithmic Trading Intelligence</div>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:48px">
            <h1 style="font-size:22px;font-weight:700;color:#111827;margin:0 0 16px">Welcome to the Free Weekly Report!</h1>
            <p style="font-size:15px;color:#374151;line-height:1.7;margin:0 0 24px">
              You're now subscribed to <strong>Nechh Robotics Market Reports</strong> — 
              a free weekly summary of algorithmic signals, key price levels, and risk notes 
              across crypto and major markets.
            </p>
            <p style="font-size:15px;color:#374151;line-height:1.7;margin:0 0 24px">
              Every <strong>Monday morning</strong>, you'll receive:
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 32px">
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid #f3f4f6">
                  <span style="color:#2563eb;font-weight:700;margin-right:10px">→</span>
                  <span style="font-size:14px;color:#374151">BTC/ETH/SOL trend direction (War Machine signals)</span>
                </td>
              </tr>
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid #f3f4f6">
                  <span style="color:#2563eb;font-weight:700;margin-right:10px">→</span>
                  <span style="font-size:14px;color:#374151">Key support/resistance levels with risk notes</span>
                </td>
              </tr>
              <tr>
                <td style="padding:10px 0;border-bottom:1px solid #f3f4f6">
                  <span style="color:#2563eb;font-weight:700;margin-right:10px">→</span>
                  <span style="font-size:14px;color:#374151">Profit Factor & drawdown updates</span>
                </td>
              </tr>
              <tr>
                <td style="padding:10px 0">
                  <span style="color:#2563eb;font-weight:700;margin-right:10px">→</span>
                  <span style="font-size:14px;color:#374151">No spam. Unsubscribe anytime.</span>
                </td>
              </tr>
            </table>
            <!-- CTA -->
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#2563eb;border-radius:8px;padding:14px 28px">
                  <a href="${SITE_URL}/performance.html" style="color:#fff;font-size:15px;font-weight:700;text-decoration:none">View Live Performance →</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <!-- Risk Disclaimer -->
        <tr>
          <td style="padding:0 48px 32px;border-top:1px solid #f3f4f6">
            <p style="font-size:11px;color:#9ca3af;line-height:1.6;margin:24px 0 0">
              <strong>Risk Disclosure:</strong> Algorithmic trading involves significant risk of loss. 
              Past performance does not guarantee future results. This email is for informational purposes only 
              and does not constitute financial advice. Never trade with money you cannot afford to lose.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:24px 48px;text-align:center">
            <p style="font-size:12px;color:#9ca3af;margin:0">
              Nechh Robotics · <a href="${SITE_URL}/legal/privacy.html" style="color:#6b7280">Privacy Policy</a> · 
              <a href="${SITE_URL}/legal/terms.html" style="color:#6b7280">Terms</a>
            </p>
            <p style="font-size:11px;color:#d1d5db;margin:8px 0 0">
              You received this because you signed up at nechhrobotics.com
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

function getWeeklyReportHtml(data) {
  const { week, btc, eth, sol, summary } = data || {};
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Weekly Market Report — Nechh Robotics</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 20px">
    <tr><td>
      <table width="600" cellpadding="0" cellspacing="0" align="center" style="background:#fff;border-radius:12px;overflow:hidden;max-width:600px;width:100%">
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af,#2563eb);padding:32px 48px;text-align:center">
            <div style="font-size:11px;color:rgba(255,255,255,0.6);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">Weekly Market Report</div>
            <div style="font-size:24px;font-weight:800;color:#fff">${week || 'This Week'} — Nechh Robotics</div>
          </td>
        </tr>
        <tr>
          <td style="padding:40px 48px">
            <h2 style="font-size:16px;font-weight:700;color:#111827;margin:0 0 20px;text-transform:uppercase;letter-spacing:1px">Signal Summary</h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:32px">
              <tr style="background:#f9fafb">
                <td style="padding:10px 16px;font-size:12px;font-weight:700;color:#6b7280;border-bottom:1px solid #e5e7eb">ASSET</td>
                <td style="padding:10px 16px;font-size:12px;font-weight:700;color:#6b7280;border-bottom:1px solid #e5e7eb">SIGNAL</td>
                <td style="padding:10px 16px;font-size:12px;font-weight:700;color:#6b7280;border-bottom:1px solid #e5e7eb">STATUS</td>
              </tr>
              <tr>
                <td style="padding:12px 16px;font-size:14px;font-weight:700;color:#111827;border-bottom:1px solid #f3f4f6">BTC/USDT</td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #f3f4f6">${btc?.signal || 'EMA Pullback'}</td>
                <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6"><span style="background:${btc?.trend === 'LONG' ? '#dcfce7' : '#fef3c7'};color:${btc?.trend === 'LONG' ? '#166534' : '#92400e'};padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700">${btc?.trend || 'NEUTRAL'}</span></td>
              </tr>
              <tr>
                <td style="padding:12px 16px;font-size:14px;font-weight:700;color:#111827;border-bottom:1px solid #f3f4f6">ETH/USDT</td>
                <td style="padding:12px 16px;font-size:14px;color:#374151;border-bottom:1px solid #f3f4f6">${eth?.signal || 'EMA Pullback'}</td>
                <td style="padding:12px 16px;border-bottom:1px solid #f3f4f6"><span style="background:${eth?.trend === 'LONG' ? '#dcfce7' : '#fef3c7'};color:${eth?.trend === 'LONG' ? '#166534' : '#92400e'};padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700">${eth?.trend || 'NEUTRAL'}</span></td>
              </tr>
              <tr>
                <td style="padding:12px 16px;font-size:14px;font-weight:700;color:#111827">SOL/USDT</td>
                <td style="padding:12px 16px;font-size:14px;color:#374151">${sol?.signal || 'EMA Pullback'}</td>
                <td style="padding:12px 16px"><span style="background:${sol?.trend === 'LONG' ? '#dcfce7' : '#fef3c7'};color:${sol?.trend === 'LONG' ? '#166534' : '#92400e'};padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700">${sol?.trend || 'NEUTRAL'}</span></td>
              </tr>
            </table>
            <p style="font-size:14px;color:#374151;line-height:1.7;margin:0 0 28px">${summary || 'Full report available on the performance dashboard.'}</p>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#2563eb;border-radius:8px;padding:12px 24px">
                  <a href="${SITE_URL}/performance.html" style="color:#fff;font-size:14px;font-weight:700;text-decoration:none">Full Performance Dashboard →</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:0 48px 32px">
            <p style="font-size:11px;color:#9ca3af;line-height:1.6;margin:0">
              <strong>Risk Disclosure:</strong> Past performance does not guarantee future results. 
              This report is for informational purposes only and does not constitute financial advice.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;padding:20px 48px;text-align:center">
            <p style="font-size:12px;color:#9ca3af;margin:0">
              <a href="${SITE_URL}/legal/privacy.html" style="color:#6b7280">Privacy</a> · 
              <a href="${SITE_URL}/legal/terms.html" style="color:#6b7280">Terms</a> · 
              Nechh Robotics
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', SITE_URL);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { to, type, data } = req.body || {};

  if (!to || !type) {
    return res.status(400).json({ error: 'Missing required fields: to, type' });
  }

  // Email format doğrulama
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) {
    return res.status(400).json({ error: 'Invalid email address' });
  }

  const RESEND_API_KEY = process.env.RESEND_API_KEY;
  if (!RESEND_API_KEY) {
    return res.status(500).json({ error: 'Email service not configured' });
  }

  const templates = {
    welcome: {
      subject: 'Welcome to Nechh Robotics — Your Weekly Reports Start Now',
      html: getWelcomeHtml(to),
    },
    weekly_report: {
      subject: `Weekly Market Report — ${data?.week || new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}`,
      html: getWeeklyReportHtml(data),
    },
  };

  if (!templates[type]) {
    return res.status(400).json({ error: `Unknown email type: ${type}` });
  }

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: FROM_ADDRESS,
        to: to,
        subject: templates[type].subject,
        html: templates[type].html,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      console.error('Resend API error:', result);
      return res.status(502).json({ error: 'Email delivery failed', detail: result });
    }

    return res.status(200).json({ success: true, emailId: result.id });
  } catch (err) {
    console.error('Email send error:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
