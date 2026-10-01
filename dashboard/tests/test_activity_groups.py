import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
DASHBOARD_CSS = ROOT / "docs" / "dashboard" / "dashboard.css"


class ActivityGroupsTest(unittest.TestCase):
    def test_activity_is_plotted_by_day_and_event_kind(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn("const days = [...new Set(items.map((item) => localDayKey(item.occurredAt)))].sort();", js)
        self.assertIn("const xForDay = (day) =>", js)
        self.assertIn('workflow_run: { y: 78, label: "RUN" }', js)
        self.assertIn('pull_request: { y: 155, label: "PR" }', js)
        self.assertIn('issue: { y: 232, label: "ISSUE" }', js)
        self.assertIn('svg.classList.add("activity-pulse-plot")', js)
        self.assertIn('envelope.classList.add("pulse-envelope")', js)

    def test_every_activity_event_remains_a_clickable_signal(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn('anchor.setAttribute("href", item.url);', js)
        self.assertIn('anchor.classList.add("activity-pulse-point"', js)
        self.assertIn('anchor.setAttribute(', js)
        self.assertIn('"aria-label"', js)
        self.assertIn('const title = document.createElementNS(SVG_NS, "title");', js)

    def test_pulse_keeps_compact_counts_and_time_axis(self):
        js = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertIn('counter.className = "pulse-counter"', js)
        self.assertIn('SIGNALS / 7D', js)
        self.assertIn('formatActivityDay(day)', js)
        self.assertIn('replace("今日", "TODAY")', js)
        self.assertIn('replace("昨日", "YDAY")', js)

    def test_pulse_plot_remains_compact_on_mobile(self):
        css = "".join(DASHBOARD_CSS.read_text(encoding="utf-8").split())
        self.assertIn(".activity-pulse-plot{display:block;width:100%;height:auto;min-height:210px}", css)
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn(".activity-pulse-plot{min-height:190px}", css)
        self.assertIn(".pulse-counter{position:static;", css)


if __name__ == "__main__":
    unittest.main()
