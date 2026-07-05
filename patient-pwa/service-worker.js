/**
 * CardioQueue Patient PWA — Service Worker
 * ==========================================
 * Provides offline caching, push notifications, and background status polling.
 */
const CACHE_NAME = "cardioqueue-patient-v1";
const APP_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL);
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Network-first, cache fallback
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (!url.protocol.startsWith("http")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, clone);
        });
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          return cached || new Response("Offline", { status: 503 });
        });
      })
  );
});

// Background polling for patient status
let trackedMobile = null;
let lastStatusHash = "";
let pollingInterval = null;

self.addEventListener("message", (event) => {
  const data = event.data;
  if (data && data.type === "TRACK_PATIENT") {
    trackedMobile = data.mobile;
    lastStatusHash = data.statusHash || "";
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(pollStatus, 30000);
  }
  if (data && data.type === "UNTRACK_PATIENT") {
    trackedMobile = null;
    lastStatusHash = "";
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }
  if (data && data.type === "UPDATE_STATUS_HASH") {
    lastStatusHash = data.statusHash || "";
  }
});

async function pollStatus() {
  if (!trackedMobile) return;
  try {
    const response = await fetch(`/?mobile=${trackedMobile}&sw_check=1`, {
      method: "GET",
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) return;
    const text = await response.text();
    const hashMatch = text.match(
      /<div id="status-hash" data-hash="([^"]+)" data-status="([^"]+)"/
    );
    if (hashMatch) {
      const currentHash = hashMatch[1];
      const currentStatus = hashMatch[2];
      if (lastStatusHash && currentHash !== lastStatusHash) {
        self.registration.showNotification("🔄 Status Updated", {
          body: `Your status changed to: ${currentStatus}`,
          icon: "https://img.icons8.com/color/48/hospital.png",
          badge: "https://img.icons8.com/color/48/hospital.png",
          tag: "cq-status-" + currentHash,
          requireInteraction: true,
          vibrate: [200, 100, 200, 100, 400],
          data: { mobile: trackedMobile, status: currentStatus },
        });
      }
      lastStatusHash = currentHash;
    }
  } catch (err) {
    // Silently fail
  }
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetMobile = event.notification.data?.mobile || "";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url.includes(self.location.origin)) {
          return client.focus();
        }
      }
      return clients.openWindow(self.location.origin);
    })
  );
});
