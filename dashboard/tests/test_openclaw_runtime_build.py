import json
import unittest
from pathlib import Path

from dashboard.build import build_snapshot, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "dashboard.schema.json").read_text(encoding="utf-8"))


class OpenClawRuntimeBuildTest(unittest.TestCase):
    def test_optional_runtime_is_canonical_and_schema_valid(self):
        runtime = {
            "scope": "domain-agents",
            "collectedAt": "2026-08-20T10:00:00Z",
            "agents": [
                {"id": "finance", "sessionCount": 2, "models": ["openai/gpt", "llama-cpp/local"], "secret": "strip"}
            ],
            "automations": [
                {"id": "job", "agentId": "finance", "name": "Finance hourly", "status": "running", "message": "strip"}
            ],
            "private": "strip",
        }
        snapshot = build_snapshot([], [], [], openclaw_runtime=runtime, generated_at="2026-08-20T10:01:00Z")
        self.assertEqual(snapshot["openclawRuntime"]["scope"], "domain-agents")
        self.assertNotIn("secret", snapshot["openclawRuntime"]["agents"][0])
        self.assertNotIn("message", snapshot["openclawRuntime"]["automations"][0])
        self.assertNotIn("private", snapshot["openclawRuntime"])
        validate_snapshot(snapshot, SCHEMA)

    def test_non_domain_runtime_scope_fails_closed(self):
        with self.assertRaises(ValueError):
            build_snapshot(
                [],
                [],
                [],
                openclaw_runtime={"scope": "all", "collectedAt": "2026-08-20T10:00:00Z", "agents": [], "automations": []},
                generated_at="2026-08-20T10:01:00Z",
            )


if __name__ == "__main__":
    unittest.main()
