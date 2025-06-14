self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open("pwa-cache").then((cache) =>
      cache.addAll(["/calculator", "/static/calculator/index.html"])
    )
  );
});

self.addEventListener("fetch", (e) => {
  e.respondWith(
    caches.match(e.request).then((r) => r || fetch(e.request))
  );
});
