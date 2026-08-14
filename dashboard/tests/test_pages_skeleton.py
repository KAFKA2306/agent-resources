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

    def test_redundant_hub_chrome_is_retired(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn('<span class="decor-sign">HUB</span>', html)
        self.assertNotIn('<p class="eyebrow">WORKSPACE</p>', html)
        self.assertNotIn('>中央ハブ</h2>', html)
        self.assertNotIn('GitHub Public Hub', html)
        self.assertNotIn('class="hub"', html)
        self.assertIn('id="repository-count"', html)
        self.assertIn('id="snapshot-status"', html)

    def test_main_information_order_stays_stable(self):
        html = HTML.read_text(encoding="utf-8")
        repository_meta = html.index('id="repository-count"')
        gates = html.index('id="lane-gates"')
        world = html.index('id="agent-world-zones"')
        stats = html.index('id="github-stats-title"')
        activity = html.index('id="activity-feed"')
        self.assertLess(repository_meta, gates)
        self.assertLess(gates, world)
        self.assertLess(world, stats)
        self.assertLess(stats, activity)

    def test_mobile_stacks_activity_after_main(self):
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".dashboard-shell{grid-template-columns:minmax(0,1fr);padding:12px}", css)
        self.assertIn(".activity-sidebar{position:static;max-height:none;overflow:visible}", css)
        self.assertIn(".dashboard-meta,.section-heading{align-items:flex-start;flex-direction:column}", css)

    def test_root_promotes_dashboard_and_preserves_docs_routes(self):
        root_html = ROOT_HTML.read_text(encoding="utf-8")
        dashboard_html = HTML.read_text(encoding="utf-8")
        self.assertIn('content="0; url=./dashboard/"', root_html)
        self.assertIn('window.location.replace("./dashboard/")', root_html)
        self.assertIn('href="./site/"', root_html)
        self.assertIn('href="../site/"', dashboard_html)
        self.assertIn('https://github.com/KAFKA2306/agent-resources', dashboard_html)
        self.assertIn('https://pypi.org/project/agent-resources/', dashboard_html)

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

    def test_public_presence_is_out_of_dashboard_scope(self):
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
        self.assertIn("SIDEBAR · LAST 7 DAYS", html)
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
        self.assertIn("rendered dashboard has zero agents", workflow)
        self.assertIn("rendered dashboard has no recent activity items", workflow)
        self.assertIn("rendered dashboard monthly statistics did not render", workflow)
        self.assertIn("PUBLIC PRESENCE", workflow)
        self.assertIn("Repository details", workflow)

    def test_attention_gates_are_explicit(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('lane: "waiting", label: "判断待ち"', js)
        self.assertIn('lane: "failed", label: "失敗・要確認"', js)
        self.assertLess(js.index('lane: "waiting"'), js.index('lane: "failed"'))

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
