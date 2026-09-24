from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dashboard.collectors.github_api import atomic_write_json, request_json

DEFAULT_REPOSITORY = "KAFKA2306/agent-resources"
DEFAULT_CANONICAL_ISSUE = 381
PAGES_URL = "https://kafka2306.github.io/agent-resources/"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_parts(repository: str) -> tuple[str, str]:
    parts = repository.split("/", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError("repository must be owner/name")
    return parts[0].strip(), parts[1].strip()


def _file_exists(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _read_text(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _normalize_issue(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("canonical issue response is invalid")
    number = raw.get("number")
    title = raw.get("title")
    state = raw.get("state")
    url = raw.get("html_url")
    updated_at = raw.get("updated_at")
    if not isinstance(number, int) or not title or not state or not url or not updated_at:
        raise ValueError("canonical issue response is incomplete")
    return {
        "number": number,
        "title": title,
        "state": state,
        "updatedAt": updated_at,
        "url": url,
    }


def _normalize_pull_requests(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise ValueError("pull request response is invalid")
    items = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("pull request item is invalid")
        number = item.get("number")
        title = item.get("title")
        url = item.get("html_url")
        updated_at = item.get("updated_at")
        head = item.get("head")
        head_sha = head.get("sha") if isinstance(head, dict) else None
        if not isinstance(number, int) or not title or not url or not updated_at or not head_sha:
            raise ValueError("pull request item is incomplete")
        items.append(
            {
                "number": number,
                "title": title,
                "draft": bool(item.get("draft")),
                "headSha": head_sha,
                "updatedAt": updated_at,
                "url": url,
            }
        )
    items.sort(key=lambda item: (str(item["updatedAt"]), int(item["number"])), reverse=True)
    return items


def _workflow_snapshot(
    raw: object,
    *,
    exact_sha: str,
    workflow_exists: bool,
    response_name: str,
) -> dict[str, object]:
    runs = raw.get("workflow_runs") if isinstance(raw, dict) else None
    if not isinstance(runs, list):
        raise ValueError(f"{response_name} workflow response is invalid")

    exact = [run for run in runs if isinstance(run, dict) and run.get("head_sha") == exact_sha]
    run = exact[0] if exact else None
    if run is None:
        return {
            "state": "EXISTING" if workflow_exists else "MISSING",
            "runId": None,
            "headSha": exact_sha,
            "status": None,
            "conclusion": None,
            "url": None,
        }

    status = run.get("status")
    conclusion = run.get("conclusion")
    state = "VERIFIED" if status == "completed" and conclusion == "success" else "UNVERIFIED"
    return {
        "state": state,
        "runId": run.get("id"),
        "headSha": run.get("head_sha"),
        "status": status,
        "conclusion": conclusion,
        "url": run.get("html_url"),
    }


def _observer_snapshot(raw: object, *, main_sha: str, workflow_exists: bool) -> dict[str, object]:
    return _workflow_snapshot(
        raw,
        exact_sha=main_sha,
        workflow_exists=workflow_exists,
        response_name="observer",
    )


def _capabilities(
    root: Path,
    observer_state: str,
    production_verification_state: str,
) -> list[dict[str, str]]:
    control = _read_text(root, "dashboard/factory_control.py")
    runtime = _read_text(root, "dashboard/factory_runtime.py")
    docs_workflow = _read_text(root, ".github/workflows/docs.yml")

    observer_exists = _file_exists(root, ".github/workflows/factory-evidence-observer.yml")
    merge_exists = _file_exists(root, ".github/workflows/factory-autonomous-merge.yml")
    release_probe_exists = _file_exists(root, ".github/workflows/dashboard-release-verify.yml")
    recovery_exists = _file_exists(root, ".github/workflows/factory-production-recovery.yml")
    pages_collector_exists = _file_exists(root, "dashboard/collectors/factory_evidence.py")
    pages_ui_exists = _file_exists(root, "docs/dashboard/factory-evidence.js")

    deterministic_policy = '"deterministic_test_failure": ("repair_agent", 1)' in control
    deterministic_executor = 'decision.action == "repair_agent"' in runtime
    reroute_policy = "ROUTABLE_FAILURES" in control
    reroute_executor = 'decision.action == "reroute"' in runtime
    diagnosis_executor = 'decision.action == "diagnose"' in runtime
    bounded_retry = "_POLICY =" in control and "retry_budget_exhausted" in control

    pages_pipeline = (
        pages_collector_exists
        and pages_ui_exists
        and "dashboard.collectors.factory_evidence" in docs_workflow
    )
    freshness_gate = "factory-state.json" in docs_workflow and "commits/main" in docs_workflow

    return [
        {
            "id": "observe-classify",
            "label": "Observe / classify",
            "state": observer_state if observer_exists else "MISSING",
        },
        {
            "id": "bounded-retry",
            "label": "Bounded retry",
            "state": "EXISTING" if bounded_retry else "MISSING",
        },
        {
            "id": "deterministic-repair",
            "label": "Deterministic repair",
            "state": (
                "EXISTING"
                if deterministic_policy and deterministic_executor
                else "DISCONNECTED"
                if deterministic_policy
                else "MISSING"
            ),
        },
        {
            "id": "autonomous-merge",
            "label": "Autonomous merge",
            "state": "EXISTING" if merge_exists else "MISSING",
        },
        {
            "id": "deploy-production-probe",
            "label": "Deploy / production probe",
            "state": production_verification_state if release_probe_exists else "MISSING",
        },
        {
            "id": "production-fix-forward",
            "label": "Production fix-forward",
            "state": "EXISTING" if recovery_exists else "MISSING",
        },
        {
            "id": "pages-current-evidence",
            "label": "Current evidence → Pages",
            "state": "EXISTING" if pages_pipeline else "DISCONNECTED",
        },
        {
            "id": "pages-freshness-gate",
            "label": "Pages freshness gate",
            "state": "EXISTING" if freshness_gate else "MISSING",
        },
        {
            "id": "general-diagnosis-patch",
            "label": "General diagnosis / patch",
            "state": "EXISTING" if diagnosis_executor else "MISSING",
        },
        {
            "id": "provider-runner-recovery",
            "label": "Runner / provider recovery",
            "state": (
                "EXISTING"
                if reroute_policy and reroute_executor
                else "DISCONNECTED"
                if reroute_policy
                else "MISSING"
            ),
        },
    ]


def collect_factory_evidence(
    *,
    repository: str = DEFAULT_REPOSITORY,
    canonical_issue: int = DEFAULT_CANONICAL_ISSUE,
    expected_revision: str,
    run_id: str,
    token: str | None = None,
    request_fn=request_json,
    repo_root: Path | str = Path("."),
    generated_at: str | None = None,
) -> dict[str, object]:
    owner, name = _repo_parts(repository)
    encoded_owner = quote(owner, safe="")
    encoded_name = quote(name, safe="")
    base = f"https://api.github.com/repos/{encoded_owner}/{encoded_name}"

    commit, _ = request_fn(f"{base}/commits/main", token)
    if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str):
        raise ValueError("current main response is invalid")
    main_sha = commit["sha"]
    if main_sha != expected_revision:
        raise RuntimeError(
            f"source revision is stale: checkout={expected_revision} current-main={main_sha}"
        )

    issue, _ = request_fn(f"{base}/issues/{canonical_issue}", token)
    pulls, _ = request_fn(
        f"{base}/pulls?state=open&base=main&sort=updated&direction=desc&per_page=20",
        token,
    )
    observer_runs, _ = request_fn(
        f"{base}/actions/workflows/factory-evidence-observer.yml/runs"
        "?branch=main&per_page=20",
        token,
    )
    release_runs, _ = request_fn(
        f"{base}/actions/workflows/dashboard-release-verify.yml/runs"
        "?branch=main&per_page=20",
        token,
    )

    root = Path(repo_root)
    observer = _observer_snapshot(
        observer_runs,
        main_sha=main_sha,
        workflow_exists=_file_exists(root, ".github/workflows/factory-evidence-observer.yml"),
    )
    production_verification = _workflow_snapshot(
        release_runs,
        exact_sha=main_sha,
        workflow_exists=_file_exists(root, ".github/workflows/dashboard-release-verify.yml"),
        response_name="production verification",
    )
    canonical = _normalize_issue(issue)
    if canonical["number"] != canonical_issue:
        raise ValueError("canonical issue number mismatch")

    return {
        "schemaVersion": "1.0.0",
        "generatedAt": generated_at or _utc_now(),
        "sourceRevision": main_sha,
        "authority": {
            "repository": repository,
            "defaultBranch": "main",
            "mainSha": main_sha,
        },
        "pages": {
            "url": PAGES_URL,
            "workflowRunId": str(run_id),
            "workflowRunUrl": f"https://github.com/{repository}/actions/runs/{run_id}",
            "sourceRevision": main_sha,
            "state": "UNVERIFIED",
        },
        "observer": observer,
        "productionVerification": production_verification,
        "canonicalIssue": canonical,
        "activePullRequests": _normalize_pull_requests(pulls),
        "capabilities": _capabilities(
            root,
            str(observer["state"]),
            str(production_verification["state"]),
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--canonical-issue", type=int, default=DEFAULT_CANONICAL_ISSUE)
    args = parser.parse_args(argv)

    payload = collect_factory_evidence(
        repository=args.repository,
        canonical_issue=args.canonical_issue,
        expected_revision=args.expected_revision,
        run_id=args.run_id,
        token=os.getenv("GITHUB_TOKEN"),
    )
    atomic_write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
