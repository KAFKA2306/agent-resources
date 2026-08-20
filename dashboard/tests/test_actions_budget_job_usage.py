import unittest
from datetime import date

from dashboard.collectors.actions_budget import _attach_recent_job_usage


class ActionsBudgetJobUsageTests(unittest.TestCase):
    def test_collects_jobs_only_for_recent_active_workflows(self):
        calls = []

        def fake_job_usage(
            owner,
            repo,
            workflow_id,
            start,
            end,
            token,
            request_fn=None,
            paginate_fn=None,
        ):
            calls.append((owner, repo, workflow_id, start, end, token))
            return {
                "run_count": 2,
                "job_count": 3,
                "jobs_by_runner_family": [{"name": "linux", "jobs": 3}],
                "jobs_by_runner_name": [],
                "jobs_by_runner_label": [{"name": "ubuntu-latest", "jobs": 3}],
                "billing_minutes_estimated": None,
                "billing_minutes_source": "not_estimated_from_jobs",
            }

        workflows = [
            {
                "id": 101,
                "name": "CI",
                "path": ".github/workflows/ci.yml",
                "month_to_date_runs": 5,
                "rolling_7d_runs": 2,
            },
            {
                "id": 102,
                "name": "Nightly",
                "path": ".github/workflows/nightly.yml",
                "month_to_date_runs": 1,
                "rolling_7d_runs": 0,
            },
        ]

        enriched = _attach_recent_job_usage(
            "KAFKA2306",
            "private-repo",
            workflows,
            date(2026, 8, 14),
            date(2026, 8, 20),
            "secret",
            object(),
            object(),
            fake_job_usage,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], 101)
        self.assertEqual(enriched[0]["rolling_7d_job_usage"]["job_count"], 3)
        self.assertIsNone(enriched[0]["rolling_7d_job_usage"]["billing_minutes_estimated"])
        self.assertIsNone(enriched[1]["rolling_7d_job_usage"])

    def test_no_job_collector_leaves_workflow_shape_unchanged(self):
        workflows = [
            {
                "id": 101,
                "name": "CI",
                "path": ".github/workflows/ci.yml",
                "month_to_date_runs": 5,
                "rolling_7d_runs": 2,
            }
        ]
        self.assertIs(
            _attach_recent_job_usage(
                "KAFKA2306",
                "private-repo",
                workflows,
                date(2026, 8, 14),
                date(2026, 8, 20),
                "secret",
                object(),
                object(),
                None,
            ),
            workflows,
        )


if __name__ == "__main__":
    unittest.main()
