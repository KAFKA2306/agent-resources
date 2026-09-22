from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable, Mapping


TERMINAL_STATES = frozenset({"VERIFIED"})
FAILURE_STATES = frozenset({"SELF_HEALING", "HUMAN_AUTHORITY"})


def derive_workline_state(signal: Mapping[str, object]) -> dict[str, object]:
    """Derive one fail-closed Control Tower workline from canonical evidence."""
    stage = str(signal.get("stage") or "UNKNOWN").upper()
    failure_class = str(signal.get("failure_class") or "").lower()
    conclusion = signal.get("conclusion")
    merged = bool(signal.get("merged"))
    deployed = signal.get("deployed")
    probed = signal.get("probed")

    if failure_class in {"legal_decision", "commercial_contract", "initial_external_auth", "irreversible_physical_action", "human_playtest"}:
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
    return max(0.0, (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds())


def build_factory_state(signals: Iterable[Mapping[str, object]], *, main_sha: str, generated_at: str) -> dict[str, object]:
    worklines = [derive_workline_state(signal) for signal in signals]
    completed = [w for w in worklines if w["state"] == "VERIFIED"]
    first_pass = [w for w in completed if not next(s for s in signals if str(s["id"]) == w["id"]).get("retried")]
    healable = [s for s in signals if s.get("failure_class") and not s.get("human_authority")]
    healed = [s for s in healable if s.get("self_healed") is True]
    interventions = [s for s in signals if s.get("human_intervention") is True]
    failures = Counter(str(s.get("failure_class")) for s in signals if s.get("failure_class"))
    lead = [_seconds(w.get("startedAt"), w.get("updatedAt")) for w in completed]
    lead = [x for x in lead if x is not None]
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
        "failurePareto": [{"failureClass": k, "count": v} for k, v in failures.most_common()],
        "worklines": worklines,
    }
