from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkDecision:
    repository: str
    benchmark_revision: str
    capability: str
    local_status: str
    decision: str
    reason: str


def select_benchmark_candidates(
    entries: Iterable[Mapping[str, object]],
    *,
    relevant_capabilities: Iterable[str],
) -> list[BenchmarkDecision]:
    """Return deterministic, not-yet-evaluated benchmark candidates.

    Ranking observations without an exact benchmark revision are evidence only and
    cannot enter capability selection. An unchanged revision that has already been
    evaluated is suppressed until new revision evidence arrives.
    """
    relevant = frozenset(str(value).strip() for value in relevant_capabilities if str(value).strip())
    selected: dict[tuple[str, str, str], BenchmarkDecision] = {}

    for row in entries:
        repository = _text(row.get("repository"))
        revision = _text(row.get("benchmark_revision"))
        capability = _text(row.get("capability"))
        local_status = _text(row.get("local_status")) or "UNVERIFIED"
        last_evaluated = _text(row.get("last_evaluated_revision"))

        if not repository or not revision or not capability or capability == "UNVERIFIED":
            continue
        if relevant and capability not in relevant:
            continue
        if last_evaluated == revision:
            continue

        key = (repository.lower(), revision, capability)
        selected.setdefault(
            key,
            BenchmarkDecision(
                repository=repository,
                benchmark_revision=revision,
                capability=capability,
                local_status=local_status,
                decision="EVALUATE",
                reason="new_relevant_benchmark_revision",
            ),
        )

    return [selected[key] for key in sorted(selected)]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
