// Caro309 Service Worker — cache static assets + network-first for API
const CACHE_VERSION = 'caro309-v1';
const CACHE_FILES = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
];

// Install: cache static files
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      return cache.addAll(CACHE_FILES).catch(() => {
        // Một số file có thể chưa có — bỏ qua lỗi
      });
    })
  );
  self.skipWaiting();
});

// Activate: xóa cache cũ
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

// Fetch strategy:
// - API calls (onrender.com) → network-only (không cache)
// - WebSocket → passthrough
// - Static files → cache-first, fallback to network
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // API calls → network only
  if (url.hostname.includes('onrender.com') || url.protocol === 'ws:' || url.protocol === 'wss:') {
    return;
  }

  // Google Fonts → cache-first
  if (url.hostname.includes('fonts.googleapis.com') || url.hostname.includes('fonts.gstatic.com')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request).then((res) => {
          const clone = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(event.request, clone));
          return res;
        });
      })
    );
    return;
  }

  // Static files → cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        // Chỉ cache nếu response OK
        if (res && res.status === 200 && res.type === 'basic') {
          const clone = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(event.request, clone));
        }
        return res;
      }).catch(() => {
        // Offline fallback
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html');
        }
      });
    })
  );
});
