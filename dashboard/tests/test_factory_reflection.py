import unittest

from dashboard.factory_reflection import (
    discover_recurrent_workflow_candidates,
    parse_candidate,
    process_candidate,
    reflection_candidate_id,
)


def candidate(**overrides):
    base = {
        "gap_class": "open_loop",
        "repository": "KAFKA2306/agent-resources",
        "subject_kind": "issue",
        "subject_id": "381",
        "evidence_urls": ["https://github.com/KAFKA2306/agent-resources/issues/381"],
        "first_observed_at": "2026-09-20T00:00:00Z",
        "last_observed_at": "2026-09-25T00:00:00Z",
        "occurrences": 1,
        "suggested_check": "issue_open:381",
        "memory_source": "graphiti",
        "private_context_included": False,
    }
    base.update(overrides)
    base["candidate_id"] = reflection_candidate_id(
        repository=base["repository"],
        gap_class=base["gap_class"],
        subject_kind=base["subject_kind"],
        suggested_check=base["suggested_check"],
    )
    return base


class FactoryReflectionTests(unittest.TestCase):
    def test_private_or_extra_memory_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_candidate(candidate(discord_body="secret"))
        with self.assertRaises(ValueError):
            parse_candidate(candidate(private_context_included=True))
        with self.assertRaises(ValueError):
            parse_candidate(candidate(evidence_urls=["https://example.com/private"]))

    def test_stable_candidate_identity_ignores_latest_subject_id(self):
        first = candidate(subject_id="100")
        second = candidate(subject_id="200")
        self.assertEqual(first["candidate_id"], second["candidate_id"])

    def test_open_issue_is_grounded_and_reused_without_mutation(self):
        calls = []

        def request_fn(url, token=None):
            if url.endswith("/repos/KAFKA2306/agent-resources"):
                return {"private": False, "archived": False}, {}
            if url.endswith("/issues/381"):
                return {
                    "number": 381,
                    "state": "open",
                    "html_url": "https://github.com/KAFKA2306/agent-resources/issues/381",
                    "body": "canonical",
                }, {}
            raise AssertionError(url)

        result = process_candidate(
            candidate(),
            request_fn=request_fn,
            mutation_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        self.assertEqual(result.status, "REUSED")
        self.assertEqual(result.canonical_issue_number, 381)
        self.assertEqual(result.factory_action, "diagnose")
        self.assertIsNotNone(result.factory_task_id)
        self.assertEqual(calls, [])

    def test_closed_memory_does_not_create_issue(self):
        def request_fn(url, token=None):
            if url.endswith("/repos/KAFKA2306/agent-resources"):
                return {"private": False, "archived": False}, {}
            if url.endswith("/issues/381"):
                return {"number": 381, "state": "closed"}, {}
            raise AssertionError(url)

        result = process_candidate(candidate(), request_fn=request_fn)
        self.assertEqual(result.status, "STALE_MEMORY")

    def test_unverified_never_mutates(self):
        calls = []

        def request_fn(url, token=None):
            if url.endswith("/repos/KAFKA2306/agent-resources"):
                return {"private": True, "archived": False}, {}
            raise AssertionError(url)

        result = process_candidate(
            candidate(),
            request_fn=request_fn,
            mutation_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(calls, [])

    def test_recurrent_discovery_requires_three_matching_failure_fingerprints(self):
        runs = []
        jobs_by_id = {}
        for run_id in (101, 102, 103):
            runs.append(
                {
                    "id": run_id,
                    "name": "Validate Dashboard PR",
                    "status": "completed",
                    "conclusion": "failure",
                    "run_attempt": 1,
                    "head_sha": f"sha{run_id}",
                    "html_url": (
                        "https://github.com/KAFKA2306/agent-resources/"
                        f"actions/runs/{run_id}"
                    ),
                    "created_at": f"2026-09-2{run_id - 100}T00:00:00Z",
                }
            )
            jobs_by_id[run_id] = {
                "jobs": [
                    {
                        "steps": [
                            {
                                "name": "Run commit-time validation",
                                "conclusion": "failure",
                            }
                        ]
                    }
                ]
            }

        def request_fn(url, token=None):
            if "actions/runs?" in url:
                return {"workflow_runs": runs}, {}
            for run_id, jobs in jobs_by_id.items():
                if url.endswith(f"/actions/runs/{run_id}/jobs?per_page=100"):
                    return jobs, {}
            raise AssertionError(url)

        found = discover_recurrent_workflow_candidates(
            owner="KAFKA2306",
            repository="agent-resources",
            request_fn=request_fn,
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["gap_class"], "recurrent_failure")
        self.assertEqual(found[0]["occurrences"], 3)
        self.assertEqual(found[0]["subject_id"], "103")

    def test_recurrent_candidate_reuses_marker_issue(self):
        payload = candidate(
            gap_class="recurrent_failure",
            subject_kind="workflow",
            subject_id="103",
            occurrences=3,
            suggested_check="workflow_failure:deadbeef",
            evidence_urls=[
                "https://github.com/KAFKA2306/agent-resources/actions/runs/101",
                "https://github.com/KAFKA2306/agent-resources/actions/runs/102",
                "https://github.com/KAFKA2306/agent-resources/actions/runs/103",
            ],
        )
        marker = f"<!-- factory-reflection:{payload['candidate_id']} -->"

        def request_fn(url, token=None):
            if url.endswith("/repos/KAFKA2306/agent-resources"):
                return {"private": False, "archived": False}, {}
            if "/actions/runs/" in url and "/jobs" not in url:
                run_id = int(url.rsplit("/", 1)[-1])
                return {"id": run_id, "conclusion": "failure"}, {}
            if "/issues?state=all" in url:
                return [
                    {
                        "number": 500,
                        "state": "open",
                        "html_url": (
                            "https://github.com/KAFKA2306/agent-resources/issues/500"
                        ),
                        "body": marker,
                    }
                ], {}
            raise AssertionError(url)

        result = process_candidate(payload, request_fn=request_fn)
        self.assertEqual(result.status, "REUSED")
        self.assertEqual(result.canonical_issue_number, 500)


if __name__ == "__main__":
    unittest.main()
