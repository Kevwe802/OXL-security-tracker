self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('family-tracker-v1').then(cache => {
      return cache.addAll([
        '/',
        '/static/location_sender.html',
        '/static/dashboard.html',
        '/static/manifest.json',
        '/static/sw.js',
        '/static/icon.png',
        '/static/icon-512.png',
        '/static/logo.png'
      ]);
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

self.addEventListener('sync', event => {
  if (event.tag === 'sync-location') {
    if (navigator.onLine) {
      self.clients.matchAll().then(clients => {
        clients.forEach(client => client.postMessage({ type: 'sync' }));
      });
    }
  }
});