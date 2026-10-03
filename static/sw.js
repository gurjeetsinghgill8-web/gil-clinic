/* GIL CLINIC service worker — app shell only, NEVER clinical data.
 *
 * Why this file is careful rather than a standard "cache everything" SW
 * ---------------------------------------------------------------------
 * A clinic tablet is shared. A doctor logs in, sees today's queue, hands the
 * tablet to the receptionist, and logs out. If this service worker had cached
 * the queue API response, the next person to open the app would be shown the
 * PREVIOUS doctor's patient list — offline, from the cache, with no server
 * request to correct it and nothing on screen to suggest it was stale.
 *
 * That is not a performance bug. It is a data leak, on a shared device, in a
 * clinic. So the rule here is absolute:
 *
 *   CACHE THE SHELL (HTML, icons, fonts) — NEVER THE RECORD (any JSON, any
 *   authenticated page, anything under /track, /my, /card, /admin, /opd/api,
 *   /api).
 *
 * Every clinical or authenticated request goes to the network, always, and a
 * failure is reported honestly as "you are offline" rather than papered over
 * with a cached answer.
 */

const VERSION = 'ghos-v1';
const SHELL_CACHE = `${VERSION}-shell`;

/* Static assets safe to serve from cache: they contain no patient data and they
 * are what makes the app open instantly on a clinic's flaky connection. */
const SHELL_ASSETS = [
  '/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon-32.png',
];

/* Anything matching these is NEVER cached and NEVER served from cache.
 *
 * Written as path prefixes rather than one big regex so the intent is readable
 * and a new private route is obvious to add. */
const NEVER_CACHE_PREFIXES = [
  '/api/',          // every public JSON API
  '/opd/api/',      // queue engine, slots, referrals, stats
  '/admin/',        // super-admin panel
  '/track/',        // patient tracking (PHI: a token IS the record)
  '/my/',           // patient portal
  '/card/',         // universal health card + its FHIR export
  '/r/',            // referral slip (contains patient details)
  '/opd/',          // the whole OPD dashboard is authenticated
  '/experience/',   // patient dashboard is authenticated
  '/login',
  '/portal',
];

function isPrivate(url) {
  const path = url.pathname;
  if (url.origin !== self.location.origin) return true;
  return NEVER_CACHE_PREFIXES.some((prefix) => path.startsWith(prefix));
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // Individually, so one missing icon cannot fail the whole install.
      await Promise.all(
        SHELL_ASSETS.map((asset) =>
          cache.add(asset).catch(() => {
            /* an icon we could not fetch is not a reason to refuse to install */
          })
        )
      );
      // Take over as soon as possible, so a doctor who just installed the app
      // does not need a second reload for offline to start working.
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Drop caches from older versions — an old cache could hold a stale
      // route list that no longer matches NEVER_CACHE_PREFIXES.
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((key) => !key.startsWith(VERSION)).map((key) => caches.delete(key))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only GETs are cacheable at all; never touch a mutation.
  if (request.method !== 'GET') return;

  let url;
  try {
    url = new URL(request.url);
  } catch (e) {
    return;
  }

  // ── Rule 1: private or cross-origin → straight to the network ──
  if (isPrivate(url)) return;

  // ── Rule 2: shell assets → cache first (they never change mid-version) ──
  if (SHELL_ASSETS.some((asset) => url.pathname === asset)) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        try {
          const response = await fetch(request);
          if (response && response.ok) {
            const cache = await caches.open(SHELL_CACHE);
            cache.put(request, response.clone());
          }
          return response;
        } catch (e) {
          return new Response('', { status: 504, statusText: 'offline' });
        }
      })()
    );
    return;
  }

  // ── Rule 3: public HTML pages → network first, cache the shell as a fallback ──
  // The landing page and the marketplace are public and useful offline, but a
  // cached copy must never win over a live one: live availability is the whole
  // point of the marketplace.
  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request);
          if (response && response.ok) {
            const cache = await caches.open(SHELL_CACHE);
            cache.put(request, response.clone());
          }
          return response;
        } catch (e) {
          const cached = await caches.match(request);
          if (cached) return cached;
          const home = await caches.match('/');
          if (home) return home;
          return new Response(
            '<!doctype html><meta charset="utf-8"><title>Offline</title>' +
              '<body style="font-family:system-ui;padding:40px;text-align:center;">' +
              '<h1 style="font-size:20px;">📶 Internet nahi hai</h1>' +
              '<p style="color:#64748b;">Queue aur patient data live server se aata hai — ' +
              'offline me purana data dikhana galat hoga. Connection aane par dobara kholein.</p></body>',
            { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        }
      })()
    );
    return;
  }

  // ── Everything else: leave it to the browser ──
});

/* Let the page ask which version is running (useful when debugging "why is my
 * app stale?" — the honest answer must not require a cache-buster guess). */
self.addEventListener('message', (event) => {
  if (event.data === 'version') {
    event.source &&
      event.source.postMessage({ type: 'version', version: VERSION });
  }
});
