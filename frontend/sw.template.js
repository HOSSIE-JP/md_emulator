// sw.js はこのテンプレートから自動生成されます。直接編集しないでください。
// 生成コマンド: WASM ビルドタスク (tasks.json) または CI ワークフロー
// バージョンプレースホルダー: __BUILD_VERSION__
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
  console.log("[SW] インストール: バージョン __BUILD_VERSION__");
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.log("[SW] アクティベート: バージョン __BUILD_VERSION__");
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

  const url = new URL(request.url);

  // Critical assets (.wasm, .js, sw.js): always bypass cache
  const isCritical = url.pathname.endsWith(".wasm")
    || url.pathname.endsWith(".js")
    || url.pathname.endsWith(".html");

  if (isCritical) {
    event.respondWith(
      fetch(request, { cache: "no-cache" })
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
    return;
  }

  // Other assets (icons, manifests, ROMs): network-first with cache fallback
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
