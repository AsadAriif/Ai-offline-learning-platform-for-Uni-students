// BGNU AI Learning Platform - Offline Service Worker
const CACHE_NAME = 'bgnu-ai-cache-v1';
const OFFLINE_URLS = [
  '/',
  '/static/MyApp/styles.css',
  '/static/MyApp/sidebar.js',
  '/static/MyApp/department_logo.png',
  '/static/MyApp/uni_logo.png',
  '/static/MyApp/fonts/manrope-600.woff2',
  '/static/MyApp/fonts/manrope-700.woff2',
  '/static/MyApp/fonts/inter-400.woff2',
  '/static/MyApp/fonts/inter-500.woff2',
  '/static/MyApp/fonts/ibmplexmono-500.woff2'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(OFFLINE_URLS).catch((err) => {
        console.warn('Some offline assets failed to precache:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(() => {
        // Fallback to app shell only for top-level page navigations
        if (event.request.mode === 'navigate') {
          return caches.match('/').then((home) => home || new Response('Offline', { status: 503, statusText: 'Offline' }));
        }
        return new Response('', { status: 503, statusText: 'Service Unavailable' });
      });
    })
  );
});

