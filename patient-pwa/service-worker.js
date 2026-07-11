const CACHE_NAME = "cq-cache-v3";
const STATIC_ASSETS = ["/", "/assets/style.css", "/assets/manifest.json", "/assets/icon-192.png", "/assets/icon-512.png"];

self.addEventListener("install", (e) => { self.skipWaiting(); e.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(STATIC_ASSETS))); });

self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((k) => Promise.all(k.filter((x) => x !== CACHE_NAME).map((x) => caches.delete(x))))); self.clients.claim(); });

self.addEventListener("fetch", (e) => {
  if (e.request.url.includes("/api/") || e.request.method === "POST") {
    return e.respondWith(fetch(e.request).catch(() => new Response(JSON.stringify({ offline: true }), { status: 200, headers: { "Content-Type": "application/json" } })));
  }
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});

self.addEventListener("push", (e) => {
  const d = e.data ? e.data.json() : {};
  e.waitUntil(self.registration.showNotification(d.title || "CardioQueue", { body: d.body || "", icon: "/assets/icon-192.png", badge: "/assets/icon-192.png", vibrate: [200, 100, 200], data: { url: d.url || "/" } }));
});

self.addEventListener("notificationclick", (e) => { e.notification.close(); e.waitUntil(clients.openWindow(e.notification.data?.url || "/")); });

self.addEventListener("sync", (e) => { if (e.tag === "cq-sync") e.waitUntil(syncData()); });

async function syncData() {
  const cache = await caches.open("cq-offline-queue");
  const requests = await cache.keys();
  for (const req of requests) { try { const res = await fetch(req); if (res.ok) await cache.delete(req); } catch (e) {} }
}