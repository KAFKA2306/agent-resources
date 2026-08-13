import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from dashboard.collectors.recent_activity import collect_recent_activity


class RecentActivityCollectorTest(unittest.TestCase):
    def setUp(self):
        self.repository = {"id": "R_public", "owner": "example-owner", "name": "public-repo", "visibility": "public"}
        self.now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)

    def test_collects_open_closed_pr_and_workflow_activity_for_seven_days(self):
        calls = []
        issue_rows = [
            {"number": 7, "title": "still open", "html_url": "https://github.com/example-owner/public-repo/issues/7", "updated_at": "2026-08-12T10:00:00Z", "state": "open"},
            {"number": 8, "title": "merged change", "html_url": "https://github.com/example-owner/public-repo/pull/8", "updated_at": "2026-08-10T09:00:00Z", "state": "closed", "pull_request": {"url": "https://api.github.com/repos/example-owner/public-repo/pulls/8"}},
            {"number": 1, "title": "too old", "html_url": "https://github.com/example-owner/public-repo/issues/1", "updated_at": "2026-08-01T00:00:00Z", "state": "closed"},
        ]
        workflow_rows = [{"id": 9001, "name": "Pages", "html_url": "https://github.com/example-owner/public-repo/actions/runs/9001", "created_at": "2026-08-11T08:00:00Z"}]
        def fetcher(url, token=None, item_key=None):
            calls.append((url, item_key))
            return workflow_rows if item_key == "workflow_runs" else issue_rows
        activity = collect_recent_activity([self.repository], fetcher=fetcher, now=self.now, window_days=7)
        self.assertEqual([item["kind"] for item in activity], ["issue", "workflow_run", "pull_request"])
        self.assertNotIn("too old", {item["summary"] for item in activity})
        self.assertIn("merged change", {item["summary"] for item in activity})
        issue_query = parse_qs(urlparse(calls[0][0]).query)
        self.assertEqual(issue_query["state"], ["all"])
        self.assertEqual(issue_query["since"], ["2026-08-06T12:00:00Z"])
        workflow_query = parse_qs(urlparse(calls[1][0]).query)
        self.assertEqual(workflow_query["created"], ["2026-08-06T12:00:00Z..2026-08-13T12:00:00Z"])
        self.assertEqual(calls[1][1], "workflow_runs")

    def test_private_repository_is_never_fetched(self):
        private = dict(self.repository, visibility="private")
        calls = []
        def fetcher(url, token=None, item_key=None):
            calls.append(url)
            return []
        self.assertEqual(collect_recent_activity([private], fetcher=fetcher, now=self.now), [])
        self.assertEqual(calls, [])

    def test_window_days_must_be_positive(self):
        with self.assertRaises(ValueError):
            collect_recent_activity([self.repository], now=self.now, window_days=0)


if __name__ == "__main__":
    unittest.main()
