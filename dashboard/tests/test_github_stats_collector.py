import unittest
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.github_stats import _search_total, _week_windows, collect_github_stats


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
        self.assertEqual(len(payload["weekly"]), 12)
        self.assertEqual(payload["weekly"][0]["weekStart"], "2026-05-25")
        self.assertEqual(payload["weekly"][-1]["weekStart"], "2026-08-10")
        self.assertEqual(payload["weekly"][-1]["weekEnd"], "2026-08-13")
        self.assertTrue(payload["weekly"][-1]["partial"])

    def test_closed_months_reuse_previous_dashboard_and_only_current_month_refreshes(self):
        now = datetime(2026, 8, 13, 11, 42, tzinfo=ZoneInfo("Asia/Tokyo"))
        previous_monthly = [
            {
                "month": f"2026-{month:02d}",
                "commits": 100 + month,
                "prsCreated": 20 + month,
                "prsMerged": 18 + month,
                "issuesCreated": 15 + month,
                "issuesClosed": 12 + month,
                "partial": False,
            }
            for month in range(1, 8)
        ]
        previous_dashboard = {
            "stats": {
                "owner": "KAFKA2306",
                "scope": "public",
                "timezone": "Asia/Tokyo",
                "monthly": previous_monthly,
            }
        }
        sleeps = []
        payload = collect_github_stats(
            now=now,
            request_fn=self.request_fn,
            request_interval=2.2,
            sleep_fn=sleeps.append,
            previous_stats=previous_dashboard,
            public_repository_count=127,
            week_count=1,
        )
        self.assertEqual(payload["publicRepositories"], 127)
        self.assertEqual(payload["monthly"][:7], previous_monthly)
        self.assertEqual(payload["monthly"][-1]["month"], "2026-08")
        self.assertTrue(payload["monthly"][-1]["partial"])
        self.assertEqual(len(self.queries), 11)
        self.assertEqual(sleeps, [2.2] * 11)
        self.assertTrue(self.queries[0].endswith("archived:true"))
        self.assertFalse(any("2026-01-01" in query or "2026-07-01" in query for query in self.queries))

    def test_partial_previous_month_is_not_reused(self):
        now = datetime(2026, 8, 13, 11, 42, tzinfo=ZoneInfo("Asia/Tokyo"))
        previous_dashboard = {
            "stats": {
                "owner": "KAFKA2306",
                "scope": "public",
                "timezone": "Asia/Tokyo",
                "monthly": [
                    {
                        "month": "2026-07",
                        "commits": 1,
                        "prsCreated": 1,
                        "prsMerged": 1,
                        "issuesCreated": 1,
                        "issuesClosed": 1,
                        "partial": True,
                    }
                ],
            }
        }
        collect_github_stats(
            start_month="2026-07",
            now=now,
            request_fn=self.request_fn,
            previous_stats=previous_dashboard,
            public_repository_count=127,
            week_count=1,
        )
        self.assertEqual(len(self.queries), 16)
        self.assertTrue(any("committer-date:2026-07-01..2026-07-31" in query for query in self.queries))

    def test_all_searches_are_public_only(self):
        now = datetime(2026, 1, 31, 23, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
        collect_github_stats(now=now, request_fn=self.request_fn)
        self.assertTrue(self.queries)
        self.assertTrue(all("is:public" in query.split() for query in self.queries))

    def test_request_interval_is_applied_without_slowing_unit_tests(self):
        sleeps = []
        now = datetime(2026, 1, 31, 23, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
        collect_github_stats(
            now=now,
            request_fn=self.request_fn,
            request_interval=2.2,
            sleep_fn=sleeps.append,
            week_count=1,
        )
        self.assertEqual(len(self.queries), 12)
        self.assertEqual(sleeps, [2.2] * 12)

    def test_week_windows_are_monday_started_and_current_week_is_partial(self):
        now = datetime(2026, 9, 5, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        windows = list(_week_windows(now, 3))
        self.assertEqual(
            windows,
            [
                ("2026-08-17", "2026-08-23", False),
                ("2026-08-24", "2026-08-30", False),
                ("2026-08-31", "2026-09-05", True),
            ],
        )

    def test_completed_weeks_reuse_previous_dashboard(self):
        now = datetime(2026, 9, 5, 9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        previous_weekly = []
        for start, end, partial in _week_windows(now, 3):
            if partial:
                continue
            previous_weekly.append(
                {
                    "weekStart": start,
                    "weekEnd": end,
                    "commits": 100,
                    "prsCreated": 20,
                    "prsMerged": 18,
                    "issuesCreated": 15,
                    "issuesClosed": 12,
                    "partial": False,
                }
            )
        previous_dashboard = {
            "stats": {
                "owner": "KAFKA2306",
                "scope": "public",
                "timezone": "Asia/Tokyo",
                "monthly": [],
                "weekly": previous_weekly,
            }
        }
        payload = collect_github_stats(
            start_month="2026-09",
            now=now,
            request_fn=self.request_fn,
            previous_stats=previous_dashboard,
            public_repository_count=127,
            week_count=3,
        )
        self.assertEqual(payload["weekly"][:2], previous_weekly)
        self.assertTrue(payload["weekly"][-1]["partial"])
        weekly_queries = [
            query for query in self.queries
            if "2026-08-17" in query or "2026-08-24" in query or "2026-08-31" in query
        ]
        self.assertTrue(all("2026-08-31" in query for query in weekly_queries))

    def test_rate_limit_uses_retry_after_then_succeeds(self):
        calls = 0
        sleeps = []

        def rate_limited_once(url, token=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise GitHubApiError(
                    "rate limited",
                    status=403,
                    headers={"Retry-After": "7"},
                    response_body='{"message":"secondary rate limit"}',
                )
            return {"total_count": 4, "incomplete_results": False}, {}

        total = _search_total(
            "issues",
            "author:KAFKA2306 is:issue is:public",
            request_fn=rate_limited_once,
            sleep_fn=sleeps.append,
        )
        self.assertEqual(total, 4)
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [7.0])

    def test_non_rate_403_is_not_retried(self):
        sleeps = []

        def forbidden(url, token=None):
            raise GitHubApiError(
                "forbidden",
                status=403,
                response_body='{"message":"Resource not accessible by integration"}',
            )

        with self.assertRaises(GitHubApiError):
            _search_total(
                "issues",
                "author:KAFKA2306 is:issue is:public",
                request_fn=forbidden,
                sleep_fn=sleeps.append,
            )
        self.assertEqual(sleeps, [])

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
