from pathlib import Path


def test_docs_workflow_persists_repository_operations_snapshot():
    workflow = Path(".github/workflows/docs.yml").read_text(encoding="utf-8")

    assert "dashboard.collectors.repository_operations" in workflow
    assert "--run-id \"${GITHUB_RUN_ID}\"" in workflow
    assert "docs/dashboard/repository-operations.json" in workflow
    assert "repository-operations.json" in workflow
    assert "operations.get(\"generatedAt\")" in workflow
    assert "operations.get(\"sourceRevision\")" in workflow
    assert "operations.get(\"runId\")" in workflow
