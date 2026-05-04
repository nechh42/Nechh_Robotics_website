// Affiliate Tracker — Nechh Robotics
(function() {
  'use strict';

  const STORAGE_KEY = 'nechh_ref';
  const STATS_KEY = 'nechh_ref_stats';

  function getParams() {
    const q = new URLSearchParams(window.location.search);
    return q.get('ref');
  }

  function storeRef(code) {
    if (!code) return;
    const existing = localStorage.getItem(STORAGE_KEY);
    if (!existing) {
      localStorage.setItem(STORAGE_KEY, code);
      localStorage.setItem(STORAGE_KEY + '_at', new Date().toISOString());
    }
  }

  function trackClick() {
    const stats = JSON.parse(localStorage.getItem(STATS_KEY) || '{}');
    stats.clicks = (stats.clicks || 0) + 1;
    localStorage.setItem(STATS_KEY, JSON.stringify(stats));
  }

  function trackConversion(planValue) {
    const stats = JSON.parse(localStorage.getItem(STATS_KEY) || '{}');
    stats.signups = (stats.signups || 0) + 1;
    stats.earn = (stats.earn || 0) + (planValue || 0) * 0.30;
    stats.conv = stats.signups ? ((stats.signups / Math.max(stats.clicks, 1)) * 100).toFixed(1) : 0;
    localStorage.setItem(STATS_KEY, JSON.stringify(stats));
  }

  // Capture ref param on landing
  const refCode = getParams();
  if (refCode) storeRef(refCode);

  // Track click for affiliates
  if (refCode) trackClick();

  // Attach conversion tracking to pricing CTAs
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('a[href*="pricing"], .nav-cta, .btn-primary, [data-track="subscribe"]').forEach(function(el) {
      el.addEventListener('click', function() {
        if (typeof gtag === 'function') {
          gtag('event', 'affiliate_click', {
            ref: localStorage.getItem(STORAGE_KEY) || 'direct'
          });
        }
      });
    });
  });

  window.affiliateTrackConversion = trackConversion;
})();
