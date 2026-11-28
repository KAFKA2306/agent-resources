import unittest
from pathlib import Path


class DashboardReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path(".github/workflows/dashboard-release-verify.yml").read_text(
            encoding="utf-8"
        )

    def test_waits_for_exact_static_pages_snapshot_before_chrome(self):
        self.assertIn("Wait for exact Pages factory snapshot", self.text)
        self.assertIn("--timeout-seconds 180", self.text)
        self.assertLess(
            self.text.index("Wait for exact Pages factory snapshot"),
            self.text.index("Verify released production dashboard in Chrome"),
        )
        self.assertIn("timeout-minutes: 8", self.text)

    def test_release_workflow_has_no_live_api_smoke(self):
        self.assertNotIn("production_live_smoke.py", self.text)
        self.assertNotIn("/api/dashboard-live", self.text)


if __name__ == "__main__":
    unittest.main()
