from dashboard.factory_runtime import workflow_run_to_signal


def _failed_jobs(step_name: str):
    return [
        {
            "steps": [
                {"name": step_name, "conclusion": "failure"},
            ]
        }
    ]


def test_workflow_failure_fingerprint_is_stable_across_revisions():
    base = {
        "id": 101,
        "name": "Validate Dashboard PR",
        "status": "completed",
        "conclusion": "failure",
        "run_attempt": 1,
        "html_url": "https://example.invalid/run/101",
    }
    first = workflow_run_to_signal(
        owner="KAFKA2306",
        repository="agent-resources",
        run={**base, "head_sha": "a" * 40},
        jobs=_failed_jobs("Run commit-time validation"),
    )
    second = workflow_run_to_signal(
        owner="KAFKA2306",
        repository="agent-resources",
        run={**base, "id": 202, "head_sha": "b" * 40},
        jobs=_failed_jobs("Run commit-time validation"),
    )

    assert first["fingerprint"] == second["fingerprint"]
    assert first["head_sha"] != second["head_sha"]
    assert first["source_id"] != second["source_id"]


def test_workflow_failure_fingerprint_changes_for_different_failed_step():
    run = {
        "id": 303,
        "name": "Validate Dashboard PR",
        "status": "completed",
        "conclusion": "failure",
        "head_sha": "c" * 40,
        "run_attempt": 1,
        "html_url": "https://example.invalid/run/303",
    }
    commit_time = workflow_run_to_signal(
        owner="KAFKA2306",
        repository="agent-resources",
        run=run,
        jobs=_failed_jobs("Run commit-time validation"),
    )
    readme = workflow_run_to_signal(
        owner="KAFKA2306",
        repository="agent-resources",
        run=run,
        jobs=_failed_jobs("Validate README resource links"),
    )

    assert commit_time["fingerprint"] != readme["fingerprint"]
