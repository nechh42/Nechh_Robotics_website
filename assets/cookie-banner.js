(function () {
  if (localStorage.getItem('nb_cookies_ok')) return;
  var isLegal = window.location.pathname.includes('/legal/');
  var privacyLink = isLegal ? 'privacy.html' : 'legal/privacy.html';
  var banner = document.createElement('div');
  banner.id = 'cookie-banner';
  banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#1f2937;color:#f9fafb;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:12px;z-index:9999;flex-wrap:wrap;font-family:Inter,system-ui,sans-serif';
  banner.innerHTML =
    '<span>We use cookies to improve your experience and analyze site traffic. <a href="' + privacyLink + '" style="color:#60a5fa;text-decoration:underline">Learn more</a></span>' +
    '<div style="display:flex;gap:8px;flex-shrink:0">' +
    '<button id="cookie-decline" style="background:transparent;color:#9ca3af;border:1px solid #4b5563;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">Decline</button>' +
    '<button id="cookie-accept" style="background:#2563eb;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px">Accept All</button>' +
    '</div>';
  document.body.appendChild(banner);
  document.getElementById('cookie-accept').addEventListener('click', function () {
    localStorage.setItem('nb_cookies_ok', '1');
    banner.remove();
  });
  document.getElementById('cookie-decline').addEventListener('click', function () {
    localStorage.setItem('nb_cookies_ok', '0');
    banner.remove();
  });
})();
