import unittest

from dashboard.domain.lanes import classify_lane


class LaneClassificationTest(unittest.TestCase):
    def test_open_issue_is_working(self):
        self.assertEqual(
            classify_lane({"kind": "issue", "state": "open"}),
            {"lane": "working", "laneReason": "open_issue"},
        )

    def test_open_pull_request_is_waiting(self):
        self.assertEqual(
            classify_lane({"kind": "pull_request", "state": "open"}),
            {"lane": "waiting", "laneReason": "open_pull_request"},
        )

    def test_workflow_in_progress_is_working(self):
        self.assertEqual(
            classify_lane({"kind": "workflow_run", "state": "in_progress"})["lane"],
            "working",
        )

    def test_successful_workflow_is_done(self):
        self.assertEqual(
            classify_lane({"kind": "workflow_run", "state": "completed"})["lane"],
            "done",
        )

    def test_failed_workflow_is_failed(self):
        self.assertEqual(
            classify_lane({"kind": "workflow_run", "state": "failed"})["lane"],
            "failed",
        )

    def test_unknown_state_is_not_done(self):
        result = classify_lane({"kind": "workflow_run", "state": "mystery"})
        self.assertEqual(result["lane"], "waiting")
        self.assertEqual(result["laneReason"], "unknown_state_requires_review")


if __name__ == "__main__":
    unittest.main()
