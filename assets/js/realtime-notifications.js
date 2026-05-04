// Real-time Notifications — Nechh Robotics
(function() {
  'use strict';

  const CHECK_INTERVAL = 30000; // 30 seconds
  const TOAST_DURATION = 8000;
  let lastTradeCount = 0;

  function createToast(title, body, type) {
    const existing = document.getElementById('nechh-toast-container');
    const container = existing || document.createElement('div');
    if (!existing) {
      container.id = 'nechh-toast-container';
      container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:10px;max-width:320px;font-family:system-ui,sans-serif;';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const color = type === 'long' ? '#00d4aa' : type === 'short' ? '#ff4d6d' : '#4d9fff';
    toast.style.cssText = `
      background:#12121a;border:1px solid ${color}33;border-left:4px solid ${color};
      border-radius:10px;padding:14px 18px;color:#e0e0f0;
      box-shadow:0 8px 32px rgba(0,0,0,0.4);
      animation:slideIn 0.3s ease;cursor:pointer;font-size:13px;
    `;
    toast.innerHTML = `
      <div style="font-weight:700;margin-bottom:4px;display:flex;align-items:center;gap:8px;">
        <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block;"></span>
        ${title}
      </div>
      <div style="color:#a3a3a3;font-size:12px;line-height:1.5;">${body}</div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(120%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, TOAST_DURATION);

    toast.addEventListener('click', () => {
      window.location.href = '/dashboard.html';
    });
  }

  async function checkForNewSignals() {
    try {
      const r = await fetch('/trades.json?' + Date.now(), { cache: 'no-store' });
      const d = await r.json();
      const trades = d.trades || d.signals || [];
      const currentCount = trades.length;

      if (lastTradeCount === 0) {
        lastTradeCount = currentCount;
        return;
      }

      if (currentCount > lastTradeCount) {
        const newest = trades[currentCount - 1];
        const pair = newest.pair || newest.symbol || 'BTC/USD';
        const side = newest.side || newest.type || 'Long';
        const entry = newest.entry || newest.entry_price || '';
        const color = side.toLowerCase().includes('short') ? 'short' : 'long';
        createToast(
          pair + ' — ' + side + ' Signal',
          'Entry: ' + entry + (newest.stop ? ' | Stop: ' + newest.stop : '') + (newest.target ? ' | Target: ' + newest.target : ''),
          color
        );
        // Browser notification
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('Nechh Robotics — New Signal', {
            body: pair + ' ' + side + ' @ ' + entry,
            icon: '/assets/icon-192.png'
          });
        }
        if (typeof gtag === 'function') {
          gtag('event', 'signal_notification', { pair, side });
        }
      }
      lastTradeCount = currentCount;
    } catch(e) {}
  }

  function requestBrowserNotification() {
    if ('Notification' in window && Notification.permission === 'default') {
      // Show a small inline prompt after 10s
      setTimeout(() => {
        const prompt = document.createElement('div');
        prompt.style.cssText = 'position:fixed;bottom:80px;right:20px;z-index:99998;background:#12121a;border:1px solid #2a2a3a;border-radius:10px;padding:14px 18px;max-width:260px;font-size:12px;color:#e0e0f0;box-shadow:0 8px 32px rgba(0,0,0,0.4);';
        prompt.innerHTML = `
          <div style="font-weight:700;margin-bottom:6px;">Enable Push Alerts?</div>
          <div style="color:#a3a3a3;margin-bottom:10px;">Get instant signal notifications.</div>
          <div style="display:flex;gap:8px;">
            <button id="nb-notify-yes" style="flex:1;padding:6px 10px;background:#4d9fff;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;">Allow</button>
            <button id="nb-notify-no" style="flex:1;padding:6px 10px;background:#2a2a3a;color:#a3a3a3;border:none;border-radius:6px;cursor:pointer;font-size:12px;">No</button>
          </div>
        `;
        document.body.appendChild(prompt);
        document.getElementById('nb-notify-yes').addEventListener('click', () => {
          Notification.requestPermission();
          prompt.remove();
        });
        document.getElementById('nb-notify-no').addEventListener('click', () => prompt.remove());
      }, 10000);
    }
  }

  // Inject slide-in keyframes if not present
  if (!document.getElementById('nechh-toast-style')) {
    const style = document.createElement('style');
    style.id = 'nechh-toast-style';
    style.textContent = '@keyframes slideIn{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}';
    document.head.appendChild(style);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      checkForNewSignals();
      setInterval(checkForNewSignals, CHECK_INTERVAL);
      requestBrowserNotification();
    });
  } else {
    checkForNewSignals();
    setInterval(checkForNewSignals, CHECK_INTERVAL);
    requestBrowserNotification();
  }
})();
