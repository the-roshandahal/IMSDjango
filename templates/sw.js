{% load static %}// Cleantech1 IMS service worker.
// Rendered by Django (see apps/core/web_views.py) so the static asset URLs
// below always match whatever whitenoise's manifest storage produced --
// no manual "bump the cache name every deploy" step needed for those.
// The cache name still carries today's date so old runtime-cached entries
// (e.g. yesterday's hashed static filenames) get swept on the next visit.
const CACHE_NAME = "ims-{% now 'Y-m-d' %}";
const OFFLINE_URL = "{% url 'core_web:offline' %}";

const PRECACHE_URLS = [
  OFFLINE_URL,
  "{% static 'css/app.css' %}",
  "{% static 'img/logo-mark.jpg' %}",
  "{% static 'img/favicon.ico' %}",
  "{% static 'img/icons/icon-192.png' %}",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // App pages: always prefer a live network response (this is a dynamic,
  // per-user app, not something to serve stale), and only fall back to a
  // cached copy or the offline page when there's no connection at all.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Static assets are content-hashed in production, so a cache-first
  // strategy is safe -- a changed file gets a new URL automatically.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        });
      })
    );
  }
});
