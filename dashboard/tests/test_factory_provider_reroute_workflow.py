from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_provider_reroute_preserves_exact_source_revision():
    source = (ROOT / ".github/workflows/factory-provider-reroute.yml").read_text(
        encoding="utf-8"
    )

    assert "const observedRoute = run.path || run.name;" in source
    assert "const rerouteRef = run.head_branch;" in source
    assert "if (refHead.sha !== expectedSha)" in source
    assert "ref: rerouteRef" in source


def test_deterministic_ops_audit_accepts_and_verifies_reroute_claim():
    source = (ROOT / ".github/workflows/github-models-ops-audit.yml").read_text(
        encoding="utf-8"
    )

    for field in ("source_run_id:", "failure_class:", "failed_route:", "head_sha:"):
        assert field in source
    assert "Validate provider reroute claim" in source
    assert 'if [ "$GITHUB_SHA" != "$EXPECTED_SHA" ]' in source


def test_factory_observer_watches_provider_route_and_alternate():
    source = (ROOT / ".github/workflows/factory-evidence-observer.yml").read_text(
        encoding="utf-8"
    )

    assert "KAFKA2306 public GitHub operations audit" in source
    assert "Deterministic Ops Audit" in source
