from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


HUMAN_ONLY_REASONS = frozenset(
    {
        "legal_decision",
        "commercial_contract",
        "initial_external_auth",
        "irreversible_physical_action",
        "human_playtest",
    }
)

ROUTABLE_FAILURES = frozenset({"unsupported_model", "provider_unavailable", "runner_unavailable"})

_POLICY = {
    "transient_network": ("retry_with_backoff", 2),
    "flaky_test": ("rerun_once", 1),
    "deterministic_test_failure": ("repair_agent", 1),
    "build_failure": ("repair_agent", 1),
    "merge_conflict": ("conflict_repair", 1),
    "permission_mismatch": ("capability_readback", 1),
    "artifact_failure": ("rebuild_artifact", 1),
    "deployment_failure": ("repair_or_retry_deploy", 1),
    "production_probe_failure": ("rollback_or_fix_forward", 1),
    "stale_process": ("cleanup_and_restart", 1),
    "stale_workspace": ("recreate_workspace", 1),
}


@dataclass(frozen=True)
class RouteCandidate:
    name: str
    capabilities: frozenset[str]
    available: bool = True
    approved: bool = True
    priority: int = 100


@dataclass(frozen=True)
class RemediationDecision:
    action: str
    terminal: bool
    reason: str
    route: str | None = None


@dataclass(frozen=True)
class WorkItem:
    task_id: str
    owner: str
    repository: str
    source_kind: str
    source_id: str
    fingerprint: str
    failure_class: str


@dataclass(frozen=True)
class VerificationDecision:
    status: str
    reason: str


def stable_task_id(
    *,
    owner: str,
    repository: str,
    source_kind: str,
    source_id: str,
    fingerprint: str,
) -> str:
    """Return a stable idempotency key for one observed work item."""
    values = {
        "fingerprint": _required(fingerprint, "fingerprint"),
        "owner": _required(owner, "owner").lower(),
        "repository": _required(repository, "repository").lower(),
        "source_id": _required(source_id, "source_id"),
        "source_kind": _required(source_kind, "source_kind"),
    }
    canonical = json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"factory:{digest[:24]}"


def classify_failure(signal: Mapping[str, object]) -> str:
    """Classify a structured failure without turning unknown state into success."""
    explicit = signal.get("kind")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()

    status = signal.get("http_status")
    if status in {408, 429, 500, 502, 503, 504}:
        return "transient_network"
    if status in {401, 403}:
        return "permission_mismatch"

    conclusion = signal.get("conclusion")
    if conclusion == "timed_out":
        return "runner_unavailable"

    return "unknown"


def discover_work(signals: Iterable[Mapping[str, object]]) -> list[WorkItem]:
    """Convert current failure evidence into deduplicated work items."""
    discovered: dict[str, WorkItem] = {}
    for signal in signals:
        conclusion = signal.get("conclusion")
        if conclusion in {"success", "neutral", "skipped"}:
            continue

        owner = _mapping_string(signal, "owner")
        repository = _mapping_string(signal, "repository")
        source_kind = _mapping_string(signal, "source_kind")
        source_id = _mapping_string(signal, "source_id")
        fingerprint = _mapping_string(signal, "fingerprint")
        failure_class = classify_failure(signal)
        task_id = stable_task_id(
            owner=owner,
            repository=repository,
            source_kind=source_kind,
            source_id=source_id,
            fingerprint=fingerprint,
        )
        discovered.setdefault(
            task_id,
            WorkItem(
                task_id=task_id,
                owner=owner,
                repository=repository,
                source_kind=source_kind,
                source_id=source_id,
                fingerprint=fingerprint,
                failure_class=failure_class,
            ),
        )
    return sorted(discovered.values(), key=lambda item: item.task_id)


def select_route(
    candidates: Iterable[RouteCandidate],
    *,
    required_capabilities: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> RouteCandidate | None:
    """Select only an approved, available route with all required capabilities."""
    required = frozenset(required_capabilities)
    excluded = frozenset(exclude)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.approved
        and candidate.available
        and candidate.name not in excluded
        and required.issubset(candidate.capabilities)
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda candidate: (candidate.priority, candidate.name))


def decide_remediation(
    *,
    failure_class: str,
    attempt: int,
    routes: Sequence[RouteCandidate] = (),
    required_capabilities: Iterable[str] = (),
    failed_route: str | None = None,
) -> RemediationDecision:
    """Choose the next bounded autonomous action for one failure."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")

    failure_class = _required(failure_class, "failure_class").lower()

    if failure_class in HUMAN_ONLY_REASONS:
        return RemediationDecision(
            action="external_authority",
            terminal=True,
            reason="machine_authority_absent",
        )

    if failure_class in ROUTABLE_FAILURES:
        selected = select_route(
            routes,
            required_capabilities=required_capabilities,
            exclude=([failed_route] if failed_route else ()),
        )
        if selected is not None:
            return RemediationDecision(
                action="reroute",
                terminal=False,
                reason=failure_class,
                route=selected.name,
            )
        return RemediationDecision(
            action="terminal_unverified",
            terminal=True,
            reason="no_approved_available_route",
        )

    policy = _POLICY.get(failure_class)
    if policy is None:
        return RemediationDecision(
            action="diagnose",
            terminal=False,
            reason="unknown_failure_requires_bounded_diagnosis",
        )

    action, max_attempts = policy
    if attempt < max_attempts:
        return RemediationDecision(
            action=action,
            terminal=False,
            reason=failure_class,
        )

    return RemediationDecision(
        action="terminal_unverified",
        terminal=True,
        reason="retry_budget_exhausted",
    )


def verify_evidence(
    *,
    expected_revision: str,
    evidence: Iterable[Mapping[str, object]],
    required_kinds: Iterable[str],
) -> VerificationDecision:
    """Verify exact-revision evidence and fail closed when evidence is incomplete."""
    revision = _required(expected_revision, "expected_revision")
    required = frozenset(_required(kind, "required_kind") for kind in required_kinds)
    by_kind: dict[str, Mapping[str, object]] = {}

    for item in evidence:
        kind = item.get("kind")
        if isinstance(kind, str) and kind:
            by_kind[kind] = item

    missing = sorted(required - by_kind.keys())
    if missing:
        return VerificationDecision("UNVERIFIED", f"missing:{','.join(missing)}")

    for kind in sorted(required):
        item = by_kind[kind]
        observed_revision = item.get("revision")
        if observed_revision != revision:
            return VerificationDecision("UNVERIFIED", f"revision_mismatch:{kind}")
        conclusion = item.get("conclusion")
        if conclusion == "failure":
            return VerificationDecision("FAIL", f"failed:{kind}")
        if conclusion != "success":
            return VerificationDecision("UNVERIFIED", f"unknown_conclusion:{kind}")

    return VerificationDecision("PASS", "all_required_evidence_verified")


def intervention_is_automation_gap(reason: str) -> bool:
    """Routine intervention is a factory defect; genuine human authority is not."""
    normalized = _required(reason, "reason").lower()
    return normalized not in HUMAN_ONLY_REASONS


def _mapping_string(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a non-empty string")
    return _required(value, name)


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
