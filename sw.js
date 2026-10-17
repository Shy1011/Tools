/* Tools 工具集 Service Worker —— 只缓存本站静态资源，不碰第三方接口 */
var VERSION = 'tools-v1';
var CORE = [
  './',
  './index.html',
  './calculator.html',
  './bit-to-hex-x6.html',
  './xy-plotter.html',
  './svg-to-pptx.html',
  './image-to-markdown.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon.ico'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(VERSION)
      .then(function (cache) { return cache.addAll(CORE); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

function put(req, res) {
  if (!res || !res.ok || res.type !== 'basic') return res;
  var copy = res.clone();
  caches.open(VERSION).then(function (cache) { cache.put(req, copy); }).catch(function () {});
  return res;
}

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;

  var url;
  try { url = new URL(req.url); } catch (e) { return; }
  if (url.origin !== self.location.origin) return;   // API / 外部资源交给浏览器

  // 页面导航：先用网络，断网时回退到缓存（再不行回首页）
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(function (res) { return put(req, res); })
        .catch(function () {
          return caches.match(req).then(function (hit) {
            return hit || caches.match('./index.html');
          });
        })
    );
    return;
  }

  // 静态资源：先给缓存，同时后台更新
  event.respondWith(
    caches.match(req).then(function (hit) {
      var network = fetch(req).then(function (res) { return put(req, res); }).catch(function () { return hit; });
      return hit || network;
    })
  );
});
