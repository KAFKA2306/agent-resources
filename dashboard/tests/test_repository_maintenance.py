import unittest
from datetime import datetime, timedelta, timezone

from dashboard.operations.repository_maintenance import (
    collect_operations_inventory,
    scan_branch_hygiene,
)


class FakeClient:
    def __init__(self, *, branch="feature/old", protected=False, active_pr=False, ahead_by=0):
        self.branch = branch
        self.protected = protected
        self.active_pr = active_pr
        self.ahead_by = ahead_by
        self.deleted = []

    def list(self, url):
        self.assert_url = url
        return [
            {
                "name": self.branch,
                "protected": self.protected,
                "commit": {"sha": "a" * 40},
            }
        ]

    def get(self, url):
        if "/pulls?" in url:
            return [{"number": 1}] if self.active_pr else []
        if "/compare/" in url:
            return {"ahead_by": self.ahead_by}
        if "/commits/" in url:
            return {"commit": {"committer": {"date": "2026-06-01T00:00:00Z"}}}
        raise AssertionError(f"unexpected URL: {url}")

    def delete_ref(self, owner, repo, branch):
        self.deleted.append((owner, repo, branch))


class RepositoryMaintenanceTest(unittest.TestCase):
    def test_inventory_uses_agent_zone_topic_as_explicit_classification(self):
        raw = [
            {
                "node_id": "R_1",
                "name": "vrmine",
                "owner": {"login": "KAFKA2306"},
                "visibility": "public",
                "private": False,
                "archived": False,
                "default_branch": "main",
                "html_url": "https://github.com/KAFKA2306/vrmine",
                "updated_at": "2026-08-20T00:00:00Z",
                "topics": ["agent-zone-vr-3d", "unity"],
            },
            {
                "node_id": "R_2",
                "name": "private-repo",
                "owner": {"login": "KAFKA2306"},
                "visibility": "private",
                "private": True,
                "archived": False,
                "default_branch": "main",
                "html_url": "https://github.com/KAFKA2306/private-repo",
                "updated_at": "2026-08-20T00:00:00Z",
                "topics": [],
            },
        ]

        def fetcher(url, token=None):
            self.assertIn("/users/KAFKA2306/repos", url)
            return raw

        result = collect_operations_inventory(
            "KAFKA2306",
            fetcher=fetcher,
            collected_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(1, result["summary"]["repositoryCount"])
        self.assertEqual("vr-3d", result["repositories"][0]["group"])
        self.assertEqual("agent-zone-topic", result["repositories"][0]["classificationSource"])
        self.assertEqual("public-nonarchived-owned-repositories", result["scope"])

    def inventory(self):
        return {
            "schemaVersion": 1,
            "scope": "public-nonarchived-owned-repositories",
            "owner": "KAFKA2306",
            "collectedAt": "2026-08-21T00:00:00Z",
            "repositories": [
                {
                    "id": "R_1",
                    "name": "example",
                    "fullName": "KAFKA2306/example",
                    "url": "https://github.com/KAFKA2306/example",
                    "defaultBranch": "main",
                    "group": "agent-web",
                    "classificationSource": "agent-zone-topic",
                    "topics": ["agent-zone-agent-web"],
                    "updatedAt": "2026-08-20T00:00:00Z",
                }
            ],
            "summary": {"repositoryCount": 1, "classifiedCount": 1, "unclassifiedCount": 0},
        }

    def test_stale_merged_branch_requires_second_scan_before_delete(self):
        first_time = datetime(2026, 8, 21, 0, 0, tzinfo=timezone.utc)
        client = FakeClient()
        first_report, state = scan_branch_hygiene(
            self.inventory(),
            {"schemaVersion": 1, "candidates": {}},
            client,
            now=first_time,
            min_age_days=30,
            confirm_hours=24,
            apply=True,
        )
        self.assertEqual("candidate", first_report["branches"][0]["status"])
        self.assertEqual([], client.deleted)
        self.assertEqual(1, first_report["summary"]["candidateCount"])

        second_report, next_state = scan_branch_hygiene(
            self.inventory(),
            state,
            client,
            now=first_time + timedelta(hours=25),
            min_age_days=30,
            confirm_hours=24,
            apply=True,
        )
        self.assertEqual("deleted", second_report["branches"][0]["status"])
        self.assertEqual([("KAFKA2306", "example", "feature/old")], client.deleted)
        self.assertEqual({}, next_state["candidates"])
        self.assertEqual(1, second_report["summary"]["deletedCount"])

    def test_active_pull_request_blocks_candidate(self):
        report, state = scan_branch_hygiene(
            self.inventory(),
            {"schemaVersion": 1, "candidates": {}},
            FakeClient(active_pr=True),
            now=datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        self.assertEqual("blocked", report["branches"][0]["status"])
        self.assertEqual("active_pull_request", report["branches"][0]["reason"])
        self.assertEqual({}, state["candidates"])

    def test_unmerged_branch_blocks_candidate(self):
        report, state = scan_branch_hygiene(
            self.inventory(),
            {"schemaVersion": 1, "candidates": {}},
            FakeClient(ahead_by=2),
            now=datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        self.assertEqual("blocked", report["branches"][0]["status"])
        self.assertEqual("not_merged_into_default", report["branches"][0]["reason"])
        self.assertEqual({}, state["candidates"])

    def test_protected_branch_name_is_not_even_considered(self):
        report, state = scan_branch_hygiene(
            self.inventory(),
            {"schemaVersion": 1, "candidates": {}},
            FakeClient(branch="release/2026-08"),
            now=datetime(2026, 8, 21, tzinfo=timezone.utc),
        )
        self.assertEqual([], report["branches"])
        self.assertEqual({}, state["candidates"])


if __name__ == "__main__":
    unittest.main()
