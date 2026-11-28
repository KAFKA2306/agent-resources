from __future__ import annotations

import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urljoin

from dashboard_snapshot_browser_e2e import find_chrome

DASHBOARD_URL = os.environ.get(
    "AGENT_RESOURCES_DASHBOARD_URL",
    "https://agent-resources-one.vercel.app/dashboard/",
)
EXPECTED_SHA = os.environ.get("EXPECTED_SHA", "")


def verify_http_resources(
    dashboard_url: str,
    expected_sha: str,
    *,
    open_url: Callable[..., Any] | None = None,
) -> list[tuple[str, int]]:
    opener = open_url or urllib.request.urlopen
    root = urljoin(dashboard_url, "../")
    query = f"?v={quote(expected_sha)}" if expected_sha else ""
    resources = (
        ("production root", root),
        ("dashboard page", dashboard_url),
        ("dashboard snapshot", urljoin(root, f"dashboard/dashboard.json{query}")),
        (
            "repository operations snapshot",
            urljoin(root, f"dashboard/repository-operations.json{query}"),
        ),
        ("factory state snapshot", urljoin(root, f"dashboard/factory-state.json{query}")),
        ("dashboard JavaScript", urljoin(root, "dashboard/dashboard.js")),
        ("factory evidence JavaScript", urljoin(root, "dashboard/factory-evidence.js")),
        ("dashboard favicon", urljoin(root, "site/assets/images/favicon.png")),
    )
    results = []
    for label, url in resources:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "User-Agent": "agent-resources-production-health",
            },
        )
        try:
            with opener(request, timeout=20) as response:
                status = int(response.status)
        except urllib.error.HTTPError as error:
            raise ValueError(f"{label} returned HTTP {error.code}: {url}") from error
        if status != 200:
            raise ValueError(f"{label} returned HTTP {status}: {url}")
        results.append((label, status))
    return results


def verify_browser_runtime(dashboard_url: str) -> None:
    result = subprocess.run(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--no-proxy-server",
            "--enable-logging=stderr",
            "--virtual-time-budget=10000",
            "--dump-dom",
            dashboard_url,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0:
        raise ValueError(f"headless Chrome exited with status {result.returncode}: {result.stderr}")
    if "ERROR:CONSOLE" in result.stderr or "Failed to load resource" in result.stderr:
        raise ValueError(f"headless Chrome reported a console or resource error: {result.stderr}")


def main() -> None:
    resources = verify_http_resources(DASHBOARD_URL, EXPECTED_SHA)
    verify_browser_runtime(DASHBOARD_URL)
    print(
        "production resource/browser health: "
        + ", ".join(f"{label}=HTTP {status}" for label, status in resources)
        + "; console/resources clean"
    )


if __name__ == "__main__":
    main()
