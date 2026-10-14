"use strict";

const CACHE_PREFIX = "ai-assistant-shell-";
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const SHELL_ASSETS = [
  "/",
  "/static/vendor/bootstrap.min.css",
  "/static/assistant/css/app.css",
  "/static/assistant/js/app.js",
  "/static/assistant/img/icon.svg",
  "/static/assistant/img/icon-192.png",
  "/static/assistant/img/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(SHELL_ASSETS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // The worker must never see or store AI prompts, responses, or CSRF tokens.
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try { return await fetch(request); }
      catch {
        const cache = await caches.open(CACHE_NAME);
        return await cache.match("/");
      }
    })());
    return;
  }
  if (SHELL_ASSETS.includes(url.pathname) && url.pathname !== "/") {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      return await cache.match(request) || fetch(request);
    })());
  }
});
