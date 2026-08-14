import threading
import time
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from dashboard.collectors.recent_activity import collect_recent_activity


class RecentActivityCollectorTest(unittest.TestCase):
    def setUp(self):
        self.repository = {
            "id": "R_public",
            "owner": "example-owner",
            "name": "public-repo",
            "visibility": "public",
        }
        self.now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)

    def test_collects_open_and_closed_issue_pr_activity_for_seven_days(self):
        calls = []
        issue_rows = [
            {
                "number": 7,
                "title": "still open",
                "html_url": "https://github.com/example-owner/public-repo/issues/7",
                "updated_at": "2026-08-12T10:00:00Z",
                "state": "open",
            },
            {
                "number": 8,
                "title": "merged change",
                "html_url": "https://github.com/example-owner/public-repo/pull/8",
                "updated_at": "2026-08-10T09:00:00Z",
                "state": "closed",
                "pull_request": {
                    "url": "https://api.github.com/repos/example-owner/public-repo/pulls/8"
                },
            },
            {
                "number": 1,
                "title": "too old",
                "html_url": "https://github.com/example-owner/public-repo/issues/1",
                "updated_at": "2026-08-01T00:00:00Z",
                "state": "closed",
            },
        ]

        def fetcher(url, token=None, item_key=None):
            calls.append((url, item_key))
            return issue_rows

        activity = collect_recent_activity(
            [self.repository],
            fetcher=fetcher,
            now=self.now,
            window_days=7,
        )

        self.assertEqual([item["kind"] for item in activity], ["issue", "pull_request"])
        self.assertNotIn("too old", {item["summary"] for item in activity})
        self.assertIn("merged change", {item["summary"] for item in activity})
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0][1])
        self.assertNotIn("/actions/runs", calls[0][0])

        issue_query = parse_qs(urlparse(calls[0][0]).query)
        self.assertEqual(issue_query["state"], ["all"])
        self.assertEqual(issue_query["sort"], ["updated"])
        self.assertEqual(issue_query["direction"], ["desc"])
        self.assertEqual(issue_query["since"], ["2026-08-06T12:00:00Z"])

    def test_public_repository_fetches_are_concurrent_and_bounded(self):
        repositories = [
            dict(self.repository, id=f"R_{index}", name=f"repo-{index}") for index in range(8)
        ]
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fetcher(url, token=None, item_key=None):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.03)
                return []
            finally:
                with lock:
                    active -= 1

        activity = collect_recent_activity(
            repositories,
            fetcher=fetcher,
            now=self.now,
            concurrency=3,
        )
        self.assertEqual(activity, [])
        self.assertGreater(max_active, 1)
        self.assertLessEqual(max_active, 3)

    def test_private_repository_is_never_fetched(self):
        private = dict(self.repository, visibility="private")
        calls = []

        def fetcher(url, token=None, item_key=None):
            calls.append(url)
            return []

        self.assertEqual(
            collect_recent_activity([private], fetcher=fetcher, now=self.now),
            [],
        )
        self.assertEqual(calls, [])

    def test_window_days_must_be_positive(self):
        with self.assertRaises(ValueError):
            collect_recent_activity([self.repository], now=self.now, window_days=0)

    def test_concurrency_must_remain_bounded(self):
        for invalid in (0, 9, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    collect_recent_activity([], now=self.now, concurrency=invalid)


if __name__ == "__main__":
    unittest.main()
