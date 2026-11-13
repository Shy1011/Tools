from __future__ import annotations

import base64
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "agent" / "xy_plotter_bridge.py"
OUTPUT = ROOT / "agent" / "e2e" / "http-output"
TOKEN = "edge-e2e-token"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(base: str, method: str, path: str, payload=None):
    headers = {"X-Agent-Token": TOKEN}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read()
        return json.loads(body) if body else None


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            sys.executable,
            str(BRIDGE),
            "--port",
            str(port),
            "--token",
            TOKEN,
            "--browser",
            "edge",
            "--page-url",
            "http://127.0.0.1:8000/xy-plotter.html",
            "--artifact-dir",
            str(OUTPUT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status = request(base, "GET", "/v1/status")
                if status.get("browserConnected"):
                    break
            except Exception:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("Edge did not connect to the local bridge")

        replace = request(
            base,
            "POST",
            "/v1/execute",
            {
                "requestId": "edge-replace",
                "action": "project.replace",
                "params": {
                    "title": "Edge bridge verification",
                    "xLabel": "X",
                    "yLabel": "Y",
                    "explanation": "HTTP bridge E2E",
                    "curves": [
                        {
                            "name": "Edge Curve",
                            "x": [1, 2, 3, 4, 5],
                            "y": [2, 4, 9, 16, 25],
                        }
                    ],
                    "options": {"cleanEnabled": False, "grid": True},
                },
                "timeoutMs": 30000,
            },
        )
        if not replace.get("ok"):
            raise RuntimeError("replace failed: " + json.dumps(replace, ensure_ascii=False))

        exports = {}
        for kind in ("png", "csv", "xlsx"):
            response = request(
                base,
                "POST",
                "/v1/execute",
                {
                    "requestId": f"edge-{kind}",
                    "action": f"export.{kind}",
                    "params": {
                        "filename": f"edge-roundtrip.{kind}",
                        "download": False,
                    },
                    "timeoutMs": 30000,
                },
            )
            exports[kind] = response
            artifact = Path(response["result"]["artifactPath"])
            if not artifact.exists() or artifact.stat().st_size == 0:
                raise RuntimeError(f"{kind} artifact was not saved")

        with zipfile.ZipFile(exports["xlsx"]["result"]["artifactPath"]) as workbook:
            sheets = workbook.namelist()
            if "xl/worksheets/sheet1.xml" not in sheets or "xl/media/image1.png" not in sheets:
                raise RuntimeError("XLSX does not contain the data and chart parts")

        xlsx_bytes = Path(exports["xlsx"]["result"]["artifactPath"]).read_bytes()
        imported = request(
            base,
            "POST",
            "/v1/execute",
            {
                "requestId": "edge-import-xlsx",
                "action": "import.xlsx",
                "params": {
                    "filename": "edge-roundtrip.xlsx",
                    "base64": base64.b64encode(xlsx_bytes).decode("ascii"),
                },
                "timeoutMs": 30000,
            },
        )
        summary = request(
            base,
            "POST",
            "/v1/execute",
            {
                "requestId": "edge-summary",
                "action": "chart.getSummary",
                "params": {},
                "timeoutMs": 30000,
            },
        )
        print(
            json.dumps(
                {
                    "status": request(base, "GET", "/v1/status"),
                    "replace": replace["result"],
                    "exports": {
                        key: value["result"]["artifactPath"]
                        for key, value in exports.items()
                    },
                    "imported": imported["result"],
                    "summary": summary["result"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        if process.returncode not in (0, -15):
            stderr = process.stderr.read() if process.stderr else ""
            if stderr:
                print(stderr, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
