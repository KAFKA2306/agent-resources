import unittest
from datetime import datetime, timedelta, timezone

from dashboard.production_live_smoke import validate_live_payload


NOW = datetime(2026, 8, 15, 8, 15, tzinfo=timezone.utc)


def make_payload(*, fetched_at=None):
    return {
        "scope": "public",
        "fetchedAt": (fetched_at or NOW).isoformat().replace("+00:00", "Z"),
        "summary": {"repositoryCount": 1},
        "requestBudget": {"workflowRequestCount": 0},
        "repositories": [
            {
                "id": "R_1",
                "visibility": "public",
                "archived": False,
            }
        ],
        "workItems": [{"repositoryId": "R_1"}],
        "activity": [{"repositoryId": "R_1"}],
    }


class ProductionLiveSmokeTest(unittest.TestCase):
    def test_accepts_fresh_public_payload(self):
        age = validate_live_payload(make_payload(fetched_at=NOW - timedelta(seconds=149)), now=NOW)
        self.assertEqual(age, 149)

    def test_rejects_payload_older_than_live_slo(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_live_payload(make_payload(fetched_at=NOW - timedelta(seconds=151)), now=NOW)

    def test_rejects_zero_repositories(self):
        payload = make_payload()
        payload["repositories"] = []
        payload["workItems"] = []
        payload["activity"] = []
        payload["summary"]["repositoryCount"] = 0
        with self.assertRaisesRegex(ValueError, "zero repositories"):
            validate_live_payload(payload, now=NOW)

    def test_rejects_summary_repository_count_mismatch(self):
        payload = make_payload()
        payload["summary"]["repositoryCount"] = 2
        with self.assertRaisesRegex(ValueError, "repository count diverged"):
            validate_live_payload(payload, now=NOW)

    def test_rejects_non_public_repository(self):
        payload = make_payload()
        payload["repositories"][0]["visibility"] = "private"
        with self.assertRaisesRegex(ValueError, "public repository boundary"):
            validate_live_payload(payload, now=NOW)

    def test_rejects_reference_outside_repository_boundary(self):
        payload = make_payload()
        payload["activity"][0]["repositoryId"] = "R_private"
        with self.assertRaisesRegex(ValueError, "non-public repository"):
            validate_live_payload(payload, now=NOW)

    def test_rejects_missing_request_budget(self):
        payload = make_payload()
        del payload["requestBudget"]
        with self.assertRaisesRegex(ValueError, "requestBudget is missing"):
            validate_live_payload(payload, now=NOW)

    def test_rejects_nonzero_workflow_request_count(self):
        payload = make_payload()
        payload["requestBudget"]["workflowRequestCount"] = 1
        with self.assertRaisesRegex(ValueError, "workflowRequestCount is not zero"):
            validate_live_payload(payload, now=NOW)


if __name__ == "__main__":
    unittest.main()
