from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime
from urllib.parse import urljoin

from dashboard_snapshot_browser_e2e import find_chrome

from dashboard.production_snapshot_smoke import verify_production_factory_state

PRODUCTION_URL = os.environ.get(
    "AGENT_RESOURCES_DASHBOARD_URL",
    "https://agent-resources-one.vercel.app/dashboard/",
)
EXPECTED_SHA = os.environ.get("EXPECTED_SHA", "")


def fetch_text(production_root: str, relative_path: str) -> str:
    request = urllib.request.Request(
        urljoin(production_root, relative_path),
        headers={
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "User-Agent": "agent-resources-snapshot-production-e2e",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"{relative_path} returned HTTP {response.status}")
        return response.read().decode("utf-8")


def fetch_json(production_root: str, relative_path: str) -> dict:
    return json.loads(fetch_text(production_root, relative_path))


def dump_production_dom(url: str) -> tuple[str, str]:
    result = subprocess.run(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--no-proxy-server",
            "--enable-logging=stderr",
            "--window-size=390,844",
            "--virtual-time-budget=10000",
            "--dump-dom",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.stderr


def rendered_gate_counts(dom: str) -> dict[str, int]:
    pattern = re.compile(
        r'<button class="lane-gate"[^>]*data-lane="(waiting|failed|done)"[^>]*>'
        r'.*?<strong>(\d+)</strong>.*?</button>',
        re.DOTALL,
    )
    return {lane: int(count) for lane, count in pattern.findall(dom)}


def selected_gate_is_pressed(dom: str, lane: str) -> bool:
    return re.search(
        rf'<button class="lane-gate"[^>]*data-lane="{re.escape(lane)}"'
        rf'[^>]*aria-pressed="true"[^>]*>',
        dom,
    ) is not None


def selected_gate_detail(dom: str) -> str:
    match = re.search(r'<section id="gate-detail"[^>]*>(.*?)</section>', dom, re.DOTALL)
    return match.group(1) if match else ""


def primary_action_detail(dom: str) -> str:
    match = re.search(r'<section id="primary-action"[^>]*>(.*?)</section>', dom, re.DOTALL)
    return match.group(1) if match else ""


def _same_timestamp(left: str, right: str) -> bool:
    try:
        left_value = left[:-1] + "+00:00" if left.endswith("Z") else left
        right_value = right[:-1] + "+00:00" if right.endswith("Z") else right
        left_time = datetime.fromisoformat(left_value)
        right_time = datetime.fromisoformat(right_value)
        return (
            left_time.tzinfo is not None
            and right_time.tzinfo is not None
            and left_time.replace(microsecond=(left_time.microsecond // 1000) * 1000)
            == right_time.replace(microsecond=(right_time.microsecond // 1000) * 1000)
        )
    except (TypeError, ValueError):
        return False


def main() -> None:
    if not EXPECTED_SHA:
        raise SystemExit("EXPECTED_SHA is required for production snapshot verification")
    production_root = urljoin(PRODUCTION_URL, "../")
    dashboard = fetch_json(production_root, "dashboard/dashboard.json")
    operations = fetch_json(production_root, "dashboard/repository-operations.json")
    factory = verify_production_factory_state(production_root, EXPECTED_SHA)
    dashboard_js = fetch_text(production_root, "dashboard/dashboard.js")
    factory_js = fetch_text(production_root, "dashboard/factory-evidence.js")
    expected_repository_count = len(dashboard.get("repositories", []))
    if expected_repository_count <= 0:
        raise ValueError("canonical dashboard snapshot has zero repositories")
    if not dashboard.get("generatedAt"):
        raise ValueError("canonical dashboard snapshot generatedAt is missing")
    if not operations.get("generatedAt") or not operations.get("sourceRevision") or not operations.get("runId"):
        raise ValueError("operations snapshot provenance is incomplete")
    if not operations.get("repositories"):
        raise ValueError("operations snapshot has zero repositories")
    if "/api/dashboard-live" in dashboard_js + factory_js or "live-config.json" in dashboard_js + factory_js:
        raise ValueError("deployed Dashboard still contains the retired live endpoint")

    dom, chrome_stderr = dump_production_dom(PRODUCTION_URL)
    weekly_dom, weekly_stderr = dump_production_dom(f"{PRODUCTION_URL}?stats=weekly")
    counts = rendered_gate_counts(dom)
    selected_lane = next(
        (lane for lane in ("waiting", "failed", "done") if counts.get(lane, 0) > 0),
        "waiting",
    )
    selected_dom, selected_stderr = dump_production_dom(f"{PRODUCTION_URL}?lane={selected_lane}")
    selected_count = counts.get(selected_lane, 0)
    primary_action = primary_action_detail(dom)
    snapshot_status = re.search(r'<span[^>]*id="snapshot-status"[^>]*>([^<]+)<', dom)
    snapshot_time = re.search(r'<time[^>]*id="snapshot-generated-at"[^>]*>([^<]+)</time>', dom)
    snapshot_datetime = re.search(
        r'<time[^>]*id="snapshot-generated-at"[^>]*datetime="([^"]+)"', dom
    )
    factory_time = re.search(r'<time[^>]*id="factory-state-generated-at"[^>]*>([^<]+)</time>', dom)
    repo_count = re.search(
        r'<(?P<tag>span|strong)[^>]*id="repository-count"[^>]*>\s*(\d+) repositories\s*</(?P=tag)>',
        dom,
    )
    actionable_count = counts.get("waiting", 0) + counts.get("failed", 0)

    checks = {
        "static snapshot freshness is labeled without LIVE success": snapshot_status is not None
        and snapshot_status.group(1) in {"Snapshot生成から2時間以内", "古いSnapshot", "Snapshot生成時刻不明", "Snapshot生成時刻異常"}
        and "LIVE · workflow snapshot" not in dom
        and "ライブ取得失敗" not in dom,
        "current GitHub status remains explicitly unverified": "GitHubの現在状態は未確認です" in dom,
        "dashboard snapshot generatedAt is rendered": snapshot_time is not None
        and snapshot_time.group(1).startswith("Snapshot:")
        and snapshot_datetime is not None
        and _same_timestamp(snapshot_datetime.group(1), dashboard["generatedAt"]),
        "factory-state generatedAt and source revision are rendered": factory_time is not None
        and factory_time.group(1) == factory["generatedAt"]
        and factory["sourceRevision"] in dom,
        "recorded capability states remain visible": all(
            f'data-capability-state="{item.get("state")}"' in dom
            for item in factory.get("capabilities", [])
            if item.get("state")
        ),
        "factory evidence does not claim a live current revision": "SNAPSHOT · current production state UNVERIFIED" in dom,
        "repository count matches the static snapshot": repo_count is not None
        and int(repo_count.group(2)) == expected_repository_count,
        "operations snapshot is served with provenance": "Operations snapshot:" in dom
        and "Operations snapshot: unavailable" not in dom
        and "Operations: unavailable" not in dom,
        "obsolete repository classifications are absent": "classified" not in dom and "unclassified" not in dom,
        "skip link targets focusable main": 'class="skip-link" href="#main"' in dom
        and re.search(r'<main(?=[^>]*id="main")(?=[^>]*tabindex="-1")[^>]*>', dom) is not None,
        "observatory shows snapshot activity": "AUTONOMOUS OBSERVATORY" in dom
        and 'id="activity-title">FACTORY PULSE / 7D</h2>' in dom,
        "three actionable gates render": set(counts) == {"waiting", "failed", "done"},
        "selected gate exposes pressed state": selected_gate_is_pressed(selected_dom, selected_lane),
        "selected gate detail renders": bool(selected_gate_detail(selected_dom)),
        "monthly stats render": 'data-stats-view="monthly" aria-pressed="true"' in dom
        and 'class="output-waveform"' in dom,
        "weekly stats render stored buckets": 'data-stats-view="weekly" aria-pressed="true"' in weekly_dom
        and 'aria-label="GitHub週次活動"' in weekly_dom
        and weekly_dom.count('class="wave-point is-commits"') == 12,
        "browser console has no errors or missing resources": all(
            "ERROR:CONSOLE" not in output and "Failed to load resource" not in output
            for output in (chrome_stderr, weekly_stderr, selected_stderr)
        ),
    }
    if actionable_count > 0:
        checks["snapshot action identifies the recorded work item"] = (
            "Snapshot上の確認候補" in primary_action
            and 'class="gate-item-owner"' in primary_action
            and 'class="gate-item-reason"' in primary_action
        )
    if selected_count > 0:
        checks["selected gate shows repository and reason"] = (
            "KAFKA2306 / " in selected_gate_detail(selected_dom)
            and 'class="gate-item-reason"' in selected_gate_detail(selected_dom)
        )
    else:
        checks["selected empty gate is explicit"] = "対象は0件です。" in selected_gate_detail(selected_dom)

    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit("production snapshot browser E2E failed: " + ", ".join(failures))
    if snapshot_status is None:
        raise SystemExit("production snapshot browser E2E failed: snapshot status is missing")

    print(
        "production snapshot browser E2E: "
        f"{expected_repository_count} repositories, factory revision {factory['sourceRevision']}, "
        f"factory generatedAt {factory['generatedAt']}, snapshot status {snapshot_status.group(1)} PASS"
    )


if __name__ == "__main__":
    main()
