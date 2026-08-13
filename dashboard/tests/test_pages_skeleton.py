import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "docs" / "dashboard" / "index.html"
CSS = ROOT / "docs" / "dashboard" / "dashboard.css"
JS = ROOT / "docs" / "dashboard" / "dashboard.js"


class DashboardSkeletonTest(unittest.TestCase):
    def test_dashboard_has_main_and_sidebar(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('<main class="main-panel"', html)
        self.assertIn('<aside class="sidebar"', html)
        self.assertIn('name="viewport"', html)

    def test_mobile_layout_collapses_to_one_column(self):
        css = CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("grid-template-columns:minmax(0,1fr);", css)

    def test_dashboard_keeps_link_to_existing_home(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('href="../"', html)

    def test_repository_groups_are_loaded_from_dashboard_json(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('fetch("./dashboard.json"', js)
        self.assertIn("repository.group", js)
        self.assertIn("repository.url", js)
        self.assertNotIn("agent-resources", js.lower())

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


if __name__ == "__main__":
    unittest.main()
