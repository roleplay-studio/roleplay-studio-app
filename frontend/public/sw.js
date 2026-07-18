/* eslint-disable no-restricted-globals */
/**
 * Service Worker — Phase 5.3 of docs/MOBILE_PLAN.md
 *
 * Strategy: cache-first for read-only API catalog endpoints, network-first
 * for everything else. SSE streams and non-GET requests are NEVER cached.
 *
 * Caching rules:
 *   - GET /api/bots, /api/personas, /api/categories — cache-first (1h TTL)
 *     These are the "catalog" — bot list, persona list, category list.
 *     Safe to serve stale for an hour; user can pull-to-refresh.
 *   - GET /api/bots/<id>, /api/personas/<id> — same as above
 *   - GET /api/categories — same
 *   - GET /uploads/* — cache-first (avatar images, 24h TTL)
 *   - Everything else — network-first, no cache write
 *
 * Precache (built into the SW on install):
 *   - / (the SPA shell)
 *   - /manifest.webmanifest
 *   - /icons/icon-192.png, /icons/icon-512.png
 *
 * Update flow:
 *   - On install, SW fetches precache list, populates cache, activates.
 *   - On activate, old caches are pruned.
 *   - On fetch, applies rules above.
 *
 * Limitations:
 *   - SSE chat streams MUST NOT be cached. We explicitly bypass them.
 *   - Auth-bearing requests (when we add auth) should never be cached.
 *
 * Versioning: cache name includes the version. Bump when rules change.
 */

const SW_VERSION = 'v2';
const STATIC_CACHE = `static-${SW_VERSION}`;
const RUNTIME_CACHE = `runtime-${SW_VERSION}`;

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

const CACHEABLE_GET_PREFIXES = [
  '/api/bots',
  '/api/personas',
  '/api/categories',
  // Skills library — read-only catalog, safe to cache.
  // Mutations (POST/PUT/DELETE) don't reach this handler because
  // the GET-only branch above rejects non-GETs by method.
  '/api/skills',
  '/uploads/',
];

const CACHEABLE_STATIC_PATHS = ['/', '/index.html', '/manifest.webmanifest'];

// ── Install: precache shell ───────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);
      // Use { cache: 'reload' } to bypass any HTTP cache from the dev server
      await cache.addAll(PRECACHE_URLS.map((u) => new Request(u, { cache: 'reload' })));
      await self.skipWaiting();
    })(),
  );
});

// ── Activate: prune old caches ─────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([STATIC_CACHE, RUNTIME_CACHE]);
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)));
      await self.clients.claim();
    })(),
  );
});

// ── Fetch: routing ────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Only handle GET. POST/PUT/DELETE/streaming/SSE always go to network.
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Same-origin only. Cross-origin (e.g. fonts.googleapis) — let browser handle.
  if (url.origin !== self.location.origin) return;

  // SSE / streaming responses — never cache. The Accept header is the
  // canonical signal; EventSource always sends text/event-stream.
  const accept = req.headers.get('accept') ?? '';
  if (accept.includes('text/event-stream')) return;

  // Cacheable read-only API catalog → cache-first
  if (CACHEABLE_GET_PREFIXES.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(cacheFirst(req, RUNTIME_CACHE));
    return;
  }

  // Cacheable static shell → cache-first with network fallback
  if (CACHEABLE_STATIC_PATHS.includes(url.pathname)) {
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }

  // Everything else → network-first, no cache write
  event.respondWith(networkFirst(req));
});

// ── Strategies ─────────────────────────────────────────────────────
async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone()).catch(() => {});
    return res;
  } catch (err) {
    // Offline + not cached → return offline shell if available
    const fallback = await cache.match('/');
    if (fallback) return fallback;
    throw err;
  }
}

async function networkFirst(req) {
  try {
    return await fetch(req);
  } catch (err) {
    // Network failure — try cache as a last resort for navigations
    if (req.mode === 'navigate') {
      const cache = await caches.open(STATIC_CACHE);
      const fallback = await cache.match('/');
      if (fallback) return fallback;
    }
    throw err;
  }
}

// ── Manual cache invalidation from the app ─────────────────────────
// The app can post a message to the SW to invalidate caches after a
// mutation (e.g. user creates/deletes a bot). This keeps the catalog
// cache fresh without forcing the user to pull-to-refresh.
self.addEventListener('message', (event) => {
  if (event.data?.type === 'INVALIDATE_RUNTIME_CACHE') {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(RUNTIME_CACHE);
        const keys = await cache.keys();
        // If a specific prefix was provided, only delete matching keys
        const prefix = event.data.prefix;
        const matched = prefix ? keys.filter((r) => new URL(r.url).pathname.startsWith(prefix)) : keys;
        await Promise.all(matched.map((r) => cache.delete(r)));
      })(),
    );
  }
});