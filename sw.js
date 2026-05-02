// Service Worker — Nechh Robotics PWA
// Strateji: Network-first (canlı içerik öncelikli), statik assets cache'le

const CACHE_NAME = 'nechh-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/about.html',
  '/blog.html',
  '/performance.html',
  '/pricing.html',
  '/contact.html',
  '/faq.html',
  '/assets/cookie-banner.js',
  '/assets/analytics-events.js',
  '/manifest.json'
];

// Install: statik dosyaları önbelleğe al
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: eski cache'leri temizle
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first, fallback cache
self.addEventListener('fetch', function(event) {
  // Sadece GET isteklerini yakala
  if (event.request.method !== 'GET') return;
  // Chrome extension ve non-http isteklerini geç
  if (!event.request.url.startsWith('http')) return;

  event.respondWith(
    fetch(event.request)
      .then(function(response) {
        // Başarılı yanıtı cache'le (statik dosyalar için)
        if (response.ok && STATIC_ASSETS.some(function(a) {
          return event.request.url.endsWith(a);
        })) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(function() {
        // Ağ yoksa cache'ten sun
        return caches.match(event.request).then(function(cached) {
          return cached || caches.match('/index.html');
        });
      })
  );
});
