from pathlib import Path

from dashboard.benchmark_analysis import (
    RepositorySnapshot,
    analyze_entries,
    build_candidate_snapshot,
    classify_local_status,
    infer_capability,
)


def test_infers_factory_capability_from_repository_evidence():
    capability, hits = infer_capability(
        "Multi-agent coding agent orchestration with agent workflow support."
    )
    assert capability == "agent_orchestration"
    assert "multi-agent" in hits


def test_local_status_separates_disconnected_from_existing(tmp_path: Path):
    implementation = tmp_path / ".github/workflows/factory-repair-agent.yml"
    implementation.parent.mkdir(parents=True)
    implementation.write_text("Apply deterministic repair", encoding="utf-8")

    assert classify_local_status(tmp_path, "self_heal") == "DISCONNECTED"

    runtime = tmp_path / "dashboard/factory_runtime.py"
    runtime.parent.mkdir()
    runtime.write_text("factory-repair-agent.yml/dispatches", encoding="utf-8")

    assert classify_local_status(tmp_path, "self_heal") == "EXISTING"


def test_analysis_pins_exact_revision_and_suppresses_existing_capability(tmp_path: Path):
    plugin = tmp_path / "plugins/issue-resolution-collaboration/.codex-plugin/plugin.json"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("{}", encoding="utf-8")

    rows = [
        {
            "repository": "example/agents",
            "ranking_window": "daily",
            "rank": 1,
            "benchmark_revision": None,
            "capability": "UNVERIFIED",
            "local_status": "UNVERIFIED",
            "decision": "PENDING_REVIEW",
            "last_evaluated_revision": None,
        }
    ]

    def loader(repository: str) -> RepositorySnapshot:
        return RepositorySnapshot(
            repository=repository,
            revision="abcdef1234567890",
            description="Multi-agent coding agent",
            topics=(),
            readme="Agent orchestration for coding agents.",
            pushed_at="2026-09-26T00:00:00Z",
            stars=100,
            forks=10,
            open_issues=2,
        )

    analyzed, failures = analyze_entries(
        rows,
        root=tmp_path,
        limit=5,
        loader=loader,
    )

    assert failures == []
    assert analyzed[0]["benchmark_revision"] == "abcdef1234567890"
    assert analyzed[0]["capability"] == "agent_orchestration"
    assert analyzed[0]["local_status"] == "EXISTING"
    assert build_candidate_snapshot(analyzed)["candidates"] == []


def test_missing_capability_becomes_actionable_candidate(tmp_path: Path):
    rows = [
        {
            "repository": "example/release",
            "ranking_window": "monthly",
            "rank": 1,
            "benchmark_revision": None,
            "capability": "UNVERIFIED",
            "local_status": "UNVERIFIED",
            "decision": "PENDING_REVIEW",
            "last_evaluated_revision": None,
        }
    ]

    def loader(repository: str) -> RepositorySnapshot:
        return RepositorySnapshot(
            repository=repository,
            revision="1234567890abcdef",
            description="Automatic rollback and production recovery",
            topics=(),
            readme="",
            pushed_at=None,
            stars=None,
            forks=None,
            open_issues=None,
        )

    analyzed, failures = analyze_entries(
        rows,
        root=tmp_path,
        limit=5,
        loader=loader,
    )
    candidate = build_candidate_snapshot(analyzed)["candidates"][0]

    assert failures == []
    assert analyzed[0]["local_status"] == "MISSING"
    assert candidate["repository"] == "example/release"
    assert candidate["benchmark_revision"] == "1234567890abcdef"


def test_quota_aware_auto_fallback_maps_to_provider_reroute():
    capability, hits = infer_capability(
        "Quota-aware auto-fallback rotates away from exhausted providers."
    )

    assert capability == "provider_reroute"
    assert "auto-fallback" in hits


def test_provider_reroute_is_disconnected_until_runtime_dispatch_is_wired(tmp_path: Path):
    workflow = tmp_path / ".github/workflows/factory-provider-reroute.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("createWorkflowDispatch", encoding="utf-8")

    control = tmp_path / "dashboard/factory_control.py"
    control.parent.mkdir()
    control.write_text("provider_unavailable", encoding="utf-8")

    assert classify_local_status(tmp_path, "provider_reroute") == "DISCONNECTED"

    runtime = tmp_path / "dashboard/factory_runtime.py"
    runtime.write_text("factory-provider-reroute.yml/dispatches", encoding="utf-8")

    assert classify_local_status(tmp_path, "provider_reroute") == "EXISTING"


def test_unrelated_revision_is_marked_evaluated_and_not_reproposed(tmp_path: Path):
    rows = [
        {
            "repository": "example/unrelated",
            "ranking_window": "daily",
            "rank": 1,
            "benchmark_revision": None,
            "capability": "UNVERIFIED",
            "local_status": "UNVERIFIED",
            "decision": "PENDING_REVIEW",
            "last_evaluated_revision": None,
        }
    ]

    def loader(repository: str) -> RepositorySnapshot:
        return RepositorySnapshot(
            repository=repository,
            revision="9999999999999999",
            description="A tiny CSS color picker",
            topics=("css",),
            readme="Color utilities.",
            pushed_at=None,
            stars=5,
            forks=1,
            open_issues=0,
        )

    analyzed, failures = analyze_entries(
        rows,
        root=tmp_path,
        limit=5,
        loader=loader,
    )

    assert failures == []
    assert analyzed[0]["decision"] == "REJECT"
    assert analyzed[0]["last_evaluated_revision"] == "9999999999999999"
    assert build_candidate_snapshot(analyzed)["candidates"] == []
