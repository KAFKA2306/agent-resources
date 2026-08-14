import json
import threading
import time
import unittest
from pathlib import Path

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.workflow_runs import collect_latest_workflow_runs

ROOT = Path(__file__).resolve().parents[1]
RUN_FIXTURE = ROOT / "fixtures" / "workflow-runs.api.example.json"


class WorkflowRunCollectorTest(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(RUN_FIXTURE.read_text(encoding="utf-8"))
        self.repository = {
            "id": "R_public_active",
            "owner": "example-owner",
            "name": "public-active",
            "visibility": "public",
        }

    def test_latest_run_preserves_status_and_conclusion(self):
        def request_fn(url, token=None):
            self.assertTrue(url.endswith("/actions/runs?per_page=1"))
            return self.payload, {}

        runs = collect_latest_workflow_runs([self.repository], request_fn=request_fn)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "completed")
        self.assertEqual(runs[0]["conclusion"], "success")
        self.assertEqual(runs[0]["runNumber"], 42)

    def test_in_progress_run_keeps_null_conclusion(self):
        payload = json.loads(json.dumps(self.payload))
        payload["workflow_runs"][0]["status"] = "in_progress"
        payload["workflow_runs"][0]["conclusion"] = None
        runs = collect_latest_workflow_runs(
            [self.repository], request_fn=lambda url, token=None: (payload, {})
        )
        self.assertEqual(runs[0]["status"], "in_progress")
        self.assertIsNone(runs[0]["conclusion"])

    def test_public_repository_fetches_are_concurrent_and_bounded(self):
        repositories = [
            dict(self.repository, id=f"R_{index}", name=f"repo-{index}") for index in range(8)
        ]
        lock = threading.Lock()
        active = 0
        max_active = 0

        def request_fn(url, token=None):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.03)
                return {"workflow_runs": []}, {}
            finally:
                with lock:
                    active -= 1

        runs = collect_latest_workflow_runs(
            repositories,
            request_fn=request_fn,
            concurrency=3,
        )
        self.assertEqual(runs, [])
        self.assertGreater(max_active, 1)
        self.assertLessEqual(max_active, 3)

    def test_private_repository_is_not_fetched(self):
        private = dict(self.repository, visibility="private")
        calls = []

        def request_fn(url, token=None):
            calls.append(url)
            return self.payload, {}

        self.assertEqual(collect_latest_workflow_runs([private], request_fn=request_fn), [])
        self.assertEqual(calls, [])

    def test_api_failure_is_not_converted_to_success(self):
        def request_fn(url, token=None):
            raise GitHubApiError("simulated failure")

        with self.assertRaises(GitHubApiError):
            collect_latest_workflow_runs([self.repository], request_fn=request_fn)

    def test_concurrency_must_remain_bounded(self):
        for invalid in (0, 9, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    collect_latest_workflow_runs([], concurrency=invalid)


if __name__ == "__main__":
    unittest.main()
