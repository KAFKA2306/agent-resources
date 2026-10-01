import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_HTML = ROOT / "docs" / "index.html"
HTML = ROOT / "docs" / "dashboard" / "index.html"
CSS = ROOT / "docs" / "dashboard" / "dashboard.css"
JS = ROOT / "docs" / "dashboard" / "dashboard.js"
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
STATS_JS = ROOT / "docs" / "dashboard" / "stats.js"
STATUS_JS = ROOT / "docs" / "dashboard" / "snapshot-status.js"
DOCS_WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"
PUBLIC_LINK_ASSETS = [
    ROOT / "docs" / "dashboard" / "public-links.js",
    ROOT / "docs" / "dashboard" / "public-links.css",
    ROOT / "docs" / "dashboard" / "public-links.json",
]


class DashboardSkeletonTest(unittest.TestCase):
    def test_dashboard_uses_mission_deck_information_architecture(self):
        html = HTML.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn('<main id="main" class="mission-deck"', html)
        self.assertIn('class="command-hero"', html)
        self.assertIn('class="situation-grid"', html)
        self.assertIn('class="evidence-deck"', html)
        self.assertIn('class="activity-bay"', html)
        self.assertIn('class="repository-deck"', html)
        self.assertIn('class="metrics-deck github-stats"', html)
        self.assertIn("grid-template-columns:minmax(0,1.65fr)minmax(300px,.72fr)", css)
        for marker in ('id="activity-feed"', 'id="agent-world-zones"', 'id="lane-gates"', 'id="github-stats-title"'):
            self.assertIn(marker, html)
        self.assertNotIn('class="main-panel"', html)
        self.assertNotIn('class="activity-sidebar"', html)
        self.assertNotIn('id="project-groups"', html)
        self.assertIn('name="viewport"', html)

    def test_command_hierarchy_preserves_canonical_status_and_public_links(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn("game.css", html)
        self.assertNotIn('class="world-decor"', html)
        self.assertIn('<p class="eyebrow">PRIORITY ROUTER</p>', html)
        self.assertIn('id="action-title">今対応すること</h2>', html)
        self.assertIn('class="hub"', html)
        self.assertIn('id="repository-count"', html)
        self.assertIn('id="snapshot-status"', html)
        self.assertIn('id="live-fetched-at"', html)
        self.assertIn('id="snapshot-generated-at"', html)
        self.assertIn('id="operations-generated-at"', html)
        self.assertIn('id="operations-summary"', html)
        self.assertIn('class="public-links"', html)
        self.assertIn("https://github.com/KAFKA2306/agent-resources", html)
        self.assertIn("https://agent-resources-one.vercel.app/site/", html)
        self.assertNotIn("https://pypi.org/project/agent-resources/", html)

    def test_main_information_order_matches_mission_flow(self):
        html = HTML.read_text(encoding="utf-8")
        hub = html.index('class="hub"')
        gates = html.index('id="lane-gates"')
        evidence = html.index('id="factory-evidence-title"')
        activity = html.index('id="activity-feed"')
        world = html.index('id="agent-world-zones"')
        stats = html.index('id="github-stats-title"')
        self.assertLess(hub, gates)
        self.assertLess(gates, evidence)
        self.assertLess(evidence, activity)
        self.assertLess(activity, world)
        self.assertLess(world, stats)

    def test_mobile_collapses_mission_deck_without_losing_activity(self):
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".mission-mast{position:relative;align-items:flex-start;flex-direction:column;padding:14px16px}", css)
        self.assertIn(".mission-deck{padding:12px12px32px}", css)
        self.assertIn(".command-hero{grid-template-columns:minmax(0,1fr);min-height:auto;padding:22px18px;border-radius:20px}", css)
        self.assertIn(".lane-gates{grid-template-columns:minmax(0,1fr)}", css)
        self.assertIn(".evidence-orbit{grid-template-columns:minmax(0,1fr)}", css)
        self.assertIn(".world-stations{grid-template-columns:minmax(0,1fr)}", css)
        self.assertIn(".activity-bay{position:static;max-height:none}", css)

    def test_root_redirects_to_dashboard_and_dashboard_links_to_products(self):
        root_html = ROOT_HTML.read_text(encoding="utf-8")
        dashboard_html = HTML.read_text(encoding="utf-8")
        self.assertIn('content="0; url=./dashboard/"', root_html)
        self.assertIn('window.location.replace("./dashboard/")', root_html)
        self.assertNotIn('href="./site/"', root_html)
        self.assertNotIn('href="../site/"', dashboard_html)
        self.assertIn("https://github.com/KAFKA2306/agent-resources", dashboard_html)
        self.assertIn("https://agent-resources-one.vercel.app/site/", dashboard_html)
        self.assertNotIn("https://pypi.org/project/agent-resources/", dashboard_html)

    def test_agent_world_is_canonical_repository_view(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('fetch("./dashboard.json"', js)
        self.assertIn("renderWorld(repositories, workItems, activity", js)
        self.assertIn('id="agent-world-zones"', html)
        self.assertNotIn('id="project-groups"', html)
        self.assertNotIn("Repository details", html)
        self.assertNotIn("rankRepositories", js)
        self.assertNotIn("repositoryHeat", js)

    def test_module_graph_cache_busts_every_page_load(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        world_js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn("const assetVersion = Date.now().toString();", html)
        self.assertIn('import(`./${name}?v=${assetVersion}`)', html)
        self.assertNotIn('src="./dashboard.js"', html)
        self.assertIn('new URL(import.meta.url).searchParams.get("v")', js)
        self.assertIn('import(`./stats.js?v=${assetVersion}`)', js)
        self.assertIn('import(`./world.js?v=${assetVersion}`)', js)
        self.assertIn('new URL(import.meta.url).searchParams.get("v")', world_js)
        self.assertIn('import(`./ranking.js?v=${assetVersion}`)', world_js)
        self.assertIn('"neural-field.js"', html)

    def test_public_presence_keeps_no_duplicate_dashboard_feature_layer(self):
        html = HTML.read_text(encoding="utf-8")
        stats_js = STATS_JS.read_text(encoding="utf-8")
        self.assertNotIn("PUBLIC PRESENCE", html)
        self.assertNotIn('id="public-links"', html)
        self.assertNotIn("mountPublicLinks", stats_js)
        self.assertNotIn("public-links.js", stats_js)
        self.assertNotIn("public-links.css", stats_js)
        for asset in PUBLIC_LINK_ASSETS:
            self.assertFalse(asset.exists(), f"retired dashboard asset still exists: {asset.name}")

    def test_zero_repositories_has_explicit_empty_state(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn("repositories.length === 0", js)
        self.assertIn("公開対象のrepositoryは0件です。", js)

    def test_activity_feed_uses_full_seven_day_snapshot_activity(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('id="activity-feed"', html)
        self.assertIn("7 DAY SIGNAL", html)
        self.assertIn("snapshot.activity", js)
        self.assertNotIn("ACTIVITY_LIMIT", js)
        self.assertIn("b.occurredAt.localeCompare(a.occurredAt)", js)
        self.assertIn("item.repositoryId", js)
        self.assertIn("item.occurredAt", js)
        self.assertIn("item.url", js)
        self.assertIn("ACTIVITY_LABELS[item.kind]", js)
        self.assertIn("直近7日の活動は0件です。", js)
        self.assertNotIn("api.github.com", js)

    def test_live_smoke_executes_browser_runtime(self):
        workflow = DOCS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Verify rendered dashboard in headless Chrome", workflow)
        self.assertIn("--headless=new", workflow)
        self.assertIn("--dump-dom", workflow)
        self.assertIn("rendered dashboard has zero repositories", workflow)
        self.assertIn("rendered dashboard has zero work items", workflow)
        self.assertIn("rendered dashboard has no recent activity items", workflow)
        self.assertIn("rendered dashboard monthly statistics did not render", workflow)
        self.assertIn("PUBLIC PRESENCE", workflow)
        self.assertIn("Repository details", workflow)

    def test_attention_gates_are_explicit(self):
        js = JS.read_text(encoding="utf-8")
        world_js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn('lane: "waiting", label: "判断待ち"', js)
        self.assertIn('lane: "failed", label: "失敗・要確認"', js)
        self.assertLess(js.index('lane: "waiting"'), js.index('lane: "failed"'))
        self.assertIn("{ createPublicSurfaceLinks, renderWorld }", js)
        self.assertIn("createPublicSurfaceLinks(repo)", js)
        self.assertIn("export function createPublicSurfaceLinks(repository)", world_js)
        self.assertNotIn("function createPublicSurfaceLinks(", js)

    def test_snapshot_generation_time_and_failure_are_explicit(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        status_js = STATUS_JS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        self.assertIn('id="snapshot-generated-at"', html)
        self.assertIn("snapshot.generatedAt", js)
        self.assertIn('snapshotStatus.dataset.state = "failed"', js)
        self.assertIn("最新成功データとして扱いません", js)
        self.assertIn("STALE_AFTER_MS = 2 * 60 * 60 * 1000", status_js)
        self.assertIn('state: "stale"', status_js)
        self.assertIn('[data-state="stale"]', css)
        self.assertIn('[data-state="failed"]', css)


if __name__ == "__main__":
    unittest.main()
