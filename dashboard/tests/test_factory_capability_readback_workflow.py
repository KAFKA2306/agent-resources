from pathlib import Path
import unittest


class FactoryCapabilityReadbackWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path('.github/workflows/factory-capability-readback.yml').read_text(encoding='utf-8')

    def test_routes_known_permission_failure_fingerprints_without_catching_every_failure(self):
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", self.text)
        self.assertIn('listJobsForWorkflowRun', self.text)
        self.assertIn('permission|authorization|commit generated lock|commit generated workflow', self.text)
        self.assertIn('NO_WORK: source run', self.text)

    def test_readback_remains_exact_revision_and_fail_closed(self):
        self.assertIn('run.head_sha !== expectedSha', self.text)
        self.assertIn('ref: expectedSha', self.text)
        self.assertIn('workflow_permissions_declared', self.text)
        self.assertIn("core.setFailed('source workflow has no explicit permissions block')", self.text)

    def test_gh_aw_sync_permission_failure_is_observed(self):
        self.assertIn('- Sync gh-aw lock files', self.text)


if __name__ == '__main__':
    unittest.main()
