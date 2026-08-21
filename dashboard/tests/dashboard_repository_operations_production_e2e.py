from __future__ import annotations

import os
import re
import subprocess

from dashboard_live_browser_e2e import find_chrome


PRODUCTION_URL = os.environ.get(
    "AGENT_RESOURCES_DASHBOARD_URL",
    "https://agent-resources-one.vercel.app/dashboard/",
)


def main() -> None:
    result = subprocess.run(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-proxy-server",
            "--virtual-time-budget=10000",
            "--dump-dom",
            PRODUCTION_URL,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )

    dom = result.stdout
    summary_pattern = re.compile(
        r"Operations:\s*(\d+) repos\s*·\s*(\d+) classified\s*·\s*(\d+) unclassified"
    )
    summary_match = summary_pattern.search(dom)

    checks = {
        "operations timestamp rendered": "Operations snapshot:" in dom
        and "Operations snapshot: unavailable" not in dom,
        "operations summary rendered": summary_match is not None,
        "operations summary is not unavailable": "Operations: unavailable" not in dom,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit(
            "repository operations production browser E2E failed: " + ", ".join(failures)
        )

    repository_count, classified_count, unclassified_count = map(int, summary_match.groups())
    if repository_count <= 0:
        raise SystemExit("repository operations production browser E2E failed: repository count is zero")
    if classified_count + unclassified_count != repository_count:
        raise SystemExit(
            "repository operations production browser E2E failed: classification counts do not sum to repository count"
        )

    print(
        "repository operations production browser E2E: "
        f"{repository_count} repos, {classified_count} classified, "
        f"{unclassified_count} unclassified PASS"
    )


if __name__ == "__main__":
    main()
