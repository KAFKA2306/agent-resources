import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "docs" / "dashboard" / "index.html"
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
WORLD_CSS = ROOT / "docs" / "dashboard" / "world.css"
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
MANIFEST = ROOT / "docs" / "dashboard" / "assets" / "asset-manifest.json"


class AgentWorldTest(unittest.TestCase):
    def test_world_is_connected_to_canonical_snapshot(self):
        html = HTML.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn('id="agent-world-zones"', html)
        self.assertIn('href="./world.css"', html)
        self.assertIn('import { renderWorld } from "./world.js";', dashboard_js)
        self.assertIn("renderWorld(repositories, workItems);", dashboard_js)
        self.assertIn('fetch("./dashboard.json"', dashboard_js)

    def test_world_layout_is_data_driven(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn("repository.group", js)
        self.assertIn("workByRepository.get(repository.id)", js)
        self.assertIn("item.repositoryId", js)
        self.assertIn("item.lane", js)
        self.assertIn("item.url", js)
        self.assertNotIn("api.github.com", js)

    def test_prompt_vault_sources_are_commit_pinned(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["source"]["commit"],
            "3e70694f9c7487bfa8e72ee57e9004601ce030e2",
        )
        self.assertTrue(manifest["policy"]["visualOnly"])
        self.assertFalse(manifest["policy"]["mutableMainHotlinksAllowed"])
        self.assertGreaterEqual(len(manifest["assets"]), 8)
        for asset in manifest["assets"]:
            self.assertEqual(len(asset["blobSha"]), 40)
            self.assertIn(manifest["source"]["commit"], asset["sourceUrl"])
            self.assertNotIn("/main/", asset["sourceUrl"])

    def test_mobile_falls_back_to_information_first_layout(self):
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".world-reference{display:none}", css)
        self.assertIn("grid-template-columns:minmax(0,1fr)", css)

    def test_monthly_activity_is_below_active_workspace(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertLess(html.index('id="agent-world-zones"'), html.index('id="lane-flow"'))
        self.assertLess(html.index('id="lane-flow"'), html.index('id="project-groups"'))
        self.assertLess(html.index('id="project-groups"'), html.index('id="github-stats-title"'))


if __name__ == "__main__":
    unittest.main()
