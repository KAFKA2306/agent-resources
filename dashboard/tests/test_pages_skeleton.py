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
    def test_dashboard_keeps_only_recent_activity_in_right_sidebar(self):
        html = HTML.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn('<main class="main-panel"', html)
        self.assertIn('<aside class="activity-sidebar"', html)
        self.assertIn("grid-template-columns:minmax(0,1fr)minmax(260px,340px)", css)
        self.assertIn('id="activity-feed"', html)
        main_start = html.index('<main class="main-panel"')
        main_end = html.index("</main>", main_start)
        sidebar = html.index('<aside class="activity-sidebar"')
        self.assertGreater(sidebar, main_end)
        self.assertNotIn('id="activity-feed"', html[main_start:main_end])
        for marker in ('id="agent-world-zones"', 'id="lane-gates"', 'id="github-stats-title"'):
            self.assertIn(marker, html[main_start:main_end])
        self.assertNotIn('id="project-groups"', html)
        self.assertIn('SIDEBAR · LAST 7 DAYS', html)
        self.assertIn('name="viewport"', html)

    def test_hub_hierarchy_is_preserved_with_compact_public_links(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn('game.css', html)
        self.assertNotIn('class="world-decor"', html)
        self.assertIn('<p class="eyebrow">WORKSPACE</p>', html)
        self.assertIn('>中央ハブ</h2>', html)
        self.assertIn('GitHub Public Hub', html)
        self.assertIn('class="hub"', html)
        self.assertIn('id="repository-count"', html)
        self.assertIn('id="snapshot-status"', html)
        self.assertNotIn('class="top-actions"', html)
        self.assertIn('class="public-links"', html)
        self.assertIn('https://github.com/KAFKA2306/agent-resources', html)
        self.assertIn('https://agent-resources-one.vercel.app/site/', html)
        self.assertNotIn('https://pypi.org/project/agent-resources/', html)

    def test_main_information_order_stays_stable(self):
        html = HTML.read_text(encoding="utf-8")
        hub = html.index('class="hub"')
        gates = html.index('id="lane-gates"')
        world = html.index('id="agent-world-zones"')
        stats = html.index('id="github-stats-title"')
        activity = html.index('id="activity-feed"')
        self.assertLess(hub, gates)
        self.assertLess(gates, world)
        self.assertLess(world, stats)
        self.assertLess(stats, activity)

    def test_mobile_stacks_activity_after_main(self):
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".dashboard-shell{grid-template-columns:minmax(0,1fr);padding:12px}", css)
        self.assertIn(".activity-sidebar{position:static;max-height:none;overflow:visible}", css)
        self.assertIn(".panel-heading,.section-heading{align-items:flex-start;flex-direction:column}", css)
        self.assertIn(".hub{align-items:flex-start;flex-direction:column}", css)
        self.assertIn(".topbar{align-items:flex-start;flex-direction:column;padding:18px}", css)

    def test_root_redirects_to_dashboard_and_dashboard_links_to_products(self):
        root_html = ROOT_HTML.read_text(encoding="utf-8")
        dashboard_html = HTML.read_text(encoding="utf-8")
        self.assertIn('content="0; url=./dashboard/"', root_html)
        self.assertIn('window.location.replace("./dashboard/")', root_html)
        self.assertNotIn('href="./site/"', root_html)
        self.assertNotIn('href="../site/"', dashboard_html)
        self.assertIn('https://github.com/KAFKA2306/agent-resources', dashboard_html)
        self.assertIn('https://agent-resources-one.vercel.app/site/', dashboard_html)
        self.assertNotIn('https://pypi.org/project/agent-resources/', dashboard_html)

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

    def test_snapshot_generation_time_and_failure_are_explicit(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        status_js = STATUS_JS.read_text(encoding="utf-8")
        self.assertIn('id="snapshot-status"', html)
        self.assertIn('id="snapshot-generated-at"', html)
        self.assertIn('id="workspace-message"', html)
        self.assertIn("classifySnapshot", js)
        self.assertIn("UNAVAILABLE", status_js)
        self.assertIn("SNAPSHOT", status_js)
        self.assertIn("LIVE", status_js)

    def test_zero_repositories_has_explicit_empty_state(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('workspaceMessage.textContent = "公開リポジトリを取得できませんでした。"', js)

    def test_attention_gates_are_explicit(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('id="lane-gates"', html)
        self.assertIn('id="gate-detail"', html)
        self.assertIn('label: "判断待ち"', js)
        self.assertIn('label: "失敗・要確認"', js)
        self.assertIn('label: "完了報告"', js)

    def test_public_presence_keeps_no_duplicate_dashboard_feature_layer(self):
        for asset in PUBLIC_LINK_ASSETS:
            self.assertFalse(asset.exists(), asset)

    def test_live_smoke_executes_browser_runtime(self):
        workflow = DOCS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("dashboard/live_smoke.mjs", workflow)

    def test_activity_feed_uses_full_seven_day_snapshot_activity(self):
        js = JS.read_text(encoding="utf-8")
        self.assertNotIn("slice(0,", js)


if __name__ == "__main__":
    unittest.main()
