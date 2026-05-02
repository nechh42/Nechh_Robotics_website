// GA4 Event Tracking — Nechh Robotics
// Otomatik olarak çalışır: abone butonları, form submit, FAQ açma, blog okuma

(function() {
  'use strict';

  function gtagEvent(name, params) {
    if (typeof gtag === 'function') {
      gtag('event', name, params || {});
    }
  }

  document.addEventListener('DOMContentLoaded', function () {

    // 1. Subscribe / CTA button clicks
    document.querySelectorAll('a[href*="pricing"], a.nav-cta, a.cta-btn, .pricing-cta, [data-track="subscribe"]').forEach(function (el) {
      el.addEventListener('click', function () {
        gtagEvent('subscribe_click', {
          button_text: el.innerText.trim().substring(0, 50),
          page: window.location.pathname
        });
      });
    });

    // 2. Lead magnet form submit
    var leadForm = document.getElementById('lead-form');
    if (leadForm) {
      leadForm.addEventListener('submit', function () {
        gtagEvent('lead_magnet_submit', { page: window.location.pathname });
      });
    }

    // 3. Contact form submit
    var contactForm = document.querySelector('form[action*="formspree"]');
    if (contactForm) {
      contactForm.addEventListener('submit', function () {
        gtagEvent('contact_form_submit', { page: window.location.pathname });
      });
    }

    // 4. FAQ accordion open
    document.querySelectorAll('.faq-q, .faq-question, [data-faq]').forEach(function (el) {
      el.addEventListener('click', function () {
        gtagEvent('faq_open', {
          question: el.innerText.trim().substring(0, 80)
        });
      });
    });

    // 5. Blog article read (scroll past 50%)
    if (document.querySelector('.article-wrap')) {
      var tracked = false;
      window.addEventListener('scroll', function () {
        if (tracked) return;
        var scrollPct = (window.scrollY + window.innerHeight) / document.body.scrollHeight;
        if (scrollPct > 0.5) {
          tracked = true;
          gtagEvent('blog_read_50pct', {
            article: document.title.substring(0, 80)
          });
        }
      });
    }

    // 6. External links (Telegram, social)
    document.querySelectorAll('a[href^="https://t.me"], a[href*="telegram"], a[href*="twitter"], a[href*="linkedin"]').forEach(function (el) {
      el.addEventListener('click', function () {
        gtagEvent('social_click', {
          platform: el.href.includes('t.me') || el.href.includes('telegram') ? 'telegram'
            : el.href.includes('twitter') ? 'twitter'
            : 'linkedin',
          page: window.location.pathname
        });
      });
    });

    // 7. Cookie banner accept/decline
    document.addEventListener('cookie_accept', function () {
      gtagEvent('cookie_accept');
    });
    document.addEventListener('cookie_decline', function () {
      gtagEvent('cookie_decline');
    });

  });

})();
