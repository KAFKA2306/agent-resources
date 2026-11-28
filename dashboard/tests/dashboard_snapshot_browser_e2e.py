from __future__ import annotations

import http.server
import json
import pathlib
import re
import shutil
import socketserver
import ssl
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from typing import ClassVar

ROOT = pathlib.Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT / "docs" / "dashboard"
PUBLIC_SURFACE_URL = "https://kafka2306.github.io/poker-raise-quiz/"
GENERATED_AT = "2026-08-19T00:00:00Z"


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
    "generatedAt": GENERATED_AT,
    "summary": {"repositoryCount": 1, "workItemCount": 1, "activityCount": 1},
    "repositories": [baseline_repository],
    "workItems": [
        {
            "id": "shared#1",
            "repositoryId": "shared",
            "kind": "issue",
            "number": 1,
            "title": "SNAPSHOT-ISSUE",
            "url": "https://github.com/KAFKA2306/poker-raise-quiz/issues/1",
            "state": "open",
            "updatedAt": "2026-08-19T00:00:00Z",
            "lane": "waiting",
            "laneReason": "baseline fixture",
        }
    ],
    "activity": [
        {
            "id": "shared:activity:1",
            "repositoryId": "shared",
            "kind": "issue",
            "occurredAt": "2026-08-19T00:00:00Z",
            "summary": "Snapshot activity fixture",
            "url": "https://github.com/KAFKA2306/poker-raise-quiz/issues/1",
        }
    ],
    "stats": {
        "owner": "KAFKA2306",
        "scope": "public",
        "timezone": "Asia/Tokyo",
        "publicRepositories": 1,
        "archivedPublicRepositories": 0,
        "monthly": [
            {
                "month": "2026-08",
                "commits": 100,
                "prsCreated": 20,
                "prsMerged": 18,
                "issuesCreated": 15,
                "issuesClosed": 12,
                "partial": True,
            }
        ],
        "weekly": [
            {
                "weekStart": "2026-08-03",
                "weekEnd": "2026-08-09",
                "commits": 30,
                "prsCreated": 6,
                "prsMerged": 5,
                "issuesCreated": 4,
                "issuesClosed": 3,
                "partial": False,
            },
            {
                "weekStart": "2026-08-10",
                "weekEnd": "2026-08-13",
                "commits": 70,
                "prsCreated": 14,
                "prsMerged": 12,
                "issuesCreated": 11,
                "issuesClosed": 9,
                "partial": True,
            },
        ],
    },
}

FACTORY_STATE = {
    "schemaVersion": "1.0.0",
    "generatedAt": GENERATED_AT,
    "sourceRevision": "abc123def456",
    "authority": {"repository": "KAFKA2306/agent-resources", "defaultBranch": "main", "mainSha": "abc123def456"},
    "pages": {
        "workflowRunId": "1234",
        "workflowRunUrl": "https://github.com/KAFKA2306/agent-resources/actions/runs/1234",
        "sourceRevision": "abc123def456",
        "state": "UNVERIFIED",
    },
    "observer": {"state": "UNVERIFIED", "runId": None, "url": None},
    "canonicalIssue": {
        "number": 381,
        "title": "Software Factory",
        "state": "OPEN",
        "updatedAt": GENERATED_AT,
        "url": "https://github.com/KAFKA2306/agent-resources/issues/381",
    },
    "activePullRequests": [],
    "capabilities": [
        {"id": "observe-classify", "label": "Observe / classify", "state": "UNVERIFIED"},
        {"id": "bounded-retry", "label": "Bounded retry", "state": "EXISTING"},
        {"id": "deterministic-repair", "label": "Deterministic repair", "state": "MISSING"},
        {"id": "future-capability", "label": "Future capability", "state": "EXPERIMENTAL"},
    ],
}

ISSUE_HISTORY = {
    "schemaVersion": 1,
    "scope": "public",
    "timezone": "Asia/Tokyo",
    "snapshots": [
        {"date": "2026-08-18", "observedAt": "2026-08-18T09:00:00+09:00", "allOpen": 10, "authoredOpen": 8},
        {"date": "2026-08-19", "observedAt": "2026-08-19T09:00:00+09:00", "allOpen": 7, "authoredOpen": 5},
    ],
}


class FixtureHandler(http.server.SimpleHTTPRequestHandler):
    requests: ClassVar[list[str]] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        type(self).requests.append(path)
        if path == "/issue-backlog-history.json":
            self.send_json(ISSUE_HISTORY)
            return
        if path == "/dashboard.json":
            self.send_json(BASELINE)
            return
        if path == "/factory-state.json":
            self.send_json(FACTORY_STATE)
            return
        if path == "/repository-operations.json":
            self.send_json({"generatedAt": GENERATED_AT, "sourceRevision": "abc123def456", "runId": "1234", "repositories": []})
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
    FixtureHandler.requests = []
    with tempfile.TemporaryDirectory() as tmp, ThreadingServer(("127.0.0.1", 0), FixtureHandler) as server:
        cert_path, key_path = create_certificate(pathlib.Path(tmp))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def dump_dom(query: str = "") -> tuple[str, str]:
                result = subprocess.run(
                    [
                        find_chrome(),
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--no-proxy-server",
                        "--ignore-certificate-errors",
                        "--enable-logging=stderr",
                        "--virtual-time-budget=4000",
                        "--dump-dom",
                        f"https://localhost:{port}/{query}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                return result.stdout, result.stderr

            dom, stderr = dump_dom()
            weekly_dom, weekly_stderr = dump_dom("?stats=weekly")
        finally:
            server.shutdown()
            thread.join(timeout=5)

    forbidden_requests = {"/api/dashboard-live", "/live-config.json"}
    checks = {
        "machine snapshot rendered its exact generation time": f'<time id="factory-state-generated-at" class="snapshot-time" datetime="{GENERATED_AT}" title="{GENERATED_AT}">{GENERATED_AT}</time>' in dom,
        "static factory snapshot stays explicitly unverified for current production": "SNAPSHOT · current production state UNVERIFIED" in dom,
        "stored capability values are preserved": 'data-capability-state="UNVERIFIED"' in dom and 'data-capability-state="MISSING"' in dom and 'data-capability-state="EXISTING"' in dom and 'data-capability-state="EXPERIMENTAL"' in dom and ">EXPERIMENTAL</small>" in dom,
        "snapshot source revision is rendered": "abc123def456" in dom,
        "snapshot age is rendered without claiming live success": "古いSnapshot" in dom and "GitHubの現在状態は未確認です" in dom and "LIVE · workflow snapshot" not in dom,
        "static repository and work item rendered": "poker-raise-quiz" in dom and "SNAPSHOT-ISSUE" in dom,
        "primary action has one-click evidence": "Snapshot上の確認候補 · 未解決PR" in dom and "Issueを開く" in dom,
        "baseline public link rendered": PUBLIC_SURFACE_URL in dom and 'class="constellation-surface is-front"' in dom,
        "work item terminology rendered": re.search(r'id="agent-world-summary"[^>]*>\s*1 NODES · 1 ACTIVE\s*<', dom) is not None,
        "issue backlog graph reports actual latest and delta": 'id="issue-history-title">未解決Issueの推移</h2>' in dom and "7件" in dom and "-3件" in dom and "2026-08-19" in dom,
        "issue backlog table accessible": "日別の件数を表で確認" in dom,
        "monthly stats selected by default": 'data-stats-view="monthly" aria-pressed="true"' in dom and 'id="github-stats-title">OUTPUT / YTD</h2>' in dom and 'class="output-waveform"' in dom,
        "weekly stats selected by query": 'data-stats-view="weekly" aria-pressed="true"' in weekly_dom and 'id="github-stats-title">OUTPUT / 12W</h2>' in weekly_dom,
        "weekly stats retain their stored values": 'data-view="weekly"' in weekly_dom and 'aria-label="GitHub週次活動"' in weekly_dom and weekly_dom.count('class="wave-point is-commits"') == 2,
        "no live endpoint or config was requested": not forbidden_requests.intersection(FixtureHandler.requests),
        "browser console has no resource or script errors": all("ERROR:CONSOLE" not in output and "Failed to load resource" not in output for output in (stderr, weekly_stderr)),
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit("dashboard snapshot browser E2E failed: " + ", ".join(failures))
    print("dashboard browser E2E: static snapshots, provenance, UNKNOWN state, monthly/weekly data PASS")


if __name__ == "__main__":
    main()
