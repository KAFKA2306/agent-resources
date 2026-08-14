import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "docs" / "dashboard"


class LaneFlowRetiredTest(unittest.TestCase):
    def test_lane_flow_diagram_is_not_part_of_dashboard(self):
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="lane-flow"', html)
        self.assertNotIn("flow.js", html)
        self.assertNotIn("flow.css", html)
        self.assertFalse((DASHBOARD / "flow.js").exists())
        self.assertFalse((DASHBOARD / "flow.css").exists())


if __name__ == "__main__":
    unittest.main()
