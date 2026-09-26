from pathlib import Path


def test_capability_readback_is_exact_revision_and_fail_closed():
    workflow = Path('.github/workflows/factory-capability-readback.yml').read_text(encoding='utf-8')

    assert "conclusion == 'action_required'" in workflow
    assert "github.event.workflow_run.conclusion == 'failure'" in workflow
    assert 'run.head_sha !== expectedSha' in workflow
    assert 'ref: expectedSha' in workflow
    assert 'source workflow has no explicit permissions block' in workflow
    assert 'actions: read' in workflow
    assert 'contents: read' in workflow
    assert 'actions: write' not in workflow
    assert 'contents: write' not in workflow


def test_failed_permission_fingerprints_route_to_readback_only():
    workflow = Path('.github/workflows/factory-capability-readback.yml').read_text(encoding='utf-8')

    assert 'listJobsForWorkflowRun' in workflow
    assert 'permission|authorization|commit generated lock|commit generated workflow' in workflow
    assert 'NO_WORK: source run' in workflow
    assert '- Sync gh-aw lock files' in workflow
