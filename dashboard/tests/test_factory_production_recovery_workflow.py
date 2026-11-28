from pathlib import Path
import unittest


class ProductionRecoveryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path(".github/workflows/factory-production-recovery.yml").read_text(encoding="utf-8")

    def test_only_runs_after_failed_release_verification(self):
        self.assertIn("- Verify Dashboard Release", self.text)
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", self.text)

    def test_refuses_stale_failure_revision(self):
        self.assertIn("main.sha !== failedSha", self.text)
        self.assertIn("refusing stale recovery", self.text)

    def test_recovery_is_bounded_against_oscillation(self):
        self.assertIn("startsWith('factory: revert production failure')", self.text)
        self.assertIn("refusing revert oscillation", self.text)

    def test_reverts_exact_failed_sha_on_isolated_branch(self):
        self.assertIn('git revert --no-edit "$FAILED_SHA"', self.text)
        self.assertIn('git switch -c "$branch"', self.text)
        self.assertIn("gh pr create", self.text)

    def test_recovery_pr_returns_to_normal_autonomous_merge_path(self):
        self.assertIn("normal exact-head validation + Vercel gate", self.text)
        self.assertNotIn("pulls.merge", self.text)


if __name__ == "__main__":
    unittest.main()
