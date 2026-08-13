import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_HTML = ROOT / "docs" / "index.html"
HTML = ROOT / "docs" / "dashboard" / "index.html"
CSS = ROOT / "docs" / "dashboard" / "dashboard.css"
JS = ROOT / "docs" / "dashboard" / "dashboard.js"
STATUS_JS = ROOT / "docs" / "dashboard" / "snapshot-status.js"


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
        for marker in ('id="agent-world-zones"', 'id="lane-gates"', 'id="project-groups"', 'id="github-stats-title"'):
            self.assertIn(marker, html[main_start:main_end])
        self.assertIn('name="viewport"', html)

    def test_main_information_order_stays_stable(self):
        html = HTML.read_text(encoding="utf-8")
        world = html.index('id="agent-world-zones"')
        gates = html.index('id="lane-gates"')
        projects = html.index('id="project-groups"')
        stats = html.index('id="github-stats-title"')
        activity = html.index('id="activity-feed"')
        self.assertLess(world, gates)
        self.assertLess(gates, projects)
        self.assertLess(projects, stats)
        self.assertLess(stats, activity)

    def test_mobile_stacks_activity_after_main(self):
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn(".dashboard-shell{grid-template-columns:minmax(0,1fr);padding:12px}", css)
        self.assertIn(".activity-sidebar{position:static;max-height:none;overflow:visible}", css)
        self.assertIn(".panel-heading,.section-heading{align-items:flex-start;flex-direction:column}", css)

    def test_root_promotes_dashboard_and_preserves_docs_routes(self):
        root_html = ROOT_HTML.read_text(encoding="utf-8")
        dashboard_html = HTML.read_text(encoding="utf-8")
        self.assertIn('content="0; url=./dashboard/"', root_html)
        self.assertIn('window.location.replace("./dashboard/")', root_html)
        self.assertIn('href="./site/"', root_html)
        self.assertIn('href="../site/"', dashboard_html)
        self.assertIn('https://github.com/KAFKA2306/agent-resources', dashboard_html)
        self.assertIn('https://pypi.org/project/agent-resources/', dashboard_html)

    def test_repository_groups_are_loaded_from_dashboard_json(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('fetch("./dashboard.json"', js)
        self.assertIn("repository.group", js)
        self.assertIn("repository.url", js)
        self.assertNotIn("api.github.com", js)

    def test_zero_repositories_has_explicit_empty_state(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn("repositories.length === 0", js)
        self.assertIn("公開対象のrepositoryは0件です。", js)

    def test_activity_feed_uses_snapshot_activity_only(self):
        html = HTML.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('id="activity-feed"', html)
        self.assertIn("snapshot.activity", js)
        self.assertIn("ACTIVITY_LIMIT = 20", js)
        self.assertIn("b.occurredAt.localeCompare(a.occurredAt)", js)
        self.assertIn("item.repositoryId", js)
        self.assertIn("item.occurredAt", js)
        self.assertIn("item.url", js)
        self.assertIn("ACTIVITY_LABELS[item.kind]", js)
        self.assertIn("最近の活動は0件です。", js)
        self.assertNotIn("api.github.com", js)

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
