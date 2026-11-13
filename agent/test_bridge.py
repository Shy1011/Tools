from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from agent import xy_plotter_bridge


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "agent" / "xy_plotter_bridge.py"
TOKEN = "test-token-123"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.port = free_port()
        cls.process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "--no-open",
                "--port",
                str(cls.port),
                "--token",
                TOKEN,
                "--artifact-dir",
                str(Path(cls.temp.name) / "exports"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(cls.base + "/v1/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.05)
        stderr = cls.process.stderr.read() if cls.process.stderr else ""
        raise RuntimeError("Bridge did not start: " + stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        cls.temp.cleanup()

    def request(
        self,
        method: str,
        path: str,
        body: dict | bytes | None = None,
        token: str | None = TOKEN,
        origin: str | None = None,
    ):
        headers = {}
        if token is not None:
            headers["X-Agent-Token"] = token
        if origin:
            headers["Origin"] = origin
        data = None
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif isinstance(body, bytes):
            data = body
            headers["Content-Type"] = "application/octet-stream"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(request, timeout=10)

    def register(self) -> str:
        session_id = "test-session"
        with self.request(
            "POST",
            "/v1/browser/register",
            {
                "sessionId": session_id,
                "userAgent": "unit-test",
                "apiVersion": "1.0.0",
                "capabilities": 44,
            },
        ) as response:
            self.assertEqual(response.status, 200)
        return session_id

    def test_health_auth_and_cors(self) -> None:
        with urllib.request.urlopen(self.base + "/v1/health", timeout=2) as response:
            payload = json.load(response)
            self.assertTrue(payload["ok"])
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request("GET", "/v1/status", token=None)
        self.assertEqual(context.exception.code, 401)
        preflight = urllib.request.Request(
            self.base + "/v1/browser/next",
            method="OPTIONS",
            headers={
                "Origin": "https://shy1011.github.io",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Agent-Token",
            },
        )
        with urllib.request.urlopen(preflight, timeout=2) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(
                response.headers["Access-Control-Allow-Origin"],
                "https://shy1011.github.io",
            )
            self.assertEqual(response.headers["Access-Control-Allow-Private-Network"], "true")

    def test_execute_round_trip_and_request_idempotency(self) -> None:
        session_id = self.register()
        payload = {
            "requestId": "round-trip-1",
            "action": "chart.getSummary",
            "params": {},
            "timeoutMs": 5000,
        }
        holder: dict[str, object] = {}

        def execute() -> None:
            with self.request("POST", "/v1/execute", payload) as response:
                holder["payload"] = json.load(response)

        thread = threading.Thread(target=execute)
        thread.start()
        with self.request(
            "GET",
            f"/v1/browser/next?sessionId={session_id}&waitMs=3000",
        ) as response:
            command = json.load(response)
        self.assertEqual(command["action"], "chart.getSummary")
        result = {
            "ok": True,
            "action": command["action"],
            "revision": 1,
            "result": {"curveCount": 1},
            "warnings": [],
            "error": None,
        }
        with self.request(
            "POST",
            "/v1/browser/result",
            {"id": command["id"], "sessionId": session_id, "result": result},
        ) as response:
            self.assertEqual(response.status, 200)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(holder["payload"]["revision"], 1)
        with self.request("POST", "/v1/execute", payload) as response:
            duplicate = json.load(response)
        self.assertEqual(duplicate["revision"], 1)

    def test_artifact_filename_is_sanitized(self) -> None:
        self.register()
        path = "/v1/artifact?" + urllib.parse.urlencode({"filename": "../bad:name.xlsx"})
        with self.request("POST", path, b"artifact-bytes") as response:
            payload = json.load(response)
        artifact = Path(payload["artifactPath"])
        self.assertTrue(artifact.exists())
        self.assertEqual(artifact.read_bytes(), b"artifact-bytes")
        self.assertEqual(artifact.parent, Path(self.temp.name) / "exports")
        self.assertNotEqual(artifact.name, "../bad:name.xlsx")

    def test_browser_launcher_handles_missing_browser(self) -> None:
        missing = Path(self.temp.name) / "missing-browser.exe"
        with mock.patch.object(
            xy_plotter_bridge,
            "browser_candidates",
            return_value=[("chrome", missing)],
        ):
            self.assertIsNone(
                xy_plotter_bridge.launch_browser("chrome", "https://example.com")
            )


if __name__ == "__main__":
    unittest.main()
