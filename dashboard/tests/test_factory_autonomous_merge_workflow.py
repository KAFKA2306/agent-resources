from pathlib import Path
import unittest


class AutonomousMergeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path(".github/workflows/factory-autonomous-merge.yml").read_text(encoding="utf-8")

    def test_is_triggered_only_after_dashboard_validation_completes(self):
        self.assertIn("workflow_run:", self.text)
        self.assertIn("- Validate Dashboard PR", self.text)
        self.assertIn("types:\n      - completed", self.text)

    def test_requires_successful_pr_validation(self):
        self.assertIn("github.event.workflow_run.event == 'pull_request'", self.text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.text)

    def test_repository_dispatch_proves_dispatched_exact_head_validation(self):
        self.assertIn("context.eventName === 'repository_dispatch'", self.text)
        self.assertIn(
            "repository_dispatch confirms successful exact-head dispatched validation",
            self.text,
        )
        self.assertIn("run.event === 'pull_request'", self.text)

    def test_binds_merge_to_exact_head_and_vercel_success(self):
        self.assertIn("pr.head.sha === headSha", self.text)
        self.assertIn("vercel.state !== 'success'", self.text)
        self.assertIn("sha: expected", self.text)

    def test_refuses_drafts_and_changed_heads(self):
        self.assertIn("!pr.draft", self.text)
        self.assertIn("pr.head.sha !== expected", self.text)

    def test_requires_exact_head_check_runs_to_finish_green(self):
        self.assertIn("checks: read", self.text)
        self.assertIn("github.rest.checks.listForRef", self.text)
        self.assertIn("acceptedConclusions", self.text)
        self.assertIn("exact-head checks failed", self.text)
        self.assertIn("exact-head checks did not settle", self.text)

    def test_routes_exact_merge_conflict_to_bounded_repair(self):
        self.assertIn("actions: write", self.text)
        self.assertIn("pr.mergeable === false", self.text)
        self.assertIn("github.rest.actions.createWorkflowDispatch", self.text)
        self.assertIn("workflow_id: 'factory-conflict-repair.yml'", self.text)
        self.assertIn("expected_head_sha: headSha", self.text)
        self.assertIn("expected_base_sha: pr.base.sha", self.text)
        self.assertIn("pr.mergeable == null", self.text)
        self.assertIn("refusing optimistic merge", self.text)


if __name__ == "__main__":
    unittest.main()
