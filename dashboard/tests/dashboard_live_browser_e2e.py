from __future__ import annotations

import datetime as dt
import http.server
import json
import pathlib
import shutil
import socketserver
import ssl
import subprocess
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT / "docs" / "dashboard"
PUBLIC_SURFACE_URL = "https://kafka2306.github.io/poker-raise-quiz/"


def repository(repo_id: str, name: str) -> dict[str, object]:
    return {
        "id": repo_id,
        "owner": "KAFKA2306",
        "name": name,
        "url": f"https://github.com/KAFKA2306/{name}",
        "group": "unclassified",
        "visibility": "public",
        "archived": False,
        "updatedAt": "2026-08-20T00:00:00Z",
    }


baseline_repository = repository("shared", "poker-raise-quiz")
baseline_repository["publicLinks"] = [{"kind": "front", "url": PUBLIC_SURFACE_URL}]

BASELINE = {
    "schemaVersion": "1.0.0",
    "generatedAt": "2026-08-19T00:00:00Z",
    "summary": {"repositoryCount": 1, "workItemCount": 1, "activityCount": 0},
    "repositories": [baseline_repository],
    "workItems": [
        {
            "id": "shared#1",
            "repositoryId": "shared",
            "kind": "issue",
            "number": 1,
            "title": "BASELINE-ISSUE",
            "url": "https://github.com/KAFKA2306/poker-raise-quiz/issues/1",
            "state": "open",
            "updatedAt": "2026-08-19T00:00:00Z",
            "lane": "waiting",
            "laneReason": "baseline fixture",
        }
    ],
    "activity": [],
}


def live_payload() -> dict[str, object]:
    fetched_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    return {
        "schemaVersion": "1.0.0",
        "source": "live",
        "scope": "public",
        "fetchedAt": fetched_at,
        "repositories": [repository("shared", "poker-raise-quiz")],
        "workItems": [
            {
                "id": "shared#2",
                "repositoryId": "shared",
                "kind": "issue",
                "number": 2,
                "title": "LIVE-ISSUE",
                "url": "https://github.com/KAFKA2306/poker-raise-quiz/issues/2",
                "state": "open",
                "updatedAt": fetched_at,
                "lane": "failed",
                "laneReason": "live fixture",
            }
        ],
        "activity": [],
    }


class FixtureHandler(http.server.SimpleHTTPRequestHandler):
    live_requests = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def log_message(self, *_args):
        return

    def send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib handler API
        path = self.path.split("?", 1)[0]
        if path == "/dashboard.json":
            self.send_json(BASELINE)
            return
        if path == "/live-config.json":
            port = self.server.server_address[1]
            self.send_json({"endpoint": f"https://localhost:{port}/api/dashboard-live"})
            return
        if path == "/api/dashboard-live":
            type(self).live_requests += 1
            self.send_json(live_payload())
            return
        super().do_GET()


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def find_chrome() -> str:
    for executable in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(executable)
        if resolved:
            return resolved
    raise SystemExit("headless Chrome/Chromium is required for dashboard browser E2E")


def create_certificate(directory: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    openssl = shutil.which("openssl")
    if not openssl:
        raise SystemExit("openssl is required for localhost HTTPS browser E2E")
    key_path = directory / "localhost.key"
    cert_path = directory / "localhost.crt"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-subj",
            "/CN=localhost",
            "-days",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return cert_path, key_path


def main() -> None:
    FixtureHandler.live_requests = 0
    with tempfile.TemporaryDirectory() as tmp, ThreadingServer(("127.0.0.1", 0), FixtureHandler) as server:
        cert_path, key_path = create_certificate(pathlib.Path(tmp))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    find_chrome(),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-proxy-server",
                    "--ignore-certificate-errors",
                    "--virtual-time-budget=4000",
                    "--dump-dom",
                    f"https://localhost:{port}/",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    dom = result.stdout
    checks = {
        "live request occurred": FixtureHandler.live_requests >= 1,
        "live status rendered": 'id="snapshot-status" data-state="fresh">LIVE<' in dom,
        "live repository rendered": "poker-raise-quiz" in dom,
        "live work item rendered": "LIVE-ISSUE" in dom,
        "primary action rendered": 'id="primary-action"' in dom and "最優先の対応" in dom,
        "primary action has one-click evidence": "次の行動: 対応先を開く" in dom,
        "baseline public link survived live overlay": PUBLIC_SURFACE_URL in dom,
        "public surface action rendered": "FRONT ↗" in dom,
        "work item terminology rendered": "作業項目 1件" in dom,
        "misleading agent count absent": "1 agents" not in dom,
        "baseline work item replaced": "BASELINE-ISSUE" not in dom,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit("dashboard browser E2E failed: " + ", ".join(failures))
    print("dashboard browser E2E: baseline publicLinks -> live overlay -> primary action PASS")


if __name__ == "__main__":
    main()
