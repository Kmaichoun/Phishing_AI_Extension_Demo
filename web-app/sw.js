const CACHE_NAME = 'phish-radar-web-v20';
const ASSETS = ['./', './login.html', './fonts.css?v=20', './auth.css?v=17', './dockit-theme.css?v=17', './professional-ui.css?v=20', './runtime-config.js?v=16', './theme.js?v=17', './auth.js?v=17', './index.html', './styles.css?v=17', './app.js?v=17', './motion.js?v=17', './awwwards-motion.js?v=20', './vendor/gsap.min.js?v=3.13.0', './vendor/ScrollTrigger.min.js?v=3.13.0', './analyzer.js?v=17', './settings.html', './settings.css?v=17', './settings.js?v=17', './manifest.webmanifest', './assets/icon128.png?v=18', './assets/fonts/outfit-latin-400-700.woff2', './assets/fonts/ibm-plex-sans-thai-400.woff2', './assets/fonts/ibm-plex-sans-thai-500.woff2', './assets/fonts/ibm-plex-sans-thai-600.woff2', './assets/fonts/ibm-plex-sans-thai-700.woff2', './assets/fonts/noto-serif-thai-500-600.woff2'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.hostname === '127.0.0.1' && url.port === '8765') return;
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
