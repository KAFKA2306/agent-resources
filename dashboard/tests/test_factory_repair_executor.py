import unittest

from dashboard.factory_control import RemediationDecision, WorkItem
from dashboard.factory_runtime import execute_remediation


class FactoryRepairExecutorTests(unittest.TestCase):
    def test_deterministic_failure_dispatches_bounded_repair_workflow(self):
        calls = []
        item = WorkItem(
            task_id="factory:repair1",
            owner="example",
            repository="repo",
            source_kind="workflow_run",
            source_id="321",
            fingerprint="fingerprint-1",
            failure_class="deterministic_test_failure",
        )
        decision = RemediationDecision(
            action="repair_agent",
            terminal=False,
            reason="deterministic_test_failure",
        )

        result = execute_remediation(
            decision,
            item,
            token="token",
            mutation_fn=lambda url, token=None, **kwargs: calls.append((url, kwargs)) or ({}, {}),
        )

        self.assertEqual(result.status, "EXECUTED")
        self.assertEqual(len(calls), 1)
        url, kwargs = calls[0]
        self.assertTrue(url.endswith("/actions/workflows/factory-repair-agent.yml/dispatches"))
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["payload"]["ref"], "main")
        self.assertEqual(kwargs["payload"]["inputs"]["source_run_id"], "321")
        self.assertEqual(kwargs["payload"]["inputs"]["failure_fingerprint"], "fingerprint-1")

    def test_repair_executor_remains_workflow_run_only(self):
        calls = []
        item = WorkItem(
            task_id="factory:repair2",
            owner="example",
            repository="repo",
            source_kind="commit_status",
            source_id="44",
            fingerprint="fingerprint-2",
            failure_class="deterministic_test_failure",
        )
        decision = RemediationDecision("repair_agent", False, "deterministic_test_failure")
        result = execute_remediation(decision, item, mutation_fn=lambda *args, **kwargs: calls.append(1))
        self.assertEqual(result.status, "DEFERRED")
        self.assertEqual(calls, [])

    def test_repair_workflow_dispatches_exact_head_validation(self):
        from pathlib import Path

        workflow = Path(".github/workflows/factory-repair-agent.yml").read_text(encoding="utf-8")
        self.assertIn("actions: write", workflow)
        self.assertIn("gh workflow run dashboard-validate.yml", workflow)
        self.assertIn('-f head_sha="$repair_sha"', workflow)

    def test_repair_workflow_coalesces_workers_after_first_head_move(self):
        from pathlib import Path

        workflow = Path(".github/workflows/factory-repair-agent.yml").read_text(encoding="utf-8")
        self.assertIn("github.rest.pulls.get", workflow)
        self.assertIn("currentPr.head.sha !== sourcePr.head.sha", workflow)
        self.assertIn("NO_WORK:", workflow)
        self.assertEqual(workflow.count("if: steps.evidence.outputs.claimed == 'true'"), 4)
        self.assertIn("group: factory-repair-${{ inputs.failure_fingerprint }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_repair_workflow_handles_commit_time_validation_deterministically(self):
        from pathlib import Path

        workflow = Path(".github/workflows/factory-repair-agent.yml").read_text(encoding="utf-8")
        self.assertIn('*"Run commit-time validation"*)', workflow)
        self.assertIn("pre-commit run --all-files --hook-stage pre-commit || true", workflow)
        self.assertIn("pre-commit run --all-files --hook-stage pre-commit", workflow)
        self.assertIn('if git diff --quiet; then echo "repair rule produced no diff"', workflow)


if __name__ == "__main__":
    unittest.main()
