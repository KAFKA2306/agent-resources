import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "docs" / "dashboard" / "index.html"
CSS = ROOT / "docs" / "dashboard" / "dashboard.css"


class DashboardSkeletonTest(unittest.TestCase):
    def test_dashboard_has_main_and_sidebar(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('<main class="main-panel"', html)
        self.assertIn('<aside class="sidebar"', html)
        self.assertIn('name="viewport"', html)

    def test_mobile_layout_collapses_to_one_column(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", css)

    def test_dashboard_keeps_link_to_existing_home(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('href="../"', html)


if __name__ == "__main__":
    unittest.main()
