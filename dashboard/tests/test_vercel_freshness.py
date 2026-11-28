import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERCEL = ROOT / "vercel.json"
DASHBOARD_HTML = ROOT / "docs" / "dashboard" / "index.html"
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
FACTORY_EVIDENCE_JS = ROOT / "docs" / "dashboard" / "factory-evidence.js"
CANONICAL_DASHBOARD = "https://kafka2306.github.io/agent-resources/dashboard/dashboard.json"
CANONICAL_FACTORY_STATE = "https://kafka2306.github.io/agent-resources/dashboard/factory-state.json"


class VercelSnapshotTest(unittest.TestCase):
    def test_vercel_routes_public_dashboard_snapshots_to_pages(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        rewrites = {rule["source"]: rule["destination"] for rule in config["rewrites"]}
        self.assertEqual(config["outputDirectory"], "deploy")
        self.assertEqual(rewrites["/dashboard/dashboard.json"], CANONICAL_DASHBOARD)
        self.assertEqual(rewrites["/dashboard/factory-state.json"], CANONICAL_FACTORY_STATE)
        self.assertNotIn("api/dashboard-live.js", config.get("functions", {}))

    def test_dashboard_reads_the_static_snapshot_without_live_endpoint_config(self):
        html = DASHBOARD_HTML.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
        factory_js = FACTORY_EVIDENCE_JS.read_text(encoding="utf-8")
        self.assertIn('rel="icon"', html)
        self.assertIn("../site/assets/images/favicon.png", html)
        self.assertIn('fetch("./dashboard.json"', dashboard_js)
        self.assertIn('fetchJson("./factory-state.json")', factory_js)
        self.assertIn('"UNVERIFIED"', factory_js)
        self.assertIn("current production state UNVERIFIED", factory_js)
        self.assertNotIn("/api/dashboard-live", dashboard_js + factory_js + html)
        self.assertNotIn("live-config.json", dashboard_js + factory_js + html)
        self.assertNotIn("api.github.com", factory_js)
        self.assertNotIn('"auto-refresh.js"', html)

    def test_vercel_build_remains_a_static_dashboard_build(self):
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        command = config["buildCommand"]
        self.assertIn("mkdocs build", command)
        self.assertNotIn("dashboard.collectors", command)
        self.assertNotIn("GITHUB_TOKEN", command)


if __name__ == "__main__":
    unittest.main()
