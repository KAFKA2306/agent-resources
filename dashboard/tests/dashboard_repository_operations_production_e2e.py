from __future__ import annotations

import os
import re
import subprocess
from urllib.parse import urljoin

from dashboard.production_live_smoke import verify_production_live
from dashboard_live_browser_e2e import find_chrome


PRODUCTION_URL = os.environ.get(
    "AGENT_RESOURCES_DASHBOARD_URL",
    "https://agent-resources-one.vercel.app/dashboard/",
)
EXPECTED_SHA = os.environ.get("EXPECTED_SHA", "main")
POKER_RAISE_QUIZ_URL = "https://kafka2306.github.io/poker-raise-quiz/"
ACTIONABLE_LANES = ("waiting", "failed", "done")


def dump_production_dom(url: str) -> str:
    result = subprocess.run(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-proxy-server",
            "--window-size=390,844",
            "--virtual-time-budget=10000",
            "--dump-dom",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    return result.stdout


def rendered_gate_counts(dom: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    pattern = re.compile(
        r'<button class="lane-gate"[^>]*data-lane="(waiting|failed|done)"[^>]*>'
        r'.*?<strong>(\d+)</strong>.*?</button>',
        re.DOTALL,
    )
    for lane, count in pattern.findall(dom):
        counts[lane] = int(count)
    return counts


def selected_gate_is_pressed(dom: str, lane: str) -> bool:
    return (
        re.search(
            rf'<button class="lane-gate"[^>]*data-lane="{re.escape(lane)}"'
            rf'[^>]*aria-pressed="true"[^>]*>',
            dom,
        )
        is not None
    )


def main() -> None:
    production_root = urljoin(PRODUCTION_URL, "../")
    _endpoint, live_payload, _age_seconds = verify_production_live(production_root, EXPECTED_SHA)
    expected_repository_count = live_payload["summary"]["repositoryCount"]

    dom = dump_production_dom(PRODUCTION_URL)
    repository_count_pattern = re.compile(
        r'id="repository-count"[^>]*>\s*(\d+) repositories\s*</span>'
    )
    repository_count_match = repository_count_pattern.search(dom)
    poker_surface_pattern = re.compile(
        r'<article class="world-station"[^>]*>.*?'
        r'<strong>poker-raise-quiz</strong>.*?'
        r'href="https://kafka2306\.github\.io/poker-raise-quiz/"[^>]*>.*?'
        r'FRONT ↗.*?</a>.*?</article>',
        re.DOTALL,
    )
    gate_counts = rendered_gate_counts(dom)
    selected_lane = next(
        (lane for lane in ACTIONABLE_LANES if gate_counts.get(lane, 0) > 0),
        "waiting",
    )
    selected_dom = dump_production_dom(f"{PRODUCTION_URL}?lane={selected_lane}")
    selected_count = gate_counts.get(selected_lane, 0)

    checks = {
        "live status rendered": 'id="snapshot-status" data-state="fresh">LIVE<' in dom,
        "live error absent": "LIVE ERROR" not in dom,
        "repository count rendered": repository_count_match is not None,
        "operations timestamp rendered": "Operations snapshot:" in dom
        and "Operations snapshot: unavailable" not in dom,
        "operations is not unavailable": "Operations: unavailable" not in dom,
        "obsolete classification absent": "classified" not in dom and "unclassified" not in dom,
        "poker-raise-quiz production surface rendered": poker_surface_pattern.search(dom)
        is not None,
        "skip link targets main": 'class="skip-link" href="#main"' in dom
        and re.search(r'<main class="main-panel"[^>]*id="main"[^>]*tabindex="-1"', dom)
        is not None,
        "three actionable gates rendered": set(gate_counts) == set(ACTIONABLE_LANES),
        "query-selected gate exposes pressed state": selected_gate_is_pressed(
            selected_dom, selected_lane
        ),
        "owner/repository label rendered": "KAFKA2306 /" in selected_dom,
    }
    if selected_count > 0:
        checks["selected gate exposes reason"] = 'class="gate-item-reason"' in selected_dom

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit(
            "repository operations production browser E2E failed: " + ", ".join(failures)
        )

    rendered_repository_count = int(repository_count_match.group(1))
    if rendered_repository_count <= 0:
        raise SystemExit("repository operations production browser E2E failed: rendered repository count is zero")
    if rendered_repository_count != expected_repository_count:
        raise SystemExit(
            "repository operations production browser E2E failed: "
            f"rendered repository count {rendered_repository_count} != live API {expected_repository_count}"
        )

    print(
        "repository operations production browser E2E: "
        f"live {rendered_repository_count} repos at {live_payload['fetchedAt']}, "
        f"operations snapshot rendered without obsolete classification, "
        f"mobile viewport skip/owner/{selected_lane} pressed state verified, "
        f"poker-raise-quiz FRONT {POKER_RAISE_QUIZ_URL} PASS"
    )


if __name__ == "__main__":
    main()
