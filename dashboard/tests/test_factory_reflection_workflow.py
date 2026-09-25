from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "factory-reflection.yml"


class FactoryReflectionWorkflowContractTests(unittest.TestCase):
    def test_factory_completion_events_trigger_reflection_scan(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        for workflow_name in (
            "Factory Repair Agent",
            "Factory Autonomous Merge",
            "Factory Production Recovery",
            "Refresh Repository Recall Index",
        ):
            self.assertIn(f"- {workflow_name}", text)

        self.assertIn("workflow_run:", text)
        self.assertIn("types:\n      - completed", text)
        self.assertIn("github.event_name == 'workflow_run'", text)
        self.assertIn("python -m dashboard.factory_reflection", text)


if __name__ == "__main__":
    unittest.main()
