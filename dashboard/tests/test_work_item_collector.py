import json
import unittest
from pathlib import Path

from dashboard.collectors.work_items import collect_work_items

ROOT = Path(__file__).resolve().parents[1]
ISSUE_FIXTURE = ROOT / "fixtures" / "issues.api.example.json"


class WorkItemCollectorTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(ISSUE_FIXTURE.read_text(encoding="utf-8"))
        self.repository = {
            "id": "R_public_active",
            "owner": "example-owner",
            "name": "public-active",
            "url": "https://github.com/example-owner/public-active",
            "visibility": "public",
            "archived": False,
            "updatedAt": "2026-08-13T01:00:00Z",
            "group": "core",
        }

    def test_issue_and_pull_request_are_separated(self):
        items = collect_work_items([self.repository], fetcher=lambda url, token=None: self.raw)
        self.assertEqual(len(items), 2)
        by_number = {item["number"]: item for item in items}
        self.assertEqual(by_number[10]["kind"], "issue")
        self.assertEqual(by_number[11]["kind"], "pull_request")

    def test_closed_items_are_ignored_and_duplicates_removed(self):
        items = collect_work_items([self.repository], fetcher=lambda url, token=None: self.raw)
        self.assertEqual({item["number"] for item in items}, {10, 11})
        issue = next(item for item in items if item["number"] == 10)
        self.assertEqual(issue["updatedAt"], "2026-08-13T01:10:00Z")

    def test_private_repository_is_never_fetched_or_emitted(self):
        private = dict(self.repository, visibility="private")
        calls = []

        def fetcher(url, token=None):
            calls.append(url)
            return self.raw

        self.assertEqual(collect_work_items([private], fetcher=fetcher), [])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
