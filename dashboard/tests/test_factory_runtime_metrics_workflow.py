from pathlib import Path


def test_runtime_metrics_workflow_is_read_only_and_fail_closed():
    workflow = Path(".github/workflows/factory-runtime-metrics.yml").read_text(encoding="utf-8")

    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "actions: write" not in workflow
    assert "contents: write" not in workflow
    assert 'raise SystemExit("workflow_runs evidence is missing")' in workflow
    assert 'raise SystemExit("no observed queue timing evidence")' in workflow
    assert 'run.get("created_at")' in workflow
    assert 'run.get("run_started_at")' in workflow
    assert '"meanQueueTimeSeconds"' in workflow
    assert '"queueTimeP50Seconds"' in workflow
    assert '"queueTimeP95Seconds"' in workflow
