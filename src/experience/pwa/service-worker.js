/**
 * GIL CLINIC — Patient Experience Service Worker
 *
 * Provides:
 *   1. Offline cache (app shell + static assets)
 *   2. API response caching for offline viewing
 *   3. Notification click handler to open patient dashboard
 *   4. Push event handler for displaying notifications
 */

const CACHE_NAME = "gil-clinic-experience-v2";
const APP_SHELL = [
  "/experience/",
  "/experience/login",
  "/experience/dashboard",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

// API endpoints to cache on fetch for offline access
const API_CACHE_PATTERNS = [
  "/api/v1/experience/my-status",
  "/api/v1/experience/me",
  "/api/v1/experience/token-slip/json",
];

// ─── Install: Cache app shell ────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL);
    })
  );
});

// ─── Activate: Clean old caches ──────────────────────────────────────────────
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

// ─── Helper: should cache this API response? ────────────────────────────────
function isApiCacheable(url) {
  return API_CACHE_PATTERNS.some((pattern) => url.includes(pattern));
}

// ─── Fetch: Network first, cache fallback ────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = event.request.url;

  // For API endpoints that should be available offline, use cache-first strategy
  if (isApiCacheable(url) && event.request.method === "GET") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            if (cached) {
              return cached;
            }
            // For the main status endpoint, return a meaningful offline response
            if (url.includes("/my-status")) {
              return new Response(
                JSON.stringify({
                  patient: null,
                  visit: {},
                  tests: [],
                  hospital: { name: "Offline" },
                  timestamp: new Date().toISOString(),
                  _offline: true,
                }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                }
              );
            }
            return new Response("Offline", { status: 503 });
          });
        })
    );
    return;
  }

  // For app shell pages and static assets, use network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then((cached) => {
          return cached || new Response("Offline", { status: 503 });
        });
      })
  );
});

// ─── Push: Show notification ─────────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let data = {
    title: "GIL CLINIC",
    body: "Your status has been updated.",
    icon: "/static/icons/icon-192.png",
  };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon,
      badge: data.icon,
      tag: "patient-status",
      renotify: true,
      vibrate: [200, 100, 200],
      data: data.url ? { url: data.url } : {},
    })
  );
});

// ─── Notification Click: Open dashboard ──────────────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/experience/dashboard";
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url.includes("/experience/") && "focus" in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});
