import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD_JS = ROOT / "docs" / "dashboard" / "world.js"
WORLD_CSS = ROOT / "docs" / "dashboard" / "world.css"


class WorkItemCollapseTest(unittest.TestCase):
    def test_busy_issue_and_pull_request_lists_start_collapsed(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        css = WORLD_CSS.read_text(encoding="utf-8").replace(" ", "")

        self.assertIn("const WORK_ITEM_COLLAPSE_THRESHOLD = 4;", js)
        self.assertIn('item.kind === "issue" || item.kind === "pull_request"', js)
        self.assertIn("issuePullRequests.length <= WORK_ITEM_COLLAPSE_THRESHOLD", js)
        self.assertIn('details.className = "world-work-details"', js)
        self.assertNotIn("details.open = true", js[js.index('details.className = "world-work-details"'):js.index("function createSurfaceIcon")])
        self.assertIn("issuePullRequestSummary(issuePullRequests)", js)
        self.assertIn(".world-work-details>summary{cursor:pointer", css)

    def test_non_issue_items_remain_visible_when_issue_list_is_collapsed(self):
        js = WORLD_JS.read_text(encoding="utf-8")
        self.assertIn('item.kind !== "issue" && item.kind !== "pull_request"', js)
        self.assertIn("if (alwaysVisible.length)", js)
        self.assertIn("container.append(createAgentList(alwaysVisible", js)


if __name__ == "__main__":
    unittest.main()
