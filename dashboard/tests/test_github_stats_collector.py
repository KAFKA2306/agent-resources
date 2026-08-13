import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.github_stats import _search_total, collect_github_stats


class GitHubStatsCollectorTest(unittest.TestCase):
    def setUp(self):
        self.queries = []

    def request_fn(self, url, token=None):
        query = parse_qs(urlparse(url).query)["q"][0]
        self.queries.append(query)
        self.assertIn("is:public", query.split())
        return {"total_count": len(self.queries), "incomplete_results": False}, {}

    def test_months_are_contiguous_and_current_month_is_partial(self):
        now = datetime(2026, 8, 13, 11, 42, tzinfo=ZoneInfo("Asia/Tokyo"))
        payload = collect_github_stats(now=now, request_fn=self.request_fn)
        self.assertEqual([row["month"] for row in payload["monthly"]], [f"2026-{month:02d}" for month in range(1, 9)])
        self.assertEqual([row["partial"] for row in payload["monthly"][:-1]], [False] * 7)
        self.assertTrue(payload["monthly"][-1]["partial"])
        self.assertEqual(payload["scope"], "public")
        self.assertEqual(payload["timezone"], "Asia/Tokyo")

    def test_all_searches_are_public_only(self):
        now = datetime(2026, 1, 31, 23, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
        collect_github_stats(now=now, request_fn=self.request_fn)
        self.assertTrue(self.queries)
        self.assertTrue(all("is:public" in query.split() for query in self.queries))

    def test_incomplete_search_fails_closed(self):
        def incomplete(url, token=None):
            return {"total_count": 99, "incomplete_results": True}, {}
        with self.assertRaises(GitHubApiError):
            _search_total("issues", "author:KAFKA2306 is:issue is:public", request_fn=incomplete)

    def test_missing_public_scope_is_rejected_before_request(self):
        called = False
        def should_not_run(url, token=None):
            nonlocal called
            called = True
            return {"total_count": 1, "incomplete_results": False}, {}
        with self.assertRaises(GitHubApiError):
            _search_total("commits", "author:KAFKA2306", request_fn=should_not_run)
        self.assertFalse(called)

    def test_future_start_month_is_rejected(self):
        now = datetime(2026, 8, 13, 11, 42, tzinfo=ZoneInfo("Asia/Tokyo"))
        with self.assertRaises(ValueError):
            collect_github_stats(start_month="2026-09", now=now, request_fn=self.request_fn)


if __name__ == "__main__":
    unittest.main()
