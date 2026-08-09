# -*- coding: utf-8 -*-
"""
ARAM: Mayhem 出装助手 - 本地服务器（仅标准库）。

启动后访问 http://localhost:8765
  /                       页面
  /api/champions          英雄列表（带缓存）
  /api/champion/<slug>    指定英雄的 ARAM Mayhem 数据（带缓存）
  /api/champion/<slug>?refresh=1   强制重新抓取
"""

import io
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import opgg_mayhem_scraper as scraper

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
CHAMPIONS_TTL = 86400  # 24 小时
CHAMPION_TTL = 1800  # 30 分钟

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def now():
    return time.time()


def cache_load(name, ttl):
    path = os.path.join(CACHE_DIR, name)
    if not os.path.isfile(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        if now() - rec.get("fetched_at", 0) > ttl:
            return None
        return rec.get("data")
    except Exception:
        return None


def cache_save(name, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    rec = {"fetched_at": now(), "data": data}
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "OPGGMayhem/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _static(self, path):
        rel = path.lstrip("/")
        if not rel or rel.endswith("/"):
            rel = "index.html"
        full = os.path.normpath(os.path.join(HERE, rel))
        if not full.startswith(HERE) or not os.path.isfile(full):
            self._send(404, "Not Found", "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(full)[1].lower()
        with io.open(full, "rb") as f:
            self._send(200, f.read(), MIME.get(ext, "application/octet-stream"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/api/champions":
                data = cache_load("champions.json", CHAMPIONS_TTL)
                if data is None:
                    data = scraper.get_champions()
                    cache_save("champions.json", data)
                self._json(200, {"ok": True, "data": data})
            elif path.startswith("/api/champion/"):
                slug = urllib.parse.unquote(path[len("/api/champion/") :]).strip().lower()
                if not slug or "/" in slug or "\\" in slug:
                    self._json(400, {"ok": False, "error": "bad slug"})
                    return
                refresh = "refresh" in query
                data = None if refresh else cache_load(f"{slug}.json", CHAMPION_TTL)
                if data is None:
                    try:
                        data = scraper.get_champion_data(slug)
                    except Exception as exc:
                        self._json(502, {"ok": False, "error": str(exc)})
                        return
                    cache_save(f"{slug}.json", data)
                # 附带英雄名称/图标信息
                champs = cache_load("champions.json", CHAMPIONS_TTL)
                if champs is None:
                    try:
                        champs = scraper.get_champions()
                        cache_save("champions.json", champs)
                    except Exception:
                        champs = []
                data["champion"] = next((c for c in champs if c["key"] == slug), None)
                self._json(200, {"ok": True, "data": data})
            elif path.startswith("/api/"):
                self._json(404, {"ok": False, "error": "not found"})
            else:
                self._static(path)
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc)})


def main():
    port = 8765
    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv[1:]):
            port = int(sys.argv[i + 2])
    os.makedirs(CACHE_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("=" * 52)
    print("  ARAM: Mayhem 出装助手 已启动")
    print(f"  请在浏览器打开:  http://localhost:{port}")
    print("  按 Ctrl+C 停止")
    print("=" * 52)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
