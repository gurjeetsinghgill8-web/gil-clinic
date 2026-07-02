/**
 * CardioQueue PWA — Service Worker
 * Caches app shell for offline use + enables Add to Home Screen.
 * Supports push notifications + vibration alerts for mobile.
 */
const CACHE_NAME = "cardioqueue-v2";
const APP_SHELL = [
  "./index.html",
  "./css/style.css",
  "./js/db.js",
  "./js/app.js",
  "./js/reception.js",
  "./js/technician.js",
  "./js/doctor.js",
  "./js/qr.js",
  "./js/export.js",
  "./lib/qrcode.min.js",
  "./manifest.json"
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

// ─── Push Notification Handling ─────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let data = { title: "CardioQueue", body: "Update from clinic", tag: "cardioqueue" };
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: "./img/hospital.png",
    badge: "./img/hospital.png",
    vibrate: [500, 200, 500],
    tag: data.tag || "cardioqueue",
    requireInteraction: true,
    silent: false,
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click — open the app
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(self.location.origin)
  );
});
