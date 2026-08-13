import json
import unittest
from pathlib import Path

from dashboard.build import build_snapshot, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "dashboard.schema.json").read_text(encoding="utf-8"))


class DashboardBuildTest(unittest.TestCase):
    def setUp(self):
        self.public_repo = {
            "id": "R_public",
            "owner": "example-owner",
            "name": "zeta",
            "url": "https://github.com/example-owner/zeta",
            "group": "core",
            "visibility": "public",
            "archived": False,
            "updatedAt": "2026-08-13T01:00:00Z",
        }
        self.public_repo_a = {
            "id": "R_public_a",
            "owner": "example-owner",
            "name": "alpha",
            "url": "https://github.com/example-owner/alpha",
            "group": "other",
            "visibility": "public",
            "archived": False,
            "updatedAt": "2026-08-13T00:59:00Z",
        }
        self.private_repo = {
            "id": "R_private",
            "owner": "example-owner",
            "name": "secret",
            "url": "https://github.com/example-owner/secret",
            "group": "other",
            "visibility": "private",
            "archived": False,
            "updatedAt": "2026-08-13T01:01:00Z",
        }
        self.work_items = [
            {
                "id": "R_public:pull_request:11",
                "repositoryId": "R_public",
                "kind": "pull_request",
                "number": 11,
                "title": "review me",
                "url": "https://github.com/example-owner/zeta/pull/11",
                "state": "open",
                "updatedAt": "2026-08-13T01:10:00Z",
            },
            {
                "id": "R_private:issue:1",
                "repositoryId": "R_private",
                "kind": "issue",
                "number": 1,
                "title": "must not leak",
                "url": "https://github.com/example-owner/secret/issues/1",
                "state": "open",
                "updatedAt": "2026-08-13T01:11:00Z",
            },
        ]
        self.workflow_runs = [
            {
                "id": "R_public:workflow_run:9001",
                "repositoryId": "R_public",
                "runNumber": 42,
                "workflowName": "pages build",
                "status": "completed",
                "conclusion": "success",
                "url": "https://github.com/example-owner/zeta/actions/runs/9001",
                "createdAt": "2026-08-13T01:20:00Z",
                "updatedAt": "2026-08-13T01:21:00Z",
            }
        ]

    def build(self, repositories=None, work_items=None, workflow_runs=None):
        return build_snapshot(
            repositories if repositories is not None else [self.public_repo, self.public_repo_a, self.private_repo],
            work_items if work_items is not None else self.work_items,
            workflow_runs if workflow_runs is not None else self.workflow_runs,
            generated_at="2026-08-13T02:45:00Z",
        )

    def test_snapshot_filters_private_data_and_validates(self):
        snapshot = self.build()
        self.assertEqual([repo["name"] for repo in snapshot["repositories"]], ["alpha", "zeta"])
        self.assertNotIn("R_private", {item["repositoryId"] for item in snapshot["workItems"]})
        self.assertEqual(snapshot["summary"], {"repositoryCount": 2, "workItemCount": 2, "activityCount": 2})
        validate_snapshot(snapshot, SCHEMA)

    def test_workflow_run_becomes_done_work_item(self):
        snapshot = self.build()
        run = next(item for item in snapshot["workItems"] if item["kind"] == "workflow_run")
        self.assertEqual(run["state"], "completed")
        self.assertEqual(run["lane"], "done")
        self.assertEqual(run["laneReason"], "workflow_completed")

    def test_failed_workflow_becomes_failed_lane(self):
        failed = dict(self.workflow_runs[0], conclusion="failure")
        snapshot = self.build(workflow_runs=[failed])
        run = next(item for item in snapshot["workItems"] if item["kind"] == "workflow_run")
        self.assertEqual(run["state"], "failed")
        self.assertEqual(run["lane"], "failed")

    def test_activity_is_newest_first(self):
        snapshot = self.build()
        self.assertEqual(snapshot["activity"][0]["occurredAt"], "2026-08-13T01:21:00Z")
        self.assertEqual(snapshot["activity"][1]["occurredAt"], "2026-08-13T01:10:00Z")

    def test_output_order_is_stable_for_reversed_inputs(self):
        first = self.build()
        second = build_snapshot(
            list(reversed([self.public_repo, self.public_repo_a, self.private_repo])),
            list(reversed(self.work_items)),
            list(reversed(self.workflow_runs)),
            generated_at="2026-08-13T02:45:00Z",
        )
        self.assertEqual(first, second)

    def test_schema_failure_aborts_validation(self):
        snapshot = self.build()
        snapshot["repositories"][0]["color"] = "red"
        with self.assertRaises(ValueError):
            validate_snapshot(snapshot, SCHEMA)


if __name__ == "__main__":
    unittest.main()
