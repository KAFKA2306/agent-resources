import unittest
from datetime import date

from dashboard.collectors.actions_job_usage import collect_workflow_job_usage


class FakeApi:
    def paginate(self, url, token=None, request_fn=None, item_key=None):
        if token != "secret":
            raise AssertionError("expected supplied token")
        if "/actions/workflows/101/runs?" in url:
            self._assert_window(url)
            if item_key != "workflow_runs":
                raise AssertionError("expected workflow_runs item key")
            return [{"id": 5001}, {"id": 5002}]
        if "/actions/runs/5001/jobs?" in url:
            if item_key != "jobs":
                raise AssertionError("expected jobs item key")
            return [
                {"runner_name": "GitHub Actions 1", "labels": ["ubuntu-latest"]},
                {"runner_name": "GitHub Actions 2", "labels": ["windows-2025"]},
            ]
        if "/actions/runs/5002/jobs?" in url:
            if item_key != "jobs":
                raise AssertionError("expected jobs item key")
            return [
                {"runner_name": "local-5070ti", "labels": ["self-hosted", "Windows", "X64"]},
                {"runner_name": None, "labels": []},
            ]
        raise AssertionError(f"unexpected URL: {url}")

    @staticmethod
    def _assert_window(url):
        if "created=2026-08-09..2026-08-15" not in url:
            raise AssertionError(f"unexpected date window: {url}")


class ActionsJobUsageTests(unittest.TestCase):
    def test_collects_job_and_runner_evidence_without_estimating_billing_minutes(self):
        api = FakeApi()
        payload = collect_workflow_job_usage(
            owner="KAFKA2306",
            repo="busy",
            workflow_id=101,
            start=date(2026, 8, 9),
            end=date(2026, 8, 15),
            token="secret",
            paginate_fn=api.paginate,
        )

        self.assertEqual(payload["run_count"], 2)
        self.assertEqual(payload["job_count"], 4)
        self.assertEqual(
            payload["jobs_by_runner_family"],
            [
                {"name": "linux", "jobs": 1},
                {"name": "self-hosted", "jobs": 1},
                {"name": "unknown", "jobs": 1},
                {"name": "windows", "jobs": 1},
            ],
        )
        self.assertEqual(
            payload["jobs_by_runner_name"],
            [
                {"name": "GitHub Actions 1", "jobs": 1},
                {"name": "GitHub Actions 2", "jobs": 1},
                {"name": "local-5070ti", "jobs": 1},
            ],
        )
        self.assertEqual(payload["billing_minutes_estimated"], None)
        self.assertEqual(payload["billing_minutes_source"], "not_estimated_from_jobs")


if __name__ == "__main__":
    unittest.main()
