from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence
from urllib.parse import quote, urlparse

from dashboard.collectors.github_api import GitHubApiError, request_json, request_mutation
from dashboard.factory_control import decide_remediation, discover_work
from dashboard.factory_runtime import workflow_run_to_signal

GAP_CLASSES = frozenset(
    {
        "recurrent_failure",
        "stale_unverified",
        "open_loop",
        "capability_gap",
        "regression_pattern",
        "missing_evidence",
    }
)
SUBJECT_KINDS = frozenset(
    {"workflow", "issue", "pull_request", "deployment", "production", "capability"}
)
_ALLOWED_KEYS = frozenset(
    {
        "candidate_id",
        "gap_class",
        "repository",
        "subject_kind",
        "subject_id",
        "evidence_urls",
        "first_observed_at",
        "last_observed_at",
        "occurrences",
        "suggested_check",
        "memory_source",
        "private_context_included",
        "expected_revision",
    }
)
_FAILURE_CONCLUSIONS = frozenset({"failure", "timed_out", "action_required", "stale"})
_SUCCESS_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})


@dataclass(frozen=True)
class ReflectionCandidate:
    candidate_id: str
    gap_class: str
    repository: str
    subject_kind: str
    subject_id: str
    evidence_urls: tuple[str, ...]
    first_observed_at: str
    last_observed_at: str
    occurrences: int
    suggested_check: str
    memory_source: str = "graphiti"
    private_context_included: bool = False
    expected_revision: str | None = None


@dataclass(frozen=True)
class GroundingResult:
    status: str
    reason: str
    evidence: dict[str, object]


@dataclass(frozen=True)
class ProcessResult:
    status: str
    candidate_id: str
    grounding: str
    reason: str
    canonical_issue_number: int | None = None
    canonical_issue_url: str | None = None
    factory_task_id: str | None = None
    factory_action: str | None = None
    factory_reason: str | None = None


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def reflection_candidate_id(
    *, repository: str, gap_class: str, subject_kind: str, suggested_check: str
) -> str:
    payload = {
        "gap_class": _required_string(gap_class, "gap_class"),
        "repository": _required_string(repository, "repository").lower(),
        "subject_kind": _required_string(subject_kind, "subject_kind"),
        "suggested_check": _required_string(suggested_check, "suggested_check"),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"reflection:{digest}"


def _validate_public_github_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError("evidence_urls must contain only public github.com HTTPS URLs")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() != "kafka2306":
        raise ValueError("evidence_urls must point to KAFKA2306 public GitHub resources")
    return url


def parse_candidate(payload: Mapping[str, object]) -> ReflectionCandidate:
    extra = set(payload) - _ALLOWED_KEYS
    if extra:
        raise ValueError(f"unexpected reflection fields: {','.join(sorted(extra))}")

    gap_class = _required_string(payload.get("gap_class"), "gap_class")
    if gap_class not in GAP_CLASSES:
        raise ValueError(f"unsupported gap_class: {gap_class}")

    subject_kind = _required_string(payload.get("subject_kind"), "subject_kind")
    if subject_kind not in SUBJECT_KINDS:
        raise ValueError(f"unsupported subject_kind: {subject_kind}")

    repository = _required_string(payload.get("repository"), "repository")
    if not repository.startswith("KAFKA2306/") or repository.count("/") != 1:
        raise ValueError("repository must be an explicit KAFKA2306 owner/name")

    raw_urls = payload.get("evidence_urls")
    if not isinstance(raw_urls, Sequence) or isinstance(raw_urls, (str, bytes)) or not raw_urls:
        raise ValueError("evidence_urls must be a non-empty sequence")
    evidence_urls = tuple(
        _validate_public_github_url(_required_string(x, "evidence_url")) for x in raw_urls
    )

    occurrences = payload.get("occurrences")
    if not isinstance(occurrences, int) or occurrences < 1:
        raise ValueError("occurrences must be >= 1")
    if gap_class == "recurrent_failure" and occurrences < 3:
        raise ValueError("recurrent_failure requires at least 3 occurrences")

    if payload.get("memory_source") != "graphiti":
        raise ValueError("memory_source must be graphiti")
    if payload.get("private_context_included") is not False:
        raise ValueError("private_context_included must be false")

    suggested_check = _required_string(payload.get("suggested_check"), "suggested_check")
    expected_id = reflection_candidate_id(
        repository=repository,
        gap_class=gap_class,
        subject_kind=subject_kind,
        suggested_check=suggested_check,
    )
    candidate_id = _required_string(payload.get("candidate_id"), "candidate_id")
    if candidate_id != expected_id:
        raise ValueError("candidate_id does not match the stable contract")

    expected_revision = payload.get("expected_revision")
    if expected_revision is not None:
        expected_revision = _required_string(expected_revision, "expected_revision")

    return ReflectionCandidate(
        candidate_id=candidate_id,
        gap_class=gap_class,
        repository=repository,
        subject_kind=subject_kind,
        subject_id=_required_string(payload.get("subject_id"), "subject_id"),
        evidence_urls=evidence_urls,
        first_observed_at=_required_string(payload.get("first_observed_at"), "first_observed_at"),
        last_observed_at=_required_string(payload.get("last_observed_at"), "last_observed_at"),
        occurrences=occurrences,
        suggested_check=suggested_check,
        memory_source="graphiti",
        private_context_included=False,
        expected_revision=expected_revision,
    )


def _repo_parts(repository: str) -> tuple[str, str]:
    owner, name = repository.split("/", 1)
    return quote(owner, safe=""), quote(name, safe="")


def _api_url(candidate: ReflectionCandidate, suffix: str = "") -> str:
    owner, repository = _repo_parts(candidate.repository)
    return f"https://api.github.com/repos/{owner}/{repository}{suffix}"


def _ground_repository(candidate: ReflectionCandidate, token: str | None, request_fn: Callable):
    repo, _ = request_fn(_api_url(candidate), token)
    if not isinstance(repo, dict):
        raise ValueError("repository evidence is invalid")
    if repo.get("private") is not False:
        return GroundingResult(
            "UNVERIFIED", "repository_not_public", {"repository": candidate.repository}
        )
    if repo.get("archived") is True:
        return GroundingResult(
            "STALE_MEMORY", "repository_archived", {"repository": candidate.repository}
        )
    return None


def _run_id_from_url(url: str) -> int | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        idx = parts.index("runs")
    except ValueError:
        return None
    if idx + 1 >= len(parts):
        return None
    try:
        return int(parts[idx + 1])
    except ValueError:
        return None


def ground_candidate(
    candidate: ReflectionCandidate,
    *,
    token: str | None = None,
    request_fn: Callable = request_json,
) -> GroundingResult:
    try:
        repo_result = _ground_repository(candidate, token, request_fn)
        if repo_result is not None:
            return repo_result

        if candidate.gap_class == "recurrent_failure":
            observed: list[dict[str, object]] = []
            for url in candidate.evidence_urls:
                run_id = _run_id_from_url(url)
                if run_id is None:
                    return GroundingResult(
                        "UNVERIFIED", "non_workflow_recurrence_evidence", {}
                    )
                run, _ = request_fn(
                    _api_url(candidate, f"/actions/runs/{run_id}"), token
                )
                if not isinstance(run, dict):
                    return GroundingResult(
                        "UNVERIFIED", "workflow_run_evidence_invalid", {}
                    )
                observed.append(run)
            failures = [
                run for run in observed if run.get("conclusion") in _FAILURE_CONCLUSIONS
            ]
            if len(failures) < 3:
                return GroundingResult(
                    "STALE_MEMORY",
                    "recurrence_no_longer_supported",
                    {"failure_count": len(failures)},
                )
            return GroundingResult(
                "VERIFIED_GAP",
                "recurrent_failure_confirmed",
                {
                    "failure_count": len(failures),
                    "run_ids": [run.get("id") for run in failures],
                },
            )

        if candidate.subject_kind == "issue":
            issue, _ = request_fn(
                _api_url(candidate, f"/issues/{quote(candidate.subject_id, safe='')}"), token
            )
            if not isinstance(issue, dict):
                return GroundingResult("UNVERIFIED", "issue_evidence_invalid", {})
            if issue.get("state") == "open":
                return GroundingResult(
                    "VERIFIED_GAP",
                    "issue_still_open",
                    {"number": issue.get("number"), "url": issue.get("html_url")},
                )
            return GroundingResult(
                "STALE_MEMORY", "issue_closed", {"number": issue.get("number")}
            )

        if candidate.subject_kind == "pull_request":
            pr, _ = request_fn(
                _api_url(candidate, f"/pulls/{quote(candidate.subject_id, safe='')}"), token
            )
            if not isinstance(pr, dict):
                return GroundingResult("UNVERIFIED", "pull_request_evidence_invalid", {})
            if pr.get("state") == "open":
                return GroundingResult(
                    "VERIFIED_GAP",
                    "pull_request_still_open",
                    {"number": pr.get("number"), "url": pr.get("html_url")},
                )
            return GroundingResult(
                "STALE_MEMORY", "pull_request_closed", {"number": pr.get("number")}
            )

        if candidate.subject_kind == "workflow":
            run, _ = request_fn(
                _api_url(
                    candidate,
                    f"/actions/runs/{quote(candidate.subject_id, safe='')}",
                ),
                token,
            )
            if not isinstance(run, dict):
                return GroundingResult("UNVERIFIED", "workflow_run_evidence_invalid", {})
            if candidate.expected_revision and run.get("head_sha") != candidate.expected_revision:
                return GroundingResult(
                    "UNVERIFIED",
                    "revision_mismatch",
                    {
                        "expected": candidate.expected_revision,
                        "observed": run.get("head_sha"),
                    },
                )
            conclusion = run.get("conclusion")
            if conclusion in _FAILURE_CONCLUSIONS:
                return GroundingResult(
                    "VERIFIED_GAP",
                    "workflow_failure_still_observed",
                    {"run_id": run.get("id"), "head_sha": run.get("head_sha")},
                )
            if conclusion in _SUCCESS_CONCLUSIONS:
                return GroundingResult(
                    "STALE_MEMORY", "workflow_now_successful", {"run_id": run.get("id")}
                )
            return GroundingResult(
                "UNVERIFIED", "workflow_not_terminal", {"run_id": run.get("id")}
            )

        return GroundingResult("UNVERIFIED", "no_grounder_for_subject_kind", {})
    except (GitHubApiError, ValueError, TypeError) as exc:
        return GroundingResult(
            "UNVERIFIED", f"grounding_error:{type(exc).__name__}", {}
        )


def _marker(candidate_id: str) -> str:
    return f"<!-- factory-reflection:{candidate_id} -->"


def _find_existing_issue(
    candidate: ReflectionCandidate,
    *,
    token: str | None,
    request_fn: Callable,
) -> dict[str, object] | None:
    if candidate.subject_kind == "issue":
        issue, _ = request_fn(
            _api_url(candidate, f"/issues/{quote(candidate.subject_id, safe='')}"), token
        )
        if (
            isinstance(issue, dict)
            and issue.get("state") == "open"
            and "pull_request" not in issue
        ):
            return issue

    issues, _ = request_fn(
        _api_url(
            candidate,
            "/issues?state=all&per_page=100&sort=updated&direction=desc",
        ),
        token,
    )
    if not isinstance(issues, list):
        raise ValueError("issue list evidence is invalid")
    marker = _marker(candidate.candidate_id)
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        if marker in str(issue.get("body") or ""):
            return issue
    return None


def _factory_route(candidate: ReflectionCandidate) -> tuple[str, str, str]:
    owner, repository = candidate.repository.split("/", 1)
    signal = {
        "owner": owner,
        "repository": repository,
        "source_kind": "reflection",
        "source_id": candidate.candidate_id,
        "fingerprint": candidate.candidate_id.removeprefix("reflection:"),
        "kind": candidate.gap_class,
        "conclusion": "failure",
    }
    work = discover_work([signal])
    if len(work) != 1:
        raise ValueError("reflection candidate must produce exactly one Factory work item")
    item = work[0]
    decision = decide_remediation(failure_class=item.failure_class, attempt=0)
    return item.task_id, decision.action, decision.reason


def _issue_body(candidate: ReflectionCandidate, grounding: GroundingResult) -> str:
    evidence = "
".join(f"- {url}" for url in candidate.evidence_urls)
    return (
        f"{_marker(candidate.candidate_id)}
"
        "## Factory Reflection evidence

"
        f"- candidate: `{candidate.candidate_id}`
"
        f"- gap: `{candidate.gap_class}`
"
        f"- subject: `{candidate.subject_kind}:{candidate.subject_id}`
"
        f"- occurrences: `{candidate.occurrences}`
"
        f"- current grounding: `VERIFIED_GAP` / `{grounding.reason}`
"
        f"- acceptance check: `{candidate.suggested_check}`

"
        "## Current public evidence

"
        f"{evidence}

"
        "This work item was created from sanitized temporal memory, then re-grounded "
        "against current public evidence. Private memory content is not included.
"
    )


def process_candidate(
    payload: Mapping[str, object],
    *,
    token: str | None = None,
    request_fn: Callable = request_json,
    mutation_fn: Callable = request_mutation,
    execute: bool = True,
) -> ProcessResult:
    candidate = parse_candidate(payload)
    grounding = ground_candidate(candidate, token=token, request_fn=request_fn)
    if grounding.status != "VERIFIED_GAP":
        return ProcessResult(
            status=grounding.status,
            candidate_id=candidate.candidate_id,
            grounding=grounding.status,
            reason=grounding.reason,
        )

    factory_task_id, factory_action, factory_reason = _factory_route(candidate)
    existing = _find_existing_issue(candidate, token=token, request_fn=request_fn)
    if existing is not None:
        return ProcessResult(
            status="REUSED",
            candidate_id=candidate.candidate_id,
            grounding=grounding.status,
            reason="canonical_issue_exists",
            canonical_issue_number=(
                existing.get("number") if isinstance(existing.get("number"), int) else None
            ),
            canonical_issue_url=(
                existing.get("html_url")
                if isinstance(existing.get("html_url"), str)
                else None
            ),
            factory_task_id=factory_task_id,
            factory_action=factory_action,
            factory_reason=factory_reason,
        )

    if not execute:
        return ProcessResult(
            status="PLANNED",
            candidate_id=candidate.candidate_id,
            grounding=grounding.status,
            reason="would_create_canonical_issue",
            factory_task_id=factory_task_id,
            factory_action=factory_action,
            factory_reason=factory_reason,
        )

    title = (
        f"[Factory Reflection] {candidate.gap_class}: "
        f"{candidate.repository} {candidate.subject_kind} {candidate.subject_id}"
    )
    created, _ = mutation_fn(
        _api_url(candidate, "/issues"),
        token,
        method="POST",
        payload={"title": title, "body": _issue_body(candidate, grounding)},
    )
    if not isinstance(created, dict) or not isinstance(created.get("number"), int):
        raise ValueError("created issue response is invalid")
    return ProcessResult(
        status="CREATED",
        candidate_id=candidate.candidate_id,
        grounding=grounding.status,
        reason="canonical_issue_created",
        canonical_issue_number=created["number"],
        canonical_issue_url=(
            created.get("html_url") if isinstance(created.get("html_url"), str) else None
        ),
        factory_task_id=factory_task_id,
        factory_action=factory_action,
        factory_reason=factory_reason,
    )


def discover_recurrent_workflow_candidates(
    *,
    owner: str,
    repository: str,
    token: str | None = None,
    request_fn: Callable = request_json,
    min_occurrences: int = 3,
    limit: int = 50,
) -> list[dict[str, object]]:
    owner_q, repo_q = quote(owner, safe=""), quote(repository, safe="")
    base = f"https://api.github.com/repos/{owner_q}/{repo_q}"
    payload, _ = request_fn(
        f"{base}/actions/runs?status=completed&per_page={limit}", token
    )
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        raise ValueError("workflow run list is invalid")

    groups: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {}
    for run in runs:
        if (
            not isinstance(run, dict)
            or run.get("conclusion") not in _FAILURE_CONCLUSIONS
        ):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int):
            continue
        jobs_payload, _ = request_fn(
            f"{base}/actions/runs/{run_id}/jobs?per_page=100", token
        )
        jobs = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else None
        if not isinstance(jobs, list):
            continue
        signal = workflow_run_to_signal(
            owner=owner, repository=repository, run=run, jobs=jobs
        )
        groups.setdefault(str(signal["fingerprint"]), []).append((run, signal))

    candidates: list[dict[str, object]] = []
    for fingerprint, items in groups.items():
        if len(items) < min_occurrences:
            continue
        items.sort(
            key=lambda pair: str(
                pair[0].get("created_at") or pair[0].get("updated_at") or ""
            )
        )
        latest_run, _ = items[-1]
        evidence_urls = [
            str(run.get("html_url"))
            for run, _ in items
            if isinstance(run.get("html_url"), str) and run.get("html_url")
        ][-5:]
        suggested_check = f"workflow_failure:{fingerprint}"
        repo_name = f"{owner}/{repository}"
        candidate_id = reflection_candidate_id(
            repository=repo_name,
            gap_class="recurrent_failure",
            subject_kind="workflow",
            suggested_check=suggested_check,
        )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "gap_class": "recurrent_failure",
                "repository": repo_name,
                "subject_kind": "workflow",
                "subject_id": str(latest_run.get("id")),
                "evidence_urls": evidence_urls,
                "first_observed_at": str(
                    items[0][0].get("created_at") or items[0][0].get("updated_at")
                ),
                "last_observed_at": str(
                    latest_run.get("created_at") or latest_run.get("updated_at")
                ),
                "occurrences": len(items),
                "suggested_check": suggested_check,
                "memory_source": "graphiti",
                "private_context_included": False,
                "expected_revision": latest_run.get("head_sha"),
            }
        )
    return candidates


def golden_issue_probe(
    *,
    repository: str,
    issue_number: int,
    token: str | None = None,
    request_fn: Callable = request_json,
) -> ProcessResult:
    evidence_url = f"https://github.com/{repository}/issues/{issue_number}"
    suggested_check = f"issue_open:{issue_number}"
    now = datetime.now(timezone.utc).isoformat()
    candidate = {
        "candidate_id": reflection_candidate_id(
            repository=repository,
            gap_class="open_loop",
            subject_kind="issue",
            suggested_check=suggested_check,
        ),
        "gap_class": "open_loop",
        "repository": repository,
        "subject_kind": "issue",
        "subject_id": str(issue_number),
        "evidence_urls": [evidence_url],
        "first_observed_at": now,
        "last_observed_at": now,
        "occurrences": 1,
        "suggested_check": suggested_check,
        "memory_source": "graphiti",
        "private_context_included": False,
    }
    return process_candidate(
        candidate, token=token, request_fn=request_fn, execute=False
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-json")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--repository", default="KAFKA2306/agent-resources")
    parser.add_argument("--probe-issue", type=int)
    parser.add_argument("--observe-only", action="store_true")
    args = parser.parse_args(argv)
    token = os.getenv("GITHUB_TOKEN")

    if args.probe_issue:
        result = golden_issue_probe(
            repository=args.repository,
            issue_number=args.probe_issue,
            token=token,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0 if result.status in {"REUSED", "PLANNED", "STALE_MEMORY"} else 2

    payload_text = args.candidate_json or os.getenv(
        "FACTORY_REFLECTION_CANDIDATE_JSON"
    )
    if payload_text:
        result = process_candidate(
            json.loads(payload_text),
            token=token,
            execute=not args.observe_only,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return (
            0
            if result.status
            in {"REUSED", "CREATED", "PLANNED", "STALE_MEMORY"}
            else 2
        )

    if args.scheduled:
        owner, repository = args.repository.split("/", 1)
        candidates = discover_recurrent_workflow_candidates(
            owner=owner,
            repository=repository,
            token=token,
        )
        results = [
            asdict(
                process_candidate(
                    candidate,
                    token=token,
                    execute=not args.observe_only,
                )
            )
            for candidate in candidates
        ]
        print(
            json.dumps(
                {"candidates": candidates, "results": results},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    parser.error("provide --candidate-json, --scheduled, or --probe-issue")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
