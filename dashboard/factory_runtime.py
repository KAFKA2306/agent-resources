from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Sequence
from urllib.parse import quote

from dashboard.collectors.github_api import request_json, request_mutation
from dashboard.factory_control import (
    RemediationDecision,
    WorkItem,
    decide_remediation,
    discover_work,
)


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    action: str
    reason: str
    target: str | None = None


def _failed_step_names(jobs: Sequence[Mapping[str, object]]) -> list[str]:
    names: list[str] = []
    for job in jobs:
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            if step.get("conclusion") != "failure":
                continue
            name = step.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return sorted(set(names))


def classify_workflow_failure(
    run: Mapping[str, object],
    jobs: Sequence[Mapping[str, object]] = (),
) -> str:
    conclusion = run.get("conclusion")
    if conclusion == "timed_out":
        return "runner_unavailable"
    if conclusion == "action_required":
        return "permission_mismatch"
    if conclusion == "stale":
        return "stale_workspace"
    if conclusion != "failure":
        return "unknown"

    failed_steps = [name.lower() for name in _failed_step_names(jobs)]
    if any("flaky" in name for name in failed_steps):
        return "flaky_test"
    if any("build" in name for name in failed_steps):
        return "build_failure"
    if any("test" in name or "lint" in name or "type" in name for name in failed_steps):
        return "deterministic_test_failure"
    return "unknown"


def workflow_run_to_signal(
    *,
    owner: str,
    repository: str,
    run: Mapping[str, object],
    jobs: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    run_id = run.get("id")
    if not isinstance(run_id, int) or run_id < 1:
        raise ValueError("workflow run id is missing")

    conclusion = run.get("conclusion")
    status = run.get("status")
    if not isinstance(status, str) or not status:
        raise ValueError("workflow run status is missing")

    workflow_name = run.get("name")
    if not isinstance(workflow_name, str) or not workflow_name:
        raise ValueError("workflow run name is missing")

    failed_steps = _failed_step_names(jobs)
    fingerprint_payload = {
        "workflow": workflow_name,
        "conclusion": conclusion,
        "failedSteps": failed_steps,
        "headSha": run.get("head_sha"),
    }
    canonical = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    return {
        "owner": owner,
        "repository": repository,
        "source_kind": "workflow_run",
        "source_id": str(run_id),
        "fingerprint": fingerprint,
        "kind": classify_workflow_failure(run, jobs),
        "conclusion": conclusion,
        "status": status,
        "workflow_name": workflow_name,
        "run_attempt": run.get("run_attempt", 1),
        "head_sha": run.get("head_sha"),
        "url": run.get("html_url"),
        "failed_steps": failed_steps,
    }


def collect_workflow_run_signal(
    *,
    owner: str,
    repository: str,
    run_id: int,
    token: str | None = None,
    request_fn: Callable = request_json,
) -> dict[str, object]:
    encoded_owner = quote(owner, safe="")
    encoded_repository = quote(repository, safe="")
    base = f"https://api.github.com/repos/{encoded_owner}/{encoded_repository}"
    run, _ = request_fn(f"{base}/actions/runs/{run_id}", token)
    jobs_payload, _ = request_fn(f"{base}/actions/runs/{run_id}/jobs?per_page=100", token)
    jobs = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else None
    if not isinstance(run, dict) or not isinstance(jobs, list):
        raise ValueError("workflow evidence response shape is invalid")
    return workflow_run_to_signal(
        owner=owner,
        repository=repository,
        run=run,
        jobs=jobs,
    )


def execute_remediation(
    decision: RemediationDecision,
    work_item: WorkItem,
    *,
    token: str | None = None,
    mutation_fn: Callable = request_mutation,
) -> ExecutionResult:
    if decision.terminal:
        return ExecutionResult(
            status="TERMINAL",
            action=decision.action,
            reason=decision.reason,
        )

    if work_item.source_kind != "workflow_run":
        return ExecutionResult(
            status="DEFERRED",
            action=decision.action,
            reason="unsupported_source_kind",
        )

    if decision.action not in {"rerun_once", "rebuild_artifact"}:
        return ExecutionResult(
            status="DEFERRED",
            action=decision.action,
            reason="no_bounded_executor_for_action",
        )

    owner = quote(work_item.owner, safe="")
    repository = quote(work_item.repository, safe="")
    target = (
        f"https://api.github.com/repos/{owner}/{repository}"
        f"/actions/runs/{quote(work_item.source_id, safe='')}/rerun-failed-jobs"
    )
    mutation_fn(target, token, method="POST")
    return ExecutionResult(
        status="EXECUTED",
        action=decision.action,
        reason=decision.reason,
        target=target,
    )


def remediate_workflow_run(
    *,
    owner: str,
    repository: str,
    run_id: int,
    token: str | None = None,
    request_fn: Callable = request_json,
    mutation_fn: Callable = request_mutation,
) -> dict[str, object]:
    signal = collect_workflow_run_signal(
        owner=owner,
        repository=repository,
        run_id=run_id,
        token=token,
        request_fn=request_fn,
    )

    if signal.get("conclusion") in {"success", "neutral", "skipped"}:
        return {"status": "NO_WORK", "signal": signal}

    work = discover_work([signal])
    if not work:
        return {"status": "NO_WORK", "signal": signal}

    item = work[0]
    run_attempt = signal.get("run_attempt", 1)
    attempt = max((run_attempt if isinstance(run_attempt, int) else 1) - 1, 0)
    decision = decide_remediation(
        failure_class=item.failure_class,
        attempt=attempt,
    )
    execution = execute_remediation(
        decision,
        item,
        token=token,
        mutation_fn=mutation_fn,
    )
    return {
        "status": execution.status,
        "signal": signal,
        "workItem": asdict(item),
        "decision": asdict(decision),
        "execution": asdict(execution),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args(argv)

    result = remediate_workflow_run(
        owner=args.owner,
        repository=args.repository,
        run_id=args.run_id,
        token=os.getenv("GITHUB_TOKEN"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["status"] in {"NO_WORK", "EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
