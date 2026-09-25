from __future__ import annotations

import argparse
import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen

from dashboard.benchmark_selection import select_benchmark_candidates


@dataclass(frozen=True)
class RepositorySnapshot:
    repository: str
    revision: str
    description: str
    topics: tuple[str, ...]
    readme: str
    pushed_at: str | None
    stars: int | None
    forks: int | None
    open_issues: int | None


@dataclass(frozen=True)
class LocalEvidence:
    path: str
    marker: str | None = None


@dataclass(frozen=True)
class LocalCapabilityRule:
    implementation: tuple[LocalEvidence, ...]
    wiring: tuple[LocalEvidence, ...]


CAPABILITY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("self_heal", ("self-heal", "self healing", "autofix", "auto-fix", "repair agent", "failure repair")),
    ("provider_reroute", ("model router", "provider router", "llm router", "model fallback", "provider fallback")),
    ("release_recovery", ("automatic rollback", "deployment rollback", "production recovery", "release automation", "progressive delivery")),
    ("review_automation", ("code review agent", "pull request review", "automated review", "review bot")),
    ("agent_orchestration", ("multi-agent", "agent orchestration", "coding agent", "software factory", "agent workflow")),
    ("memory_context", ("long-term memory", "agent memory", "context engineering", "knowledge graph", "memory layer")),
    ("ci_runner_acceleration", ("github actions runner", "self-hosted runner", "ci acceleration", "build cache", "remote cache", "workflow runner")),
)

LOCAL_CAPABILITY_RULES: dict[str, LocalCapabilityRule] = {
    "self_heal": LocalCapabilityRule(
        implementation=(LocalEvidence(".github/workflows/factory-repair-agent.yml", "Apply deterministic repair"),),
        wiring=(LocalEvidence("dashboard/factory_runtime.py", "factory-repair-agent.yml/dispatches"),),
    ),
    "provider_reroute": LocalCapabilityRule(
        implementation=(LocalEvidence(".github/workflows/factory-provider-reroute.yml", "createWorkflowDispatch"),),
        wiring=(LocalEvidence("dashboard/factory_control.py", "provider_unavailable"),),
    ),
    "release_recovery": LocalCapabilityRule(
        implementation=(LocalEvidence(".github/workflows/factory-production-recovery.yml", "Create isolated fix-forward revert"),),
        wiring=(LocalEvidence(".github/workflows/factory-evidence-observer.yml", "Verify Dashboard Release"),),
    ),
    "review_automation": LocalCapabilityRule(
        implementation=(LocalEvidence("skills/development/workflow/code-review"),),
        wiring=(LocalEvidence("plugins/issue-resolution-collaboration/.codex-plugin/plugin.json"),),
    ),
    "agent_orchestration": LocalCapabilityRule(
        implementation=(LocalEvidence("plugins/issue-resolution-collaboration/.codex-plugin/plugin.json"),),
        wiring=(LocalEvidence("plugins/issue-resolution-collaboration"),),
    ),
    "memory_context": LocalCapabilityRule(
        implementation=(LocalEvidence("dashboard/factory_reflection.py"),),
        wiring=(LocalEvidence(".github/workflows/factory-reflection.yml", "dashboard.factory_reflection"),),
    ),
}


def infer_capability(text: str) -> tuple[str, tuple[str, ...]]:
    normalized = " ".join(text.lower().split())
    best: tuple[int, int, str, tuple[str, ...]] | None = None
    for order, (capability, terms) in enumerate(CAPABILITY_TERMS):
        hits = tuple(term for term in terms if term in normalized)
        if not hits:
            continue
        candidate = (len(hits), -order, capability, hits)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None:
        return "UNVERIFIED", ()
    return best[2], best[3]


def _matches(root: Path, evidence: LocalEvidence) -> bool:
    target = root / evidence.path
    if not target.exists():
        return False
    if evidence.marker is None:
        return True
    if not target.is_file():
        return False
    return evidence.marker in target.read_text(encoding="utf-8", errors="replace")


def classify_local_status(root: Path, capability: str) -> str:
    rule = LOCAL_CAPABILITY_RULES.get(capability)
    if rule is None:
        return "UNVERIFIED"
    implementation = all(_matches(root, item) for item in rule.implementation)
    if not implementation:
        return "MISSING"
    wiring = all(_matches(root, item) for item in rule.wiring)
    return "EXISTING" if wiring else "DISCONNECTED"


def _request_json(url: str) -> Mapping[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "agent-resources-factory-benchmark/2",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("GitHub response is not an object")
    return payload


def fetch_repository_snapshot(repository: str) -> RepositorySnapshot:
    encoded = quote(repository, safe="/")
    metadata = _request_json(f"https://api.github.com/repos/{encoded}")
    default_branch = metadata.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise ValueError(f"{repository} has no default branch evidence")

    commit = _request_json(
        f"https://api.github.com/repos/{encoded}/commits/{quote(default_branch, safe='')}"
    )
    revision = commit.get("sha")
    if not isinstance(revision, str) or len(revision) < 7:
        raise ValueError(f"{repository} has no exact default-branch revision")

    readme = ""
    try:
        readme_payload = _request_json(f"https://api.github.com/repos/{encoded}/readme")
        raw = readme_payload.get("content")
        if isinstance(raw, str):
            readme = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        readme = ""

    topics = metadata.get("topics")
    normalized_topics = tuple(str(value) for value in topics) if isinstance(topics, list) else ()
    return RepositorySnapshot(
        repository=repository,
        revision=revision,
        description=str(metadata.get("description") or ""),
        topics=normalized_topics,
        readme=readme[:120_000],
        pushed_at=str(metadata.get("pushed_at")) if metadata.get("pushed_at") else None,
        stars=metadata.get("stargazers_count") if isinstance(metadata.get("stargazers_count"), int) else None,
        forks=metadata.get("forks_count") if isinstance(metadata.get("forks_count"), int) else None,
        open_issues=metadata.get("open_issues_count") if isinstance(metadata.get("open_issues_count"), int) else None,
    )


def _sort_key(row: Mapping[str, object]) -> tuple[int, int, str]:
    window_order = {"daily": 0, "monthly": 1, "weekly": 2}
    window = str(row.get("ranking_window") or "")
    rank = row.get("rank")
    return (
        window_order.get(window, 9),
        rank if isinstance(rank, int) else 10_000,
        str(row.get("repository") or "").lower(),
    )


def analyze_entries(
    entries: Sequence[Mapping[str, object]],
    *,
    root: Path,
    limit: int,
    loader: Callable[[str], RepositorySnapshot] = fetch_repository_snapshot,
) -> tuple[list[dict[str, object]], list[str]]:
    rows = [dict(row) for row in entries]
    repositories: list[str] = []
    for row in sorted(rows, key=_sort_key):
        repository = row.get("repository")
        if not isinstance(repository, str) or not repository or row.get("benchmark_revision"):
            continue
        if repository not in repositories:
            repositories.append(repository)
        if len(repositories) >= limit:
            break

    failures: list[str] = []
    for repository in repositories:
        try:
            snapshot = loader(repository)
        except Exception as exc:
            failures.append(f"{repository}:{type(exc).__name__}:{exc}")
            for row in rows:
                if row.get("repository") == repository and not row.get("benchmark_revision"):
                    row["activity_evidence"] = "UNVERIFIED"
                    row["reason"] = f"analysis_unverified:{type(exc).__name__}"
            continue

        evidence_text = "\n".join(
            [snapshot.description, " ".join(snapshot.topics), snapshot.readme]
        )
        capability, hits = infer_capability(evidence_text)
        local_status = classify_local_status(root, capability)
        activity = (
            f"pushed_at={snapshot.pushed_at or 'UNVERIFIED'};"
            f"stars={snapshot.stars if snapshot.stars is not None else 'UNVERIFIED'};"
            f"forks={snapshot.forks if snapshot.forks is not None else 'UNVERIFIED'};"
            f"open_issues={snapshot.open_issues if snapshot.open_issues is not None else 'UNVERIFIED'}"
        )
        for row in rows:
            if row.get("repository") != repository or row.get("benchmark_revision"):
                continue
            row["benchmark_revision"] = snapshot.revision
            row["activity_evidence"] = activity
            row["capability"] = capability
            row["local_status"] = local_status
            if capability == "UNVERIFIED":
                row["decision"] = "REJECT"
                row["reason"] = "no_factory_capability_detected"
                row["last_evaluated_revision"] = snapshot.revision
            else:
                row["decision"] = "CANDIDATE"
                row["reason"] = "readme_terms:" + ",".join(hits)

    return rows, failures


def build_candidate_snapshot(entries: Sequence[Mapping[str, object]]) -> dict[str, object]:
    decisions = select_benchmark_candidates(
        entries,
        relevant_capabilities=[name for name, _ in CAPABILITY_TERMS],
    )
    actionable = [
        asdict(item)
        for item in decisions
        if item.local_status in {"MISSING", "DISCONNECTED"}
    ]
    return {
        "schema_version": 1,
        "candidates": actionable,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="dashboard/oss-benchmark-ledger.json")
    parser.add_argument("--candidates", default="dashboard/oss-benchmark-candidates.json")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    ledger_path = Path(args.ledger)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("benchmark ledger entries must be a list")

    analyzed, failures = analyze_entries(
        entries,
        root=Path(args.root),
        limit=args.limit,
    )
    ledger_path.write_text(
        json.dumps({"schema_version": 1, "entries": analyzed[-1000:]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    candidate_path = Path(args.candidates)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(build_candidate_snapshot(analyzed), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    analyzed_count = sum(1 for row in analyzed if row.get("benchmark_revision"))
    status = "PASS" if not failures else ("PARTIAL" if analyzed_count else "UNVERIFIED")
    print(json.dumps({"status": status, "analyzed": analyzed_count, "failures": failures}))
    return 0 if analyzed_count or not entries else 2


if __name__ == "__main__":
    raise SystemExit(main())
