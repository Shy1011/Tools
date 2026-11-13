#!/usr/bin/env python3
"""Local HTTP bridge for the XY Plotter browser agent API."""

from __future__ import annotations

import argparse
import collections
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


API_VERSION = "1.0.0"
DEFAULT_PAGE_URL = "https://shy1011.github.io/Tools/xy-plotter.html"
MAX_BODY_BYTES = 64 * 1024 * 1024
RESULT_TTL_SECONDS = 600


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def structured_error(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "ok": False,
        "result": None,
        "warnings": [],
        "error": {"code": code, "message": message, "details": details},
    }


class BridgeState:
    def __init__(
        self,
        token: str,
        actions: set[str],
        catalog: dict[str, Any],
        artifact_dir: Path,
    ) -> None:
        self.token = token
        self.actions = actions
        self.catalog = catalog
        self.artifact_dir = artifact_dir
        self.condition = threading.Condition()
        self.commands: collections.deque[dict[str, Any]] = collections.deque()
        self.results: collections.OrderedDict[str, dict[str, Any]] = collections.OrderedDict()
        self.request_ids: dict[str, str] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.started_at = time.time()

    def auth_ok(self, token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(token, self.token)

    def register_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("sessionId") or "").strip()
        if not session_id:
            raise ValueError("sessionId is required")
        with self.condition:
            now = time.time()
            self.sessions[session_id] = {
                "sessionId": session_id,
                "userAgent": str(payload.get("userAgent") or "")[:500],
                "apiVersion": str(payload.get("apiVersion") or "")[:50],
                "capabilities": int(payload.get("capabilities") or 0),
                "lastSeen": now,
            }
            self.condition.notify_all()
        return {"ok": True, "sessionId": session_id, "connected": True}

    def enqueue(
        self,
        action: str,
        params: dict[str, Any],
        request_id: str | None,
        session_id: str | None,
    ) -> tuple[str, bool]:
        now = time.time()
        with self.condition:
            self._cleanup_results(now)
            if request_id and request_id in self.request_ids:
                return self.request_ids[request_id], True
            command_id = uuid.uuid4().hex
            if request_id:
                self.request_ids[request_id] = command_id
            self.commands.append(
                {
                    "id": command_id,
                    "requestId": request_id,
                    "action": action,
                    "params": params,
                    "targetSessionId": session_id,
                    "createdAt": now,
                    "state": "queued",
                }
            )
            self.condition.notify_all()
            return command_id, False

    def wait_for_result(self, command_id: str, timeout: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while command_id not in self.results:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._remove_queued(command_id)
                    return None
                self.condition.wait(remaining)
            wrapped = self.results[command_id]
            return wrapped.get("result")

    def take_next(self, session_id: str, wait_ms: int) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(1.0, min(wait_ms, 30000) / 1000.0)
        with self.condition:
            while True:
                if session_id in self.sessions:
                    self.sessions[session_id]["lastSeen"] = time.time()
                for command in list(self.commands):
                    target = command.get("targetSessionId")
                    if command.get("state") == "queued" and target in (None, "", session_id):
                        command["state"] = "running"
                        command["startedAt"] = time.time()
                        self.commands.remove(command)
                        return command
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.condition.wait(min(remaining, 1.0))

    def submit_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        command_id = str(payload.get("id") or "").strip()
        session_id = str(payload.get("sessionId") or "").strip()
        if not command_id:
            raise ValueError("id is required")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("result must be an object")
        with self.condition:
            self.results[command_id] = {
                "completedAt": time.time(),
                "sessionId": session_id,
                "result": result,
            }
            self.condition.notify_all()
        return {"ok": True, "id": command_id, "received": True}

    def status(self) -> dict[str, Any]:
        now = time.time()
        with self.condition:
            active_cutoff = now - 35
            sessions = [
                {**item, "active": item.get("lastSeen", 0) >= active_cutoff}
                for item in self.sessions.values()
            ]
            sessions.sort(key=lambda item: item.get("lastSeen", 0), reverse=True)
            return {
                "ok": True,
                "apiVersion": API_VERSION,
                "uptimeSeconds": round(now - self.started_at, 1),
                "browserConnected": any(item["active"] for item in sessions),
                "sessions": sessions,
                "queuedCommands": len(self.commands),
                "actionCount": len(self.actions),
            }

    def artifact_path(self, filename: str) -> Path:
        raw = Path(str(filename or "artifact.bin")).name
        raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw).strip().rstrip(".")
        if not raw:
            raw = "artifact.bin"
        if len(raw) > 180:
            stem = Path(raw).stem[:140]
            raw = stem + Path(raw).suffix[:20]
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        candidate = (self.artifact_dir / raw).resolve()
        root = self.artifact_dir.resolve()
        if root != candidate.parent:
            raise ValueError("invalid artifact path")
        if candidate.exists():
            stem, suffix = candidate.stem, candidate.suffix
            for index in range(2, 10000):
                alternate = candidate.with_name(f"{stem} ({index}){suffix}")
                if not alternate.exists():
                    return alternate
        return candidate

    def _remove_queued(self, command_id: str) -> None:
        for command in list(self.commands):
            if command.get("id") == command_id:
                self.commands.remove(command)
                break

    def _cleanup_results(self, now: float) -> None:
        expired_ids = []
        for command_id, item in self.results.items():
            if now - float(item.get("completedAt", 0)) > RESULT_TTL_SECONDS:
                expired_ids.append(command_id)
            else:
                break
        for command_id in expired_ids:
            self.results.pop(command_id, None)
        if expired_ids:
            stale_ids = set(expired_ids)
            self.request_ids = {
                request_id: command_id
                for request_id, command_id in self.request_ids.items()
                if command_id not in stale_ids
            }


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: BridgeState) -> None:
        super().__init__(address, BridgeHandler)
        self.state = state


class BridgeHandler(BaseHTTPRequestHandler):
    server: BridgeServer
    server_version = "XYPlotterBridge/" + API_VERSION

    def log_message(self, fmt: str, *args: Any) -> None:
        message = fmt % args
        if "?token=" in message:
            message = message.split("?token=", 1)[0]
        sys.stderr.write("[xy-plotter-bridge] " + message + "\n")

    def _origin_allowed(self, origin: str) -> bool:
        if not origin:
            return True
        if origin == "https://shy1011.github.io":
            return True
        parsed = urlparse(origin)
        return parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost")

    def _cors_headers(self) -> dict[str, str]:
        origin = self.headers.get("Origin", "")
        headers = {
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Agent-Token",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
            "Access-Control-Allow-Private-Network": "true",
        }
        if origin and self._origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
        return headers

    def _send_json(
        self,
        status: int,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for key, value in self._cors_headers().items():
            self.send_header(key, value)
        self.end_headers()

    def _authorized(self) -> bool:
        if not self._origin_allowed(self.headers.get("Origin", "")):
            self._send_json(HTTPStatus.FORBIDDEN, structured_error("ORIGIN_FORBIDDEN", "Origin is not allowed"))
            return False
        if not self.server.state.auth_ok(self.headers.get("X-Agent-Token")):
            self._send_json(HTTPStatus.UNAUTHORIZED, structured_error("BRIDGE_AUTH_FAILED", "Invalid bridge token"))
            return False
        return True

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large")
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> dict[str, Any]:
        raw = self._read_body()
        try:
            value = json.loads(raw.decode("utf-8") if raw else "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON: " + str(exc)) from exc
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not self._origin_allowed(origin):
            self._send_empty(HTTPStatus.FORBIDDEN)
            return
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "xy-plotter-bridge",
                    "apiVersion": API_VERSION,
                },
            )
            return
        if not self._authorized():
            return
        if parsed.path == "/v1/status":
            self._send_json(HTTPStatus.OK, self.server.state.status())
            return
        if parsed.path == "/v1/capabilities":
            self._send_json(
                HTTPStatus.OK,
                {
                    **self.server.state.catalog,
                    "bridge": {
                        "version": API_VERSION,
                        "execute": "/v1/execute",
                        "status": "/v1/status",
                    },
                },
            )
            return
        if parsed.path == "/v1/browser/next":
            query = parse_qs(parsed.query)
            session_id = (query.get("sessionId") or [""])[0]
            if not session_id:
                self._send_json(HTTPStatus.BAD_REQUEST, structured_error("INVALID_PARAMS", "sessionId is required"))
                return
            try:
                wait_ms = int((query.get("waitMs") or ["25000"])[0])
            except ValueError:
                wait_ms = 25000
            command = self.server.state.take_next(session_id, wait_ms)
            if command is None:
                self._send_empty(HTTPStatus.NO_CONTENT)
            else:
                self._send_json(HTTPStatus.OK, command)
            return
        self._send_json(HTTPStatus.NOT_FOUND, structured_error("NOT_FOUND", "Unknown endpoint"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._authorized():
            return
        try:
            if parsed.path == "/v1/browser/register":
                payload = self._read_json()
                result = self.server.state.register_session(payload)
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/v1/browser/result":
                payload = self._read_json()
                result = self.server.state.submit_result(payload)
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/v1/execute":
                payload = self._read_json()
                action = str(payload.get("action") or "").strip()
                if action not in self.server.state.actions:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        structured_error("UNSUPPORTED_ACTION", "Unsupported action: " + action),
                    )
                    return
                params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
                request_id = str(payload.get("requestId") or "").strip() or None
                session_id = str(payload.get("sessionId") or "").strip() or None
                try:
                    timeout_ms = int(payload.get("timeoutMs", 30000))
                except (TypeError, ValueError):
                    timeout_ms = 30000
                timeout_ms = max(1000, min(timeout_ms, 120000))
                command_id, duplicate = self.server.state.enqueue(
                    action, params, request_id, session_id
                )
                result = self.server.state.wait_for_result(command_id, timeout_ms / 1000.0)
                if result is None:
                    self._send_json(
                        HTTPStatus.GATEWAY_TIMEOUT,
                        structured_error(
                            "BROWSER_TIMEOUT",
                            "No browser result before the command timeout",
                            {"requestId": request_id, "duplicate": duplicate},
                        ),
                    )
                    return
                self._send_json(HTTPStatus.OK, result)
                return
            if parsed.path == "/v1/artifact":
                query = parse_qs(parsed.query)
                filename = (query.get("filename") or ["artifact.bin"])[0]
                target = self.server.state.artifact_path(filename)
                data = self._read_body()
                target.write_bytes(data)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "artifactPath": str(target),
                        "filename": target.name,
                        "size": len(data),
                    },
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, structured_error("NOT_FOUND", "Unknown endpoint"))
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, structured_error("INVALID_PARAMS", str(exc)))
        except OSError as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, structured_error("INTERNAL_ERROR", str(exc)))


def load_catalog(root: Path) -> tuple[dict[str, Any], set[str]]:
    path = root / "agent" / "actions.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    actions = {
        str(item.get("name"))
        for item in catalog.get("actions", [])
        if isinstance(item, dict) and item.get("name")
    }
    if not actions:
        raise RuntimeError(f"No actions found in {path}")
    return catalog, actions


def browser_candidates(choice: str) -> list[tuple[str, Path]]:
    env = os.environ
    edge_paths = [
        Path(env.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(env.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(env.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    chrome_paths = [
        Path(env.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(env.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(env.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    candidates: list[tuple[str, Path]] = []
    if choice in ("auto", "edge"):
        candidates.extend(("edge", item) for item in edge_paths)
        edge_command = shutil.which("msedge")
        if edge_command:
            candidates.append(("edge", Path(edge_command)))
    if choice in ("auto", "chrome"):
        candidates.extend(("chrome", item) for item in chrome_paths)
        chrome_command = shutil.which("chrome")
        if chrome_command:
            candidates.append(("chrome", Path(chrome_command)))
    seen: set[str] = set()
    unique = []
    for name, path in candidates:
        key = str(path).lower()
        if key not in seen and str(path) and path.exists():
            seen.add(key)
            unique.append((name, path))
    return unique


def launch_browser(choice: str, page_url: str) -> dict[str, Any] | None:
    for name, executable in browser_candidates(choice):
        try:
            subprocess.Popen(
                [str(executable), page_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return {"browser": name, "executable": str(executable)}
        except OSError:
            continue
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local XY Plotter agent bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.environ.get("XY_PLOTTER_AGENT_TOKEN", ""))
    parser.add_argument("--browser", choices=("auto", "edge", "chrome"), default="auto")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL)
    parser.add_argument("--artifact-dir", default="agent-exports")
    parser.add_argument("--no-open", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("Security error: bridge may only listen on 127.0.0.1 or localhost")
    root = Path(__file__).resolve().parent.parent
    catalog, actions = load_catalog(root)
    artifact_dir = Path(args.artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir
    token = args.token or secrets.token_urlsafe(24)
    state = BridgeState(token, actions, catalog, artifact_dir)
    server = BridgeServer((args.host, args.port), state)
    actual_port = server.server_address[1]
    bridge_url = f"http://127.0.0.1:{actual_port}"
    page = urlparse(args.page_url)
    query = parse_qs(page.query)
    query.update(
        {
            "agent": ["1"],
            "fresh": ["1"],
            "bridge": [bridge_url],
            "token": [token],
        }
    )
    agent_url = page._replace(query=urlencode(query, doseq=True)).geturl()

    print("XY Plotter agent bridge")
    print(f"  API:   {bridge_url}")
    print(f"  Token: {token}")
    print(f"  Page:  {agent_url}")
    print(f"  Files: {artifact_dir}")
    if args.no_open:
        launched = None
    else:
        launched = launch_browser(args.browser, agent_url)
        if launched:
            print(f"  Browser: {launched['browser']} ({launched['executable']})")
        else:
            print("  Browser: not found; open the Page URL manually", file=sys.stderr)
    sys.stdout.flush()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping bridge.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
