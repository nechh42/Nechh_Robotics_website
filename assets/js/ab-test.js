// A/B Test System — Nechh Robotics
// Deterministic assignment: visitors stay in the same bucket forever
(function() {
  'use strict';

  const EXPERIMENTS = [
    {
      id: 'hero_cta_v1',
      selector: '.hero-actions a.btn-primary, .hero-actions .btn-primary, a.nav-cta',
      variants: [
        { weight: 0.5, text: 'Get Access \u2192', label: 'control' },
        { weight: 0.25, text: 'Start Free Trial \u2192', label: 'variant_a' },
        { weight: 0.25, text: 'Join Now \u2192', label: 'variant_b' }
      ]
    }
  ];

  function getBucket(experimentId) {
    const key = 'nechh_ab_' + experimentId;
    let stored = localStorage.getItem(key);
    if (stored) return stored;

    // Deterministic hash from a random seed stored per user
    let seed = localStorage.getItem('nechh_ab_seed');
    if (!seed) {
      seed = Math.random().toString(36).slice(2);
      localStorage.setItem('nechh_ab_seed', seed);
    }
    const hash = seed.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
    stored = String(hash % 100);
    localStorage.setItem(key, stored);
    return stored;
  }

  function pickVariant(experiment, bucket) {
    let cumulative = 0;
    const bucketNum = parseInt(bucket, 10);
    for (const v of experiment.variants) {
      cumulative += v.weight * 100;
      if (bucketNum < cumulative) return v;
    }
    return experiment.variants[0];
  }

  function run() {
    EXPERIMENTS.forEach(exp => {
      const bucket = getBucket(exp.id);
      const variant = pickVariant(exp, bucket);
      const els = document.querySelectorAll(exp.selector);
      els.forEach(el => {
        if (el.textContent.trim() !== variant.text.trim()) {
          el.textContent = variant.text;
        }
        el.setAttribute('data-ab-test', exp.id + ':' + variant.label);
      });
      // GA4 event
      if (typeof gtag === 'function') {
        gtag('event', 'ab_exposure', {
          experiment_id: exp.id,
          variant: variant.label
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
