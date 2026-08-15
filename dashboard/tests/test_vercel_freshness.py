import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERCEL = ROOT / "vercel.json"
DASHBOARD_HTML = ROOT / "docs" / "dashboard" / "index.html"
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
AUTO_REFRESH = ROOT / "docs" / "dashboard" / "auto-refresh.js"
LIVE_CONFIG = ROOT / "docs" / "dashboard" / "live-config.json"
LIVE_API = ROOT / "api" / "dashboard-live.js"


class VercelFreshnessTest(unittest.TestCase):
    def test_vercel_keeps_snapshot_as_baseline_and_builds_live_function(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        self.assertEqual(config["outputDirectory"], "deploy")
        rewrite = config["rewrites"][0]
        self.assertEqual(rewrite["source"], "/dashboard/dashboard.json")
        self.assertEqual(
            rewrite["destination"],
            "https://kafka2306.github.io/agent-resources/dashboard/dashboard.json",
        )
        self.assertIn("api/dashboard-live.js", config["functions"])
        self.assertGreaterEqual(config["functions"]["api/dashboard-live.js"]["maxDuration"], 30)

    def test_vercel_build_is_static_and_does_not_duplicate_github_collection(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        command = config["buildCommand"]
        self.assertIn("mkdocs build", command)
        self.assertNotIn("dashboard.collectors", command)
        self.assertNotIn("GITHUB_TOKEN", command)

    def test_browser_refreshes_live_state_without_full_page_reload(self):
        html = DASHBOARD_HTML.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
        js = AUTO_REFRESH.read_text(encoding="utf-8")
        self.assertIn('"auto-refresh.js"', html)
        self.assertIn('import(`./${name}?v=${assetVersion}`)', html)
        self.assertIn('id="live-fetched-at"', html)
        self.assertIn("2 * 60 * 1000", js)
        self.assertIn('document.addEventListener("visibilitychange"', js)
        self.assertIn('window.addEventListener("focus"', js)
        self.assertIn('window.addEventListener("pageshow"', js)
        self.assertIn('"dashboard:refresh-live"', js)
        self.assertNotIn("window.location.reload()", js)
        self.assertIn("mergeLiveSnapshot", dashboard_js)
        self.assertIn('fetch(endpoint, { headers: { Accept: "application/json" } })', dashboard_js)

    def test_pages_live_endpoint_targets_verified_vercel_url(self):
        config = json.loads(LIVE_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(
            config["endpoint"],
            "https://agent-resources-one.vercel.app/api/dashboard-live",
        )
        api = LIVE_API.read_text(encoding="utf-8")
        self.assertIn('response.setHeader("Access-Control-Allow-Origin", "*")', api)
        self.assertIn("DASHBOARD_GITHUB_TOKEN", api)
        self.assertNotIn("ghp_", api)
        self.assertNotIn("github_pat_", api)


if __name__ == "__main__":
    unittest.main()
