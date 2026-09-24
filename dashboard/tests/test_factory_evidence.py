import tempfile
import unittest
from pathlib import Path

from dashboard.collectors.factory_evidence import collect_factory_evidence


class FactoryEvidenceCollectorTests(unittest.TestCase):
    def _repo_root(self, root: Path) -> Path:
        files = {
            ".github/workflows/factory-evidence-observer.yml": "name: Factory Evidence Observer\n",
            ".github/workflows/factory-autonomous-merge.yml": "name: Factory Autonomous Merge\n",
            ".github/workflows/dashboard-release-verify.yml": "name: Verify Dashboard Release\n",
            ".github/workflows/factory-production-recovery.yml": "name: Factory Production Recovery\n",
            ".github/workflows/docs.yml": (
                "python -m dashboard.collectors.factory_evidence\n"
                "factory-state.json\n"
                "https://api.github.com/repos/example/repo/commits/main\n"
            ),
            "dashboard/collectors/factory_evidence.py": "# collector\n",
            "docs/dashboard/factory-evidence.js": "// ui\n",
            "dashboard/factory_control.py": (
                '_POLICY = {"deterministic_test_failure": ("repair_agent", 1)}\n'
                'ROUTABLE_FAILURES = frozenset({"runner_unavailable"})\n'
                'reason="retry_budget_exhausted"\n'
            ),
            "dashboard/factory_runtime.py": 'if decision.action == "repair_agent":\n    pass\n',
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def _request(self, url, _token):
        if url.endswith("/commits/main"):
            return {"sha": "abc123"}, {}
        if url.endswith("/issues/381"):
            return {
                "number": 381,
                "title": "Canonical factory",
                "state": "open",
                "updated_at": "2026-09-25T00:00:00Z",
                "html_url": "https://github.com/KAFKA2306/agent-resources/issues/381",
            }, {}
        if "/pulls?" in url:
            return [
                {
                    "number": 7,
                    "title": "active",
                    "draft": False,
                    "updated_at": "2026-09-25T00:01:00Z",
                    "html_url": "https://github.com/KAFKA2306/agent-resources/pull/7",
                    "head": {"sha": "head7"},
                }
            ], {}
        if "factory-evidence-observer.yml/runs" in url:
            return {
                "workflow_runs": [
                    {
                        "id": 99,
                        "head_sha": "abc123",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://github.com/KAFKA2306/agent-resources/actions/runs/99",
                    }
                ]
            }, {}
        raise AssertionError(f"unexpected URL: {url}")

    def test_current_main_is_bound_to_machine_readable_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repo_root(Path(temporary))
            payload = collect_factory_evidence(
                expected_revision="abc123",
                run_id="1234",
                request_fn=self._request,
                repo_root=root,
                generated_at="2026-09-25T00:02:00Z",
            )

        self.assertEqual(payload["sourceRevision"], "abc123")
        self.assertEqual(payload["pages"]["workflowRunId"], "1234")
        self.assertEqual(payload["observer"]["state"], "VERIFIED")
        self.assertEqual(payload["observer"]["headSha"], "abc123")
        self.assertEqual(payload["canonicalIssue"]["number"], 381)
        self.assertEqual(payload["activePullRequests"][0]["headSha"], "head7")

        states = {item["id"]: item["state"] for item in payload["capabilities"]}
        self.assertEqual(states["pages-current-evidence"], "EXISTING")
        self.assertEqual(states["pages-freshness-gate"], "EXISTING")
        self.assertEqual(states["deterministic-repair"], "EXISTING")
        self.assertEqual(states["provider-runner-recovery"], "DISCONNECTED")
        self.assertEqual(states["general-diagnosis-patch"], "MISSING")

    def test_stale_checkout_fails_before_publishing(self):
        def only_main(url, _token):
            if url.endswith("/commits/main"):
                return {"sha": "new-main"}, {}
            raise AssertionError("collector must stop after detecting stale main")

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "source revision is stale"):
                collect_factory_evidence(
                    expected_revision="old-main",
                    run_id="1234",
                    request_fn=only_main,
                    repo_root=Path(temporary),
                )


if __name__ == "__main__":
    unittest.main()
