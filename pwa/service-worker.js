/**
 * CardioQueue PWA — Service Worker
 * Caches app shell for offline use + enables Add to Home Screen.
 */
const CACHE_NAME = "cardioqueue-v1";
const APP_SHELL = [
  "/pwa/index.html",
  "/pwa/css/style.css",
  "/pwa/js/db.js",
  "/pwa/js/app.js",
  "/pwa/js/reception.js",
  "/pwa/js/technician.js",
  "/pwa/js/doctor.js",
  "/pwa/js/patient.js",
  "/pwa/js/qr.js",
  "/pwa/js/export.js",
  "/pwa/lib/qrcode.min.js",
  "/pwa/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return res;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || new Response("Offline", { status: 503 })))
  );
});
