import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "docs" / "dashboard" / "index.html"
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
WORLD_CSS = ROOT / "docs" / "dashboard" / "world.css"
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
MANIFEST = ROOT / "docs" / "dashboard" / "assets" / "asset-manifest.json"
ASSET_ROOT = ROOT / "docs" / "dashboard"


class AgentWorldTest(unittest.TestCase):
    def test_world_is_connected_to_canonical_or_live_public_state(self):
        html = HTML.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn('id="agent-world-zones"', html)
        self.assertIn('href="./world.css"', html)
        self.assertIn('import(`./world.js?v=${assetVersion}`)', dashboard_js)
        self.assertIn(
            "const referenceTime = snapshot.liveFetchedAt || snapshot.generatedAt;",
            dashboard_js,
        )
        self.assertIn(
            "renderWorld(repositories, workItems, activity, referenceTime);",
            dashboard_js,
        )
        self.assertIn('fetch("./dashboard.json"', dashboard_js)
        self.assertIn("mergeLiveSnapshot(baselineSnapshot, live)", dashboard_js)

    def test_world_layout_is_data_driven(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn("rankRepositories(repositories, workItems, activity, generatedAt)", js)
        self.assertIn("workByRepository.get(repository.id)", js)
        self.assertIn("item.repositoryId", js)
        self.assertIn("item.lane", js)
        self.assertIn("item.kind", js)
        self.assertIn("item.url", js)
        self.assertNotIn("repository.group", js)
        self.assertNotIn("agent-zone-", js)
        self.assertNotIn("unclassified", js)
        self.assertNotIn("api.github.com", js)
        self.assertNotIn("raw.githubusercontent.com", js)

    def test_world_has_no_repository_zone_layer(self):
        world_js = WORLD_JS.read_text(encoding="utf-8")
        dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn("repository.group", world_js)
        self.assertNotIn("agent-zone-", world_js)
        self.assertNotIn("world-unclassified-details", world_js)
        self.assertNotIn("unclassified", world_js)
        self.assertNotIn("zoned", world_js)
        self.assertNotIn('id="operations-zone-action"', html)
        self.assertNotIn("project zone", html)
        self.assertNotIn('section.className = "project-group repository-directory"', dashboard_js)
        self.assertNotIn('id="project-groups"', html)
        self.assertNotIn("groupRepositories(repositories)", dashboard_js)

    def test_repositories_are_ranked_by_current_work(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn('stations.className = "world-stations"', js)
        self.assertIn("rankRepositories(repositories, workItems, activity, generatedAt)", js)
        self.assertIn("repositoryHeat(repository, workItems, activity, generatedAt)", js)
        self.assertIn("${repositories.length} repositories", js)
        self.assertNotIn("unclassified", js)
        self.assertNotIn("agent-zone-", js)

    def test_station_project_header_is_top_aligned(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("station.append(repositoryLink, scene, agents);", js)
        self.assertIn(".world-station{display:grid;align-content:start;", css)
        self.assertIn(".world-station-link{display:flex;align-items:flex-start;", css)

    def test_station_has_one_click_front_and_pages_links(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("repository.publicLinks", js)
        self.assertIn('link.kind === "pages" ? "PAGES ↗" : "FRONT ↗"', js)
        self.assertIn('actions.className = "world-station-actions"', js)
        self.assertIn('anchor.rel = "noopener noreferrer"', js)
        self.assertIn("station.insertBefore(publicSurfaceLinks, scene);", js)
        self.assertIn(".world-station-actions{display:flex;flex-wrap:wrap;gap:5px}", css)
        self.assertIn(".world-surface-link{display:inline-flex", css)

    def test_prompt_vault_sources_are_commit_pinned(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"]["commit"], "99e9e038942660d5bf27faafbcc1b1a490b0fca7")
        self.assertEqual(manifest["source"]["consumerManifest"], "design-systems/kafka-signal/consumers/agent-resources.json")
        self.assertTrue(manifest["policy"]["visualOnly"])
        self.assertTrue(manifest["policy"]["stableAssetIdsRequired"])
        self.assertFalse(manifest["policy"]["mutableMainHotlinksAllowed"])
        self.assertEqual(len(manifest["assets"]), 13)
        for asset in manifest["assets"]:
            self.assertEqual(len(asset["blobSha"]), 40)
            self.assertEqual(len(asset["sha256"]), 64)
            self.assertIn(manifest["source"]["commit"], asset["sourceUrl"])
            self.assertNotIn("/main/", asset["sourceUrl"])

    def test_stable_asset_ids_drive_role_state_and_scene_selection(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        required_ids = {"role.issue-working.v1","role.pull-request-review.v1","role.workflow-terminal.v1","state.working.v1","state.waiting.v1","state.done.v1","state.failed.v1","scene.desk.v1","scene.review-bench.v1","scene.terminal.v1","prop.small-pack.v1"}
        for asset_id in required_ids:
            self.assertIn(f'"{asset_id}"', js)
        self.assertIn("function resolveAsset(assetId)", js)
        self.assertIn("ROLE_ASSET_IDS[kind]", js)
        self.assertIn("STATE_ASSET_IDS[lane]", js)
        self.assertIn('item.kind === "workflow_run"', js)
        self.assertIn('item.kind === "pull_request"', js)
        self.assertNotIn('"scene.sign.v1"', js)
        self.assertNotIn('"scene.floor.v1"', js)

    def test_vendored_asset_hashes_are_a_visual_regression_gate(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        classes = {asset["class"] for asset in manifest["assets"]}
        self.assertEqual(classes, {"role", "state", "scene", "prop"})
        for asset in manifest["assets"]:
            local = ASSET_ROOT / asset["localPath"]
            self.assertTrue(local.is_file(), asset["id"])
            digest = hashlib.sha256(local.read_bytes()).hexdigest()
            self.assertEqual(digest, asset["sha256"], asset["id"])

    def test_css_figure_is_only_a_failure_fallback(self):
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")
        js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn(".world-role-asset", css)
        self.assertIn(".world-state-asset", css)
        self.assertIn(".world-scene-asset", css)
        self.assertIn(".world-agent-figure.has-role-asset::before,.world-agent-figure.has-role-asset::after{display:none}", css)
        self.assertIn('figure.classList.add("has-role-asset")', js)
        self.assertIn('image.dataset.assetState = "failed"', js)
        self.assertIn("image.hidden = true", js)
        self.assertIn("copy.append(title, status)", js)

    def test_mobile_falls_back_to_information_first_layout(self):
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".world-floor-asset,.world-station-scene{display:none}", css)
        self.assertIn("grid-template-columns:minmax(0,1fr)", css)

    def test_monthly_activity_is_below_active_workspace(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertLess(html.index('id="lane-gates"'), html.index('id="agent-world-zones"'))
        self.assertLess(html.index('id="agent-world-zones"'), html.index('id="github-stats-title"'))
        self.assertNotIn('id="lane-flow"', html)
        self.assertNotIn('id="project-groups"', html)


if __name__ == "__main__":
    unittest.main()
