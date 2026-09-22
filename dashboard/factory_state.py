from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable, Mapping


TERMINAL_STATES = frozenset({"VERIFIED"})
FAILURE_STATES = frozenset({"SELF_HEALING", "HUMAN_AUTHORITY"})
HUMAN_AUTHORITY_FAILURES = frozenset(
    {
        "legal_decision",
        "commercial_contract",
        "initial_external_auth",
        "irreversible_physical_action",
        "human_playtest",
    }
)


def derive_workline_state(signal: Mapping[str, object]) -> dict[str, object]:
    """Derive one fail-closed Control Tower workline from canonical evidence."""
    stage = str(signal.get("stage") or "UNKNOWN").upper()
    failure_class = str(signal.get("failure_class") or "").lower()
    conclusion = signal.get("conclusion")
    merged = bool(signal.get("merged"))
    deployed = signal.get("deployed")
    probed = signal.get("probed")

    if failure_class in HUMAN_AUTHORITY_FAILURES:
        state = "HUMAN_AUTHORITY"
    elif conclusion == "failure":
        state = "SELF_HEALING"
    elif conclusion not in {"success", None}:
        state = "UNVERIFIED"
    elif merged and deployed is True and probed is True:
        state = "VERIFIED"
    elif merged and deployed is True:
        state = "PROBING"
    elif merged:
        state = "DEPLOYING"
    elif conclusion == "success":
        state = "READY_TO_MERGE"
    else:
        state = "ACTIVE"

    return {
        "id": str(signal["id"]),
        "title": str(signal.get("title") or signal["id"]),
        "state": state,
        "stage": stage,
        "failureClass": failure_class or None,
        "headSha": signal.get("head_sha"),
        "runId": signal.get("run_id"),
        "artifactId": signal.get("artifact_id"),
        "startedAt": signal.get("started_at"),
        "updatedAt": signal.get("updated_at"),
    }


def _seconds(start: object, end: object) -> float | None:
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return max(
        0.0,
        (
            datetime.fromisoformat(end.replace("Z", "+00:00"))
            - datetime.fromisoformat(start.replace("Z", "+00:00"))
        ).total_seconds(),
    )


def build_factory_state(
    signals: Iterable[Mapping[str, object]], *, main_sha: str, generated_at: str
) -> dict[str, object]:
    """Build metrics from one immutable evidence snapshot.

    Collectors may provide generators. Materialize once so deriving worklines and
    metrics observes the same evidence instead of consuming the iterator twice.
    """
    evidence = list(signals)
    worklines = [derive_workline_state(signal) for signal in evidence]
    signal_by_id = {str(signal["id"]): signal for signal in evidence}
    completed = [workline for workline in worklines if workline["state"] == "VERIFIED"]
    first_pass = [
        workline
        for workline in completed
        if not signal_by_id[workline["id"]].get("retried")
    ]
    healable = [
        signal
        for signal in evidence
        if signal.get("failure_class")
        and str(signal.get("failure_class")).lower() not in HUMAN_AUTHORITY_FAILURES
    ]
    healed = [signal for signal in healable if signal.get("self_healed") is True]
    interventions = [
        signal for signal in evidence if signal.get("human_intervention") is True
    ]
    failures = Counter(
        str(signal.get("failure_class"))
        for signal in evidence
        if signal.get("failure_class")
    )
    lead = [
        _seconds(workline.get("startedAt"), workline.get("updatedAt"))
        for workline in completed
    ]
    lead = [seconds for seconds in lead if seconds is not None]
    total = len(worklines)

    return {
        "schemaVersion": "1.0.0",
        "generatedAt": generated_at,
        "factory": {"mainSha": main_sha},
        "metrics": {
            "e2eYield": len(completed) / total if total else None,
            "firstPassYield": len(first_pass) / len(completed) if completed else None,
            "selfHealRate": len(healed) / len(healable) if healable else None,
            "humanInterventionRate": len(interventions) / total if total else None,
            "meanLeadTimeSeconds": sum(lead) / len(lead) if lead else None,
        },
        "failurePareto": [
            {"failureClass": failure_class, "count": count}
            for failure_class, count in failures.most_common()
        ],
        "worklines": worklines,
    }
