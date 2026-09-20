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


def intervention_is_automation_gap(reason: str) -> bool:
    """Routine intervention is a factory defect; genuine human authority is not."""
    normalized = _required(reason, "reason").lower()
    return normalized not in HUMAN_ONLY_REASONS


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
