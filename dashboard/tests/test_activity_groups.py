import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
TIMELINE_CSS = ROOT / "docs" / "dashboard" / "activity-timeline.css"


class ActivityGroupsTest(unittest.TestCase):
    def test_activity_is_grouped_by_day_then_repository(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("function groupActivity(items)", js)
        self.assertIn("const dayKey = localDayKey(item.occurredAt);", js)
        self.assertIn("day.repositories.has(item.repositoryId)", js)
        self.assertIn('daySection.className = "activity-day"', js)
        self.assertIn('card.className = "activity-repository-card"', js)
        self.assertIn("`${day.repositories.size} repos · ${formatActivityCounts(day.items)}`", js)

    def test_only_latest_repository_activity_is_open_by_default(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("card.append(repositoryHeading, createActivityItem(repositoryItems[0]));", js)
        self.assertIn("if (repositoryItems.length > 1)", js)
        self.assertIn('details.className = "activity-more"', js)
        self.assertIn("`残り${repositoryItems.length - 1}件を見る`", js)
        self.assertNotIn("details.open = true", js)

    def test_summary_keeps_standard_activity_counts_visible(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn('const ACTIVITY_COUNT_LABELS = { issue: "Issue", pull_request: "PR", workflow_run: "Run" };', js)
        self.assertIn("formatActivityCounts(repositoryItems)", js)
        self.assertIn('if (dayKey === localDayKey(today)) return "今日";', js)
        self.assertIn('if (dayKey === localDayKey(yesterday)) return "昨日";', js)

    def test_grouped_activity_remains_compact_on_mobile(self):
        css = TIMELINE_CSS.read_text(encoding="utf-8").replace(" ", "")
        self.assertIn(".activity-day{display:grid;gap:8px}", css)
        self.assertIn(".activity-repository-card{display:grid;gap:5px", css)
        self.assertIn(".activity-more>summary{cursor:pointer", css)
        self.assertIn("@media(max-width:760px)", css)


if __name__ == "__main__":
    unittest.main()
