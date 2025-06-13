// Просто кэшируем статику
self.addEventListener('install', (e) => {
    e.waitUntil(
      caches.open('pwa-v1').then(cache => cache.addAll([
        '/static/app.js',
        '/static/style.css'
      ]))
    );
  });