/**
 * CardioQueue Service Worker — PWA Offline + Push Notifications
 * 
 * Provides:
 *   1. Offline cache (app shell + static assets)
 *   2. Background status polling for notifications even when tab is closed
 *   3. Push event handler for displaying notifications
 *   4. Notification click handler to open patient status page
 */

const CACHE_NAME = "cardioqueue-v2";
const APP_SHELL = [
  "/",
  "/?source=pwa",
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
  // Claim all clients so SW controls all pages immediately
  self.clients.claim();
});

// ─── Fetch: Network-first, cache fallback ────────────────────────────────────
self.addEventListener("fetch", (event) => {
  // Only handle GET requests
  if (event.request.method !== "GET") return;

  // Skip non-http(s) URLs (e.g., chrome-extension, data:, blob:)
  const url = new URL(event.request.url);
  if (!url.protocol.startsWith("http")) return;

  // Network-first strategy for reliability
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache successful responses
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, clone);
        });
        return response;
      })
      .catch(() => {
        // Fall back to cache when offline
        return caches.match(event.request).then((cached) => {
          return cached || new Response("Offline", { status: 503 });
        });
      })
  );
});

// ─── Message Handler: Track patient for background notifications ────────────
// When a patient opens their status page, it sends a message to this SW
// with their patient_id. The SW then polls for status changes periodically.

let trackedPatientId = null;
let trackedPatientName = "";
let lastStatusHash = "";
let pollingInterval = null;

self.addEventListener("message", (event) => {
  const data = event.data;

  if (data && data.type === "TRACK_PATIENT") {
    // Start tracking a patient for background notifications
    trackedPatientId = data.patientId;
    trackedPatientName = data.patientName || "Patient";
    lastStatusHash = data.statusHash || "";

    console.log("[SW] Now tracking patient:", trackedPatientId);

    // Start polling every 30 seconds
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(pollStatus, 30000);
  }

  if (data && data.type === "UNTRACK_PATIENT") {
    // Stop tracking
    trackedPatientId = null;
    trackedPatientName = "";
    lastStatusHash = "";
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
    console.log("[SW] Stopped tracking patient");
  }

  if (data && data.type === "UPDATE_STATUS_HASH") {
    lastStatusHash = data.statusHash || "";
  }
});

// ─── Poll Status: Fetch patient status from the server ───────────────────────
async function pollStatus() {
  if (!trackedPatientId) return;

  try {
    // Fetch the status page and extract the status hash
    const response = await fetch(`/?patient=${trackedPatientId}&sw_check=1`, {
      method: "GET",
      headers: { "Cache-Control": "no-cache" },
    });

    if (!response.ok) return;

    const text = await response.text();

    // Look for the status-hash div that Patient_Status.py renders
    const hashMatch = text.match(
      /<div id="status-hash" data-hash="([^"]+)" data-status="([^"]+)"/
    );

    if (hashMatch) {
      const currentHash = hashMatch[1];
      const currentStatus = hashMatch[2];

      if (lastStatusHash && currentHash !== lastStatusHash) {
        // Status changed! Show notification
        showStatusNotification(currentStatus, currentHash);
      }

      lastStatusHash = currentHash;
    }
  } catch (err) {
    // Silently fail — network might be unavailable
    console.log("[SW] Poll error:", err);
  }
}

// ─── Show Notification from background poll ──────────────────────────────────
function showStatusNotification(status, hash) {
  const title = "🔄 Status Updated";
  const body = `${trackedPatientName}, your status changed to: ${status}`;

  self.registration.showNotification(title, {
    body: body,
    icon: "https://img.icons8.com/color/48/hospital.png",
    badge: "https://img.icons8.com/color/48/hospital.png",
    tag: `cq-status-${trackedPatientId}-${hash}`,
    requireInteraction: true,
    vibrate: [200, 100, 200, 100, 400],
    data: {
      patientId: trackedPatientId,
      status: status,
      url: `/?patient=${trackedPatientId}`,
    },
  });
}

// ─── Push Event: Handle server-pushed notifications (for future use) ─────────
self.addEventListener("push", (event) => {
  let data = { title: "CardioQueue", body: "Updates available", url: "/" };

  if (event.data) {
    try {
      data = JSON.parse(event.data.text());
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: "https://img.icons8.com/color/48/hospital.png",
    badge: "https://img.icons8.com/color/48/hospital.png",
    tag: "cq-push-" + Date.now(),
    requireInteraction: true,
    vibrate: [200, 100, 200],
    data: {
      url: data.url || "/",
    },
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// ─── Notification Click: Open patient status page ───────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || "/";

  // Try to focus an existing window, or open a new one
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        // Check if there's already a window with this URL
        for (const client of windowClients) {
          if (client.url.includes(targetUrl.split("?")[0])) {
            return client.focus();
          }
        }
        // Open new window
        return clients.openWindow(targetUrl);
      })
  );
});
