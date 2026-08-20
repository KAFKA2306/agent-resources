import unittest
from datetime import date

from dashboard.collectors.actions_budget import collect_actions_budget
from dashboard.collectors.github_api import GitHubApiError


class FakeApi:
    def __init__(self, *, billing_available=True):
        self.billing_available = billing_available

    def paginate(self, url, token=None, request_fn=None, item_key=None):
        self.assert_token(token)
        return [
            {"name": "busy", "private": True, "archived": False, "owner": {"login": "KAFKA2306"}},
            {"name": "idle", "private": True, "archived": False, "owner": {"login": "KAFKA2306"}},
            {"name": "archive", "private": True, "archived": True, "owner": {"login": "KAFKA2306"}},
            {"name": "foreign", "private": True, "archived": False, "owner": {"login": "other"}},
        ]

    def request(self, url, token=None):
        self.assert_token(token)
        if "/settings/billing/usage?" in url:
            if not self.billing_available:
                raise GitHubApiError("forbidden", status=403)
            return (
                {
                    "usageItems": [
                        {
                            "product": "Actions",
                            "unitType": "minutes",
                            "quantity": 1000,
                            "repositoryName": "KAFKA2306/busy",
                            "sku": "actions_linux",
                        },
                        {
                            "product": "Actions",
                            "unitType": "minutes",
                            "quantity": 250,
                            "repositoryName": "KAFKA2306/idle",
                            "sku": "actions_windows",
                        },
                        {"product": "Actions", "unitType": "GB-hours", "quantity": 4},
                        {"product": "Codespaces", "unitType": "minutes", "quantity": 999},
                    ]
                },
                {},
            )
        if url.endswith("/busy/actions/workflows?per_page=100"):
            return (
                {
                    "workflows": [
                        {"id": 102, "name": "Nightly", "path": ".github/workflows/nightly.yml", "state": "active"},
                        {"id": 101, "name": "CI", "path": ".github/workflows/ci.yml", "state": "active"},
                        {"id": 103, "name": "Old", "path": ".github/workflows/old.yml", "state": "disabled_manually"},
                    ]
                },
                {},
            )
        if url.endswith("/idle/actions/workflows?per_page=100"):
            return ({"workflows": [{"id": 201, "name": "CI", "path": ".github/workflows/ci.yml", "state": "active"}]}, {})
        if "/busy/actions/workflows/101/runs?" in url:
            if "2026-08-09..2026-08-15" in url:
                return ({"total_count": 10}, {})
            return ({"total_count": 20}, {})
        if "/busy/actions/workflows/102/runs?" in url:
            if "2026-08-09..2026-08-15" in url:
                return ({"total_count": 4}, {})
            return ({"total_count": 9}, {})
        if "/busy/actions/runs?" in url:
            if "2026-08-09..2026-08-15" in url:
                return ({"total_count": 14}, {})
            return ({"total_count": 31}, {})
        if "/idle/actions/runs?" in url:
            return ({"total_count": 0}, {})
        raise AssertionError(f"unexpected URL: {url}")

    @staticmethod
    def assert_token(token):
        if token != "secret":
            raise AssertionError("private collector must use the supplied token")


class ActionsBudgetCollectorTests(unittest.TestCase):
    def test_separates_billing_minutes_from_run_activity(self):
        api = FakeApi()
        payload = collect_actions_budget(
            today=date(2026, 8, 15),
            token="secret",
            request_fn=api.request,
            paginate_fn=api.paginate,
        )

        self.assertEqual(payload["schema_version"], "actions-budget.v1")
        self.assertEqual(payload["billing"]["reported_actions_minutes"], 1250.0)
        self.assertEqual(payload["billing"]["remaining_included_minutes"], 750.0)
        self.assertEqual(payload["billing"]["budget_state"], "warning")
        self.assertEqual(
            payload["billing"]["reported_actions_minutes_by_repository"],
            [
                {"name": "KAFKA2306/busy", "minutes": 1000.0},
                {"name": "KAFKA2306/idle", "minutes": 250.0},
            ],
        )
        self.assertEqual(
            payload["billing"]["reported_actions_minutes_by_sku"],
            [
                {"name": "actions_linux", "minutes": 1000.0},
                {"name": "actions_windows", "minutes": 250.0},
            ],
        )
        self.assertEqual(payload["activity"]["private_repository_count"], 3)
        self.assertEqual(payload["activity"]["forward_active_repository_count"], 1)
        self.assertEqual(payload["activity"]["month_to_date_runs"], 31)
        self.assertEqual(payload["activity"]["rolling_7d_runs"], 14)
        self.assertEqual(payload["activity"]["rolling_7d_runs_from_active_workflows"], 14)
        self.assertEqual(payload["activity"]["projected_monthly_runs_from_active_workflows"], 62.0)
        self.assertFalse(payload["activity"]["projection_is_billed_minutes"])
        self.assertEqual(payload["decision"]["highest_run_repository"], "KAFKA2306/busy")
        self.assertEqual(payload["decision"]["highest_billed_repository"], "KAFKA2306/busy")
        self.assertTrue(payload["decision"]["can_assert_remaining_minutes"])

        busy = next(row for row in payload["repositories"] if row["name"] == "busy")
        self.assertEqual(busy["active_workflows"], 2)
        self.assertEqual(
            busy["active_workflow_inventory"],
            [
                {
                    "id": 101,
                    "name": "CI",
                    "path": ".github/workflows/ci.yml",
                    "month_to_date_runs": 20,
                    "rolling_7d_runs": 10,
                },
                {
                    "id": 102,
                    "name": "Nightly",
                    "path": ".github/workflows/nightly.yml",
                    "month_to_date_runs": 9,
                    "rolling_7d_runs": 4,
                },
            ],
        )
        self.assertEqual(busy["month_to_date_runs_from_active_workflows"], 29)
        self.assertEqual(busy["rolling_7d_runs_from_active_workflows"], 14)
        self.assertEqual(busy["month_to_date_unattributed_runs"], 2)
        self.assertEqual(busy["rolling_7d_unattributed_runs"], 0)
        self.assertTrue(busy["forward_active"])

        idle = next(row for row in payload["repositories"] if row["name"] == "idle")
        self.assertEqual(idle["active_workflows"], 1)
        self.assertEqual(
            idle["active_workflow_inventory"],
            [
                {
                    "id": 201,
                    "name": "CI",
                    "path": ".github/workflows/ci.yml",
                    "month_to_date_runs": 0,
                    "rolling_7d_runs": 0,
                }
            ],
        )
        self.assertEqual(idle["month_to_date_runs_from_active_workflows"], 0)
        self.assertEqual(idle["rolling_7d_runs_from_active_workflows"], 0)
        self.assertFalse(idle["forward_active"])

        archived = next(row for row in payload["repositories"] if row["name"] == "archive")
        self.assertFalse(archived["forward_active"])
        self.assertEqual(archived["active_workflows"], 0)
        self.assertEqual(archived["active_workflow_inventory"], [])
        self.assertEqual(archived["month_to_date_runs"], 0)
        self.assertEqual(archived["rolling_7d_runs_from_active_workflows"], 0)

    def test_billing_403_is_unknown_not_zero(self):
        api = FakeApi(billing_available=False)
        payload = collect_actions_budget(
            today=date(2026, 8, 15),
            token="secret",
            request_fn=api.request,
            paginate_fn=api.paginate,
        )

        self.assertEqual(payload["billing"]["status"], "unavailable")
        self.assertEqual(payload["billing"]["reason"], "github_api_http_403")
        self.assertIsNone(payload["billing"]["reported_actions_minutes"])
        self.assertIsNone(payload["billing"]["reported_actions_minutes_by_repository"])
        self.assertIsNone(payload["billing"]["reported_actions_minutes_by_sku"])
        self.assertIsNone(payload["billing"]["remaining_included_minutes"])
        self.assertEqual(payload["billing"]["budget_state"], "unknown")
        self.assertIsNone(payload["decision"]["highest_billed_repository"])
        self.assertFalse(payload["decision"]["can_assert_remaining_minutes"])

    def test_thresholds_must_be_ordered(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            collect_actions_budget(
                today=date(2026, 8, 15),
                token="secret",
                warning_minutes=1600,
                critical_minutes=1200,
            )


if __name__ == "__main__":
    unittest.main()
