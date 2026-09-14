#!/usr/bin/env python3
"""Deterministic comparison for bounded recurring-research provider evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DECISIONS = {"KEEP_CURRENT", "REALLOCATE", "INCONCLUSIVE", "UNAVAILABLE"}
COMPLETED = "COMPLETED"
VALID_STATUSES = {COMPLETED, "UNAVAILABLE", "UNVERIFIED", "FAILED"}
VALID_RESULTS = {"MATERIAL_DELTA", "NO_MATERIAL_DELTA", "UNAVAILABLE", "UNVERIFIED", "FAILED"}

HIGHER_IS_BETTER = (
    "primary_source_ratio",
    "fresh_source_count",
    "contradictions_detected",
)
LOWER_IS_BETTER = (
    "stale_or_duplicate_results",
    "unverifiable_claims",
    "newest_source_age_hours",
    "input_context_bytes",
    "repeated_static_context_bytes",
    "unnecessary_reads",
    "heavy_research_invocations",
    "human_interventions",
    "handoff_failures",
    "skipped_or_delayed_executions",
    "duplicate_executions",
)
REQUIRED_METRICS = HIGHER_IS_BETTER + LOWER_IS_BETTER


class ContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_provider(
    provider: dict[str, Any],
    window: dict[str, str],
    previous_source_revisions: set[tuple[str, str]],
) -> None:
    name = provider.get("name")
    _require(isinstance(name, str) and name.strip(), "provider.name is required")
    route = provider.get("route")
    _require(isinstance(route, str) and route.strip(), f"{name}: route is required")
    status = provider.get("status")
    result = provider.get("result")
    _require(status in VALID_STATUSES, f"{name}: invalid status")
    _require(result in VALID_RESULTS, f"{name}: invalid result")
    _require(provider.get("observation_window") == window, f"{name}: observation window mismatch")

    if status != COMPLETED:
        _require(
            result in {"UNAVAILABLE", "UNVERIFIED", "FAILED"},
            f"{name}: incomplete provider cannot claim a completed result",
        )
        return

    _require(
        result in {"MATERIAL_DELTA", "NO_MATERIAL_DELTA"},
        f"{name}: completed provider needs a material/no-material result",
    )
    metrics = provider.get("metrics")
    _require(isinstance(metrics, dict), f"{name}: metrics are required")
    for key in REQUIRED_METRICS:
        value = metrics.get(key)
        _require(
            isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0,
            f"{name}: metric {key} must be a non-negative number",
        )
    _require(metrics["primary_source_ratio"] <= 1, f"{name}: primary_source_ratio must be <= 1")

    sources = provider.get("sources")
    _require(isinstance(sources, list), f"{name}: sources must be a list")
    identities: set[tuple[str, str]] = set()
    for source in sources:
        _require(isinstance(source, dict), f"{name}: source entries must be objects")
        url = source.get("url")
        revision = source.get("revision")
        _require(isinstance(url, str) and url.startswith("https://"), f"{name}: source URL must be https")
        _require(isinstance(revision, str) and revision.strip(), f"{name}: source revision is required")
        identity = (url.rstrip("/"), revision)
        _require(identity not in identities, f"{name}: duplicate source/revision {identity!r}")
        _require(
            identity not in previous_source_revisions,
            f"{name}: previous source/revision cannot be recounted as current delta {identity!r}",
        )
        identities.add(identity)
        _require(isinstance(source.get("primary"), bool), f"{name}: source.primary must be boolean")
        _require(isinstance(source.get("contradiction"), bool), f"{name}: source.contradiction must be boolean")

    expected_fresh = len(sources)
    expected_contradictions = sum(bool(source["contradiction"]) for source in sources)
    expected_primary_ratio = (
        sum(bool(source["primary"]) for source in sources) / len(sources)
        if sources
        else 0.0
    )
    _require(
        metrics["fresh_source_count"] == expected_fresh,
        f"{name}: fresh_source_count must equal unique current-delta sources",
    )
    _require(
        metrics["contradictions_detected"] == expected_contradictions,
        f"{name}: contradictions_detected must match preserved contradiction evidence",
    )
    _require(
        abs(metrics["primary_source_ratio"] - expected_primary_ratio) < 1e-9,
        f"{name}: primary_source_ratio must be derived from current-delta sources",
    )

    if result == "NO_MATERIAL_DELTA":
        _require(not sources, f"{name}: NO_MATERIAL_DELTA cannot contain current-delta sources")


def _dominates(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, bool]:
    """Return (a_non_worse, a_strictly_better) across the canonical dimensions."""
    a_metrics = a["metrics"]
    b_metrics = b["metrics"]
    non_worse = True
    strict = False
    for key in HIGHER_IS_BETTER:
        av, bv = a_metrics[key], b_metrics[key]
        non_worse &= av >= bv
        strict |= av > bv
    for key in LOWER_IS_BETTER:
        av, bv = a_metrics[key], b_metrics[key]
        non_worse &= av <= bv
        strict |= av < bv
    return bool(non_worse), strict


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload.get("version") == 1, "version must be 1")
    task = payload.get("task")
    _require(isinstance(task, dict), "task is required")
    task_id = task.get("id")
    _require(isinstance(task_id, str) and task_id.strip(), "task.id is required")
    static_digest = task.get("static_context_sha256")
    _require(
        isinstance(static_digest, str)
        and len(static_digest) == 64
        and all(c in "0123456789abcdef" for c in static_digest),
        "task.static_context_sha256 must be lowercase sha256",
    )
    _require(isinstance(task.get("current_delta_since"), str), "task.current_delta_since is required")
    previous_entries = task.get("previous_source_revisions", [])
    _require(
        isinstance(previous_entries, list),
        "task.previous_source_revisions must be a list",
    )
    previous_source_revisions: set[tuple[str, str]] = set()
    for entry in previous_entries:
        _require(isinstance(entry, dict), "previous source revisions must be objects")
        url = entry.get("url")
        revision = entry.get("revision")
        _require(
            isinstance(url, str) and url.startswith("https://"),
            "previous source URL must be https",
        )
        _require(
            isinstance(revision, str) and revision.strip(),
            "previous source revision is required",
        )
        identity = (url.rstrip("/"), revision)
        _require(
            identity not in previous_source_revisions,
            f"duplicate previous source/revision {identity!r}",
        )
        previous_source_revisions.add(identity)
    owner = task.get("owner_repository")
    _require(isinstance(owner, str) and owner.count("/") == 1, "task.owner_repository must be owner/repo")
    issue_number = task.get("handoff_issue")
    _require(isinstance(issue_number, int) and issue_number > 0, "task.handoff_issue must be a positive integer")

    window = payload.get("observation_window")
    _require(
        isinstance(window, dict)
        and isinstance(window.get("start"), str)
        and isinstance(window.get("end"), str)
        and window["start"] < window["end"],
        "observation_window start/end are required",
    )

    providers = payload.get("providers")
    _require(isinstance(providers, list) and len(providers) == 2, "exactly two provider routes are required")
    names = [provider.get("name") for provider in providers if isinstance(provider, dict)]
    _require(len(names) == 2 and len(set(names)) == 2, "provider names must be unique")
    for provider in providers:
        _require(isinstance(provider, dict), "provider entries must be objects")
        _validate_provider(provider, window, previous_source_revisions)

    current_name = payload.get("current_provider")
    candidate_name = payload.get("candidate_provider")
    by_name = {provider["name"]: provider for provider in providers}
    _require(current_name in by_name, "current_provider must name a provider")
    _require(candidate_name in by_name and candidate_name != current_name, "candidate_provider must name the other provider")
    current = by_name[current_name]
    candidate = by_name[candidate_name]

    incomplete = [p for p in providers if p["status"] != COMPLETED]
    if incomplete:
        decision = "UNAVAILABLE" if any(p["status"] == "UNAVAILABLE" for p in incomplete) else "INCONCLUSIVE"
        reasons = [f"{p['name']}:{p['status']}" for p in incomplete]
    else:
        candidate_non_worse, candidate_strict = _dominates(candidate, current)
        current_non_worse, current_strict = _dominates(current, candidate)
        if candidate_non_worse and candidate_strict:
            decision = "REALLOCATE"
            reasons = ["candidate strictly dominates current provider across observed dimensions"]
        elif current_non_worse:
            decision = "KEEP_CURRENT"
            reasons = [
                "current provider dominates candidate"
                if current_strict
                else "providers are tied on all observed dimensions"
            ]
        else:
            decision = "INCONCLUSIVE"
            reasons = ["observed dimensions trade off; no provider dominates"]

    transition = payload.get("schedule_transition")
    if decision == "REALLOCATE":
        _require(isinstance(transition, dict), "REALLOCATE requires schedule_transition")
        old_id = transition.get("stop_schedule_id")
        new_id = transition.get("start_schedule_id")
        _require(isinstance(old_id, str) and old_id, "stop_schedule_id is required")
        _require(isinstance(new_id, str) and new_id, "start_schedule_id is required")
        _require(old_id != new_id, "old and new schedule IDs must differ")
        _require(transition.get("stop_before_start") is True, "REALLOCATE requires stop_before_start=true")
    elif transition is not None:
        _require(isinstance(transition, dict), "schedule_transition must be an object")
        if transition.get("stop_schedule_id") and transition.get("start_schedule_id"):
            _require(
                transition["stop_schedule_id"] != transition["start_schedule_id"],
                "schedule IDs must differ",
            )

    contradictions = [
        {
            "provider": provider["name"],
            "url": source["url"],
            "revision": source["revision"],
        }
        for provider in providers
        if provider["status"] == COMPLETED
        for source in provider["sources"]
        if source["contradiction"]
    ]

    evidence_digest = _sha256_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return {
        "version": 1,
        "task_id": task_id,
        "owner_repository": owner,
        "handoff_issue": issue_number,
        "observation_window": window,
        "current_provider": current_name,
        "candidate_provider": candidate_name,
        "decision": decision,
        "reasons": reasons,
        "contradictions": contradictions,
        "provider_states": {
            provider["name"]: {
                "status": provider["status"],
                "result": provider["result"],
            }
            for provider in providers
        },
        "evidence_sha256": evidence_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = evaluate(payload)
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
