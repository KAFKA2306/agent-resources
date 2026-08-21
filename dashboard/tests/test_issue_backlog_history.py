import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from dashboard.collectors.github_stats import collect_issue_backlog_history


class IssueBacklogHistoryTest(unittest.TestCase):
    def test_appends_direct_daily_snapshot_and_preserves_history(self):
        counts = {
            "user:KAFKA2306 is:issue is:open is:public": 628,
            "author:KAFKA2306 is:issue is:open is:public": 542,
        }

        def request_fn(url, token=None):
            query = parse_qs(urlparse(url).query)["q"][0]
            return {"total_count": counts[query], "incomplete_results": False}, {}

        previous = {
            "schemaVersion": 1,
            "owner": "KAFKA2306",
            "scope": "public",
            "timezone": "Asia/Tokyo",
            "snapshots": [
                {
                    "date": "2026-08-21",
                    "observedAt": "2026-08-21T09:17:00+09:00",
                    "allOpen": 611,
                    "authoredOpen": 526,
                }
            ],
        }
        now = datetime(2026, 8, 22, 9, 17, tzinfo=ZoneInfo("Asia/Tokyo"))
        payload = collect_issue_backlog_history(
            now=now,
            request_fn=request_fn,
            previous_history=previous,
        )

        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["owner"], "KAFKA2306")
        self.assertEqual(payload["scope"], "public")
        self.assertEqual(payload["timezone"], "Asia/Tokyo")
        self.assertEqual(
            payload["snapshots"],
            [
                previous["snapshots"][0],
                {
                    "date": "2026-08-22",
                    "observedAt": "2026-08-22T09:17:00+09:00",
                    "allOpen": 628,
                    "authoredOpen": 542,
                },
            ],
        )

    def test_same_day_snapshot_is_replaced_not_duplicated(self):
        counts = {
            "user:KAFKA2306 is:issue is:open is:public": 600,
            "author:KAFKA2306 is:issue is:open is:public": 500,
        }

        def request_fn(url, token=None):
            query = parse_qs(urlparse(url).query)["q"][0]
            return {"total_count": counts[query], "incomplete_results": False}, {}

        previous = {
            "schemaVersion": 1,
            "owner": "KAFKA2306",
            "scope": "public",
            "timezone": "Asia/Tokyo",
            "snapshots": [
                {
                    "date": "2026-08-22",
                    "observedAt": "2026-08-22T08:00:00+09:00",
                    "allOpen": 590,
                    "authoredOpen": 490,
                }
            ],
        }
        payload = collect_issue_backlog_history(
            now=datetime(2026, 8, 22, 9, 17, tzinfo=ZoneInfo("Asia/Tokyo")),
            request_fn=request_fn,
            previous_history=previous,
        )

        self.assertEqual(len(payload["snapshots"]), 1)
        self.assertEqual(payload["snapshots"][0]["allOpen"], 600)
        self.assertEqual(payload["snapshots"][0]["authoredOpen"], 500)

    def test_invalid_previous_history_is_not_reused(self):
        calls = 0

        def request_fn(url, token=None):
            nonlocal calls
            calls += 1
            return {"total_count": calls, "incomplete_results": False}, {}

        payload = collect_issue_backlog_history(
            now=datetime(2026, 8, 22, 9, 17, tzinfo=ZoneInfo("Asia/Tokyo")),
            request_fn=request_fn,
            previous_history={"schemaVersion": 999, "snapshots": [{"date": "2020-01-01"}]},
        )
        self.assertEqual(len(payload["snapshots"]), 1)
        self.assertEqual(payload["snapshots"][0]["date"], "2026-08-22")

    def test_request_interval_applies_to_both_backlog_queries(self):
        sleeps = []

        def request_fn(url, token=None):
            return {"total_count": 1, "incomplete_results": False}, {}

        collect_issue_backlog_history(
            now=datetime(2026, 8, 22, 9, 17, tzinfo=ZoneInfo("Asia/Tokyo")),
            request_fn=request_fn,
            request_interval=2.2,
            sleep_fn=sleeps.append,
        )
        self.assertEqual(sleeps, [2.2, 2.2])


if __name__ == "__main__":
    unittest.main()
