import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERCEL = ROOT / "vercel.json"
DASHBOARD_HTML = ROOT / "docs" / "dashboard" / "index.html"
AUTO_REFRESH = ROOT / "docs" / "dashboard" / "auto-refresh.js"


class VercelFreshnessTest(unittest.TestCase):
    def test_vercel_proxies_live_pages_snapshot_without_redeploy(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        self.assertEqual(config["outputDirectory"], "deploy")
        rewrite = config["rewrites"][0]
        self.assertEqual(rewrite["source"], "/dashboard/dashboard.json")
        self.assertEqual(
            rewrite["destination"],
            "https://kafka2306.github.io/agent-resources/dashboard/dashboard.json",
        )
        header = config["headers"][0]
        self.assertEqual(header["source"], "/dashboard/dashboard.json")
        self.assertIn("no-store", header["headers"][0]["value"])

    def test_vercel_build_is_static_and_does_not_duplicate_github_collection(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        command = config["buildCommand"]
        self.assertIn("mkdocs build", command)
        self.assertNotIn("dashboard.collectors", command)
        self.assertNotIn("GITHUB_TOKEN", command)

    def test_browser_refreshes_periodically_and_after_tab_returns(self):
        html = DASHBOARD_HTML.read_text(encoding="utf-8")
        js = AUTO_REFRESH.read_text(encoding="utf-8")
        self.assertIn('"auto-refresh.js"', html)
        self.assertIn('import(`./${name}?v=${assetVersion}`)', html)
        self.assertIn("5 * 60 * 1000", js)
        self.assertIn('document.addEventListener("visibilitychange"', js)
        self.assertIn('document.visibilityState !== "visible"', js)
        self.assertIn("window.location.reload()", js)


if __name__ == "__main__":
    unittest.main()
