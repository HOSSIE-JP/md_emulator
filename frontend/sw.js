const CACHE_NAME = "md-wasm-pwa-__BUILD_VERSION__";
const APP_SHELL = [
  "./",
  "./index.html",
  "./wasm.html",
  "./wasm-player.js",
  "./manifest.webmanifest",
  "./icons/app-icon.svg",
  "./pkg/md_wasm.js",
  "./pkg/md_wasm_bg.wasm",
  "./pkg/md_wasm.d.ts",
  "./pkg/md_wasm_bg.wasm.d.ts",
  "./roms/index.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  // Network-first: always try fresh content, fall back to cache offline
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.status === 200 && response.type === "basic") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, clone).catch(() => {});
          });
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
