// NightCal Service Worker (PWA)
const CACHE_NAME = "nightcal-shell-v2";
const PRECACHE_ASSETS = [
  "/",
  "/today",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
  "/css/nightcal.css",
  "/data/sample-model.json"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(PRECACHE_ASSETS).catch(err => {
        console.warn("[sw] Pre-cache non-fatal error:", err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip non-GET requests and cross-origin calls
  if (req.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  // Skip Matrix chat sync and write APIs
  if (url.pathname.startsWith("/_matrix") || url.pathname.startsWith("/api/chat")) {
    return;
  }

  // Network-first for dynamic navigation and API model
  if (req.mode === "navigate" || url.pathname === "/api/model") {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(req);
          if (cached) return cached;
          if (req.mode === "navigate") {
            return (await caches.match("/today")) || (await caches.match("/"));
          }
          if (url.pathname === "/api/model") {
            return await caches.match("/data/sample-model.json");
          }
          throw new Error("Offline and un-cached");
        })
    );
    return;
  }

  // Stale-While-Revalidate for static assets (css, js, images, icons)
  event.respondWith(
    caches.match(req).then(cached => {
      const fetchPromise = fetch(req).then(networkRes => {
        if (networkRes && networkRes.status === 200) {
          const clone = networkRes.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
        }
        return networkRes;
      }).catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
