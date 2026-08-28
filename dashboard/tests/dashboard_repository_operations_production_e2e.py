from __future__ import annotations

import os
import re
import subprocess
from html.parser import HTMLParser
from urllib.parse import urljoin

from dashboard.production_live_smoke import verify_production_live
from dashboard_live_browser_e2e import find_chrome


PRODUCTION_URL = os.environ.get(
    "AGENT_RESOURCES_DASHBOARD_URL",
    "https://agent-resources-one.vercel.app/dashboard/",
)
EXPECTED_SHA = os.environ.get("EXPECTED_SHA", "main")
POKER_RAISE_QUIZ_URL = "https://kafka2306.github.io/poker-raise-quiz/"


class _LiveTimestampParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.datetime: str | None = None
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if self.depth == 0 and tag == "time" and attributes.get("id") == "live-fetched-at":
            self.depth = 1
            self.datetime = attributes.get("datetime")
        elif self.depth > 0:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.depth > 0:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth > 0:
            self.text_parts.append(data)


def parse_live_timestamp(dom: str) -> tuple[str, str] | None:
    parser = _LiveTimestampParser()
    parser.feed(dom)
    parser.close()
    text = "".join(parser.text_parts).strip()
    if not parser.datetime or not text:
        return None
    return parser.datetime, text


def main() -> None:
    production_root = urljoin(PRODUCTION_URL, "../")
    _endpoint, live_payload, _age_seconds = verify_production_live(production_root, EXPECTED_SHA)
    expected_repository_count = live_payload["summary"]["repositoryCount"]

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
    repository_count_pattern = re.compile(
        r'id="repository-count"[^>]*>\s*(\d+) repositories\s*</span>'
    )
    repository_count_match = repository_count_pattern.search(dom)
    live_timestamp = parse_live_timestamp(dom)
    poker_surface_pattern = re.compile(
        r'<article class="world-station"[^>]*>.*?'
        r'<strong>poker-raise-quiz</strong>.*?'
        r'href="https://kafka2306\.github\.io/poker-raise-quiz/"[^>]*>.*?'
        r'FRONT ↗.*?</a>.*?</article>',
        re.DOTALL,
    )

    checks = {
        "live status rendered": 'id="snapshot-status" data-state="fresh">LIVE<' in dom,
        "live timestamp rendered": live_timestamp is not None,
        "live error absent": "LIVE ERROR" not in dom,
        "repository count rendered": repository_count_match is not None,
        "operations timestamp rendered": "Operations snapshot:" in dom
        and "Operations snapshot: unavailable" not in dom,
        "operations summary rendered": summary_match is not None,
        "operations summary is not unavailable": "Operations: unavailable" not in dom,
        "poker-raise-quiz production surface rendered": poker_surface_pattern.search(dom)
        is not None,
    }
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

    repository_count, classified_count, unclassified_count = map(int, summary_match.groups())
    if repository_count <= 0:
        raise SystemExit("repository operations production browser E2E failed: repository count is zero")
    if classified_count + unclassified_count != repository_count:
        raise SystemExit(
            "repository operations production browser E2E failed: classification counts do not sum to repository count"
        )

    live_datetime, live_text = live_timestamp
    if live_text.removeprefix("Live:").strip() in {"読込中", "取得できません"}:
        raise SystemExit("repository operations production browser E2E failed: live timestamp is unavailable")

    print(
        "repository operations production browser E2E: "
        f"live {rendered_repository_count} repos at {live_datetime}, operations {repository_count} repos, "
        f"{classified_count} classified, {unclassified_count} unclassified, "
        f"poker-raise-quiz FRONT {POKER_RAISE_QUIZ_URL} PASS"
    )


if __name__ == "__main__":
    main()
