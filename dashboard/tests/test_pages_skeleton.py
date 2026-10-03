import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_HTML = ROOT / "docs" / "index.html"
HTML = ROOT / "docs" / "dashboard" / "index.html"
CSS = ROOT / "docs" / "dashboard" / "dashboard.css"
JS = ROOT / "docs" / "dashboard" / "dashboard.js"
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
NEURAL_JS = ROOT / "docs" / "dashboard" / "neural-field.js"
FACTORY_EVIDENCE_JS = ROOT / "docs" / "dashboard" / "factory-evidence.js"
STATS_JS = ROOT / "docs" / "dashboard" / "stats.js"
STATUS_JS = ROOT / "docs" / "dashboard" / "snapshot-status.js"
DOCS_WORKFLOW = ROOT / ".github" / "workflows" / "docs.yml"
PUBLIC_LINK_ASSETS = [
    ROOT / "docs" / "dashboard" / "public-links.js",
    ROOT / "docs" / "dashboard" / "public-links.css",
    ROOT / "docs" / "dashboard" / "public-links.json",
]


class DashboardSkeletonTest(unittest.TestCase):
    def test_dashboard_uses_autonomy_reactor_bridge_information_architecture(self):
        html = HTML.read_text(encoding="utf-8")
        css = "".join(CSS.read_text(encoding="utf-8").split())
        self.assertIn('<main id="main" class="bridge-shell"', html)
        self.assertIn('class="bridge-stage"', html)
        self.assertIn('class="reactor-stage"', html)
        self.assertIn('class="evidence-spine"', html)
        self.assertIn('class="operations-summary mission-vector"', html)
        self.assertIn('class="signal-stream"', html)
        self.assertIn('class="repository-field"', html)
        self.assertIn('class="telemetry-deck github-stats"', html)
        self.assertIn("grid-template-columns:minmax(260px,.88fr)minmax(560px,1.55fr)minmax(260px,.82fr)", css)
        for marker in ('id="factory-capabilities"', 'id="activity-feed"', 'id="agent-world-zones"', 'id="lane-gates"', 'id="github-stats-title"'):
            self.assertIn(marker, html)
        self.assertNotIn('class="mission-deck"', html)
        self.assertNotIn('class="command-hero"', html)
        self.assertNotIn('class="situation-grid"', html)
        self.assertNotIn('class="activity-sidebar"', html)
        self.assertNotIn('id="project-groups"', html)
        self.assertIn('name="viewport"', html)

    def test_bridge_hierarchy_preserves_canonical_status_and_public_links(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn("game.css", html)
        self.assertNotIn('class="world-decor"', html)
        self.assertIn('<p class="eyebrow">MISSION VECTOR</p>', html)
        self.assertIn('id="action-title">INTERVENTION</h2>', html)
        self.assertIn('class="hub"', html)
        self.assertIn('id="repository-count"', html)
        self.assertIn('id="snapshot-status"', html)
        self.assertIn('id="factory-capabilities"', html)
        self.assertIn('id="factory-freshness"', html)
        self.assertIn('id="live-fetched-at"', html)
        self.assertIn('id="snapshot-generated-at"', html)
        self.assertIn('id="operations-generated-at"', html)
        self.assertIn('id="operations-summary"', html)
        self.assertIn('class="hero-telemetry"', html)
        self.assertIn('id="hero-repository-total"', html)
        self.assertIn('id="hero-activity-total"', html)
        self.assertIn('id="hero-autonomy-total"', html)
        self.assertIn('id="hero-motion-label"', html)
        self.assertIn('class="public-links"', html)
        self.assertIn("https://github.com/KAFKA2306/agent-resources", html)
        self.assertIn("https://agent-resources-one.vercel.app/site/", html)
        self.assertNotIn("https://pypi.org/project/agent-resources/", html)

    def test_main_information_order_matches_bridge_flow(self):
        html = HTML.read_text(encoding="utf-8")
        hub = html.index('class="hub"')
        reactor = html.index('id="factory-capabilities"')
        evidence = html.index('id="factory-evidence-title"')
        gates = html.index('id="lane-gates"')
        activity = html.index('id="activity-feed"')
        world = html.index('id="agent-world-zones"')
        stats = html.index('id="github-stats-title"')
        self.assertLess(hub, reactor)
        self.assertLess(reactor, evidence)
        self.assertLess(evidence, gates)
        self.assertLess(gates, activity)
        self.assertLess(activity, world)
        self.assertLess(world, stats)

    def test_mobile_collapses_reactor_to_readable_modules(self):
        css = "".join(CSS.read_text(encoding="utf-8").split())
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn(".bridge-mast{position:relative;align-items:flex-start;flex-direction:column;padding:13px15px}", css)
        self.assertIn(".bridge-shell{padding:10px10px30px}", css)
        self.assertIn(".bridge-stage{border-radius:20px}", css)
        self.assertIn(".reactor-field{height:auto;min-height:0;margin:12px00;padding:8px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;background:none;border-radius:0}", css)
        self.assertIn(".reactor-node{position:relative;left:auto;top:auto;width:auto;min-height:80px;transform:none;animation:none}", css)
        self.assertIn(".lane-gates{grid-template-columns:minmax(0,1fr);gap:8px}", css)
        self.assertIn(".evidence-chain{grid-template-columns:minmax(0,1fr)}", css)
        self.assertIn(".constellation-node-label{display:none}", css)

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
        self.assertIn("NO SIGNAL", js)

    def test_activity_feed_uses_full_seven_day_snapshot_activity(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('id="activity-feed"', html)
        self.assertIn("LIVE SIGNAL STREAM", html)
        self.assertIn("snapshot.activity", js)
        self.assertNotIn("ACTIVITY_LIMIT", js)
        self.assertIn("a.occurredAt.localeCompare(b.occurredAt)", js)
        self.assertIn("item.repositoryId", js)
        self.assertIn("item.occurredAt", js)
        self.assertIn("item.url", js)
        self.assertIn("ACTIVITY_LABELS[item.kind]", js)
        self.assertIn("NO SIGNAL", js)
        self.assertIn("activity-pulse-plot", js)
        self.assertIn("pulse-envelope", js)
        self.assertNotIn("api.github.com", js)

    def test_observatory_motion_and_evidence_are_data_driven(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        neural_js = NEURAL_JS.read_text(encoding="utf-8")
        evidence_js = FACTORY_EVIDENCE_JS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")

        self.assertIn('data-stage="main"', html)
        self.assertIn('data-stage="pages"', html)
        self.assertIn("document.documentElement.dataset.factoryActivity", js)
        self.assertIn("document.documentElement.dataset.factoryMotion", js)
        self.assertIn("heroRepositoryTotal.textContent", js)
        self.assertIn("heroActivityTotal.textContent", js)
        self.assertIn("heroMotionLabel.textContent", js)
        self.assertIn("heroAutonomyTotal.textContent", evidence_js)
        self.assertIn("document.documentElement.dataset.factoryAutonomy", evidence_js)
        self.assertIn('factoryActivity >= 0.65 ? "hot" : "active"', js)
        self.assertIn(':root[data-factory-motion="active"] .reactor-link[data-flow="active"]', css)
        self.assertIn(':root[data-factory-motion="hot"] .reactor-core-pulse', css)
        self.assertIn("uniform float u_activity", neural_js)
        self.assertIn('link.dataset.flow = tone === "verified" || tone === "online" ? "active" : tone;', evidence_js)
        self.assertIn('setEvidencePath("failed", "main")', evidence_js)
        self.assertIn('setEvidencePath("failed", "pages")', evidence_js)
        self.assertIn('.reactor-link[data-flow="active"]', css)
        self.assertIn('.evidence-spine[data-chain-state="failed"]', css)
        self.assertIn("Observatory scale-up: make the factory feel physically large.", css)
        self.assertIn(".repository-constellation-shell{min-height:720px", css)
        self.assertIn(".reactor-field{width:min(100%,900px);height:720px", css)
        self.assertIn(".hero-metric strong{font-size:clamp(3.1rem,4.4vw,5.4rem)", css)

    def test_live_smoke_executes_browser_runtime(self):
        workflow = DOCS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Verify rendered dashboard in headless Chrome", workflow)
        self.assertIn("--headless=new", workflow)
        self.assertIn("--dump-dom", workflow)
        self.assertIn("rendered dashboard has zero repositories", workflow)
        self.assertIn("rendered dashboard has zero work items", workflow)
        self.assertIn("rendered dashboard has no recent activity items", workflow)
        self.assertIn("activity-pulse-point", workflow)
        self.assertIn("output-waveform", workflow)
        self.assertIn("rendered dashboard monthly statistics did not render", workflow)
        self.assertIn("PUBLIC PRESENCE", workflow)
        self.assertIn("Repository details", workflow)

    def test_attention_gates_are_explicit(self):
        js = JS.read_text(encoding="utf-8")
        world_js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn('lane: "waiting", label: "WAIT", detailLabel: "判断待ち"', js)
        self.assertIn('lane: "failed", label: "FAIL", detailLabel: "失敗・要確認"', js)
        self.assertIn('lane: "done", label: "DONE", detailLabel: "完了報告"', js)
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
