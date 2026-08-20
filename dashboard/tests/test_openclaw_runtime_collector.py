import json
import subprocess
import unittest

from dashboard.collectors.openclaw_runtime import build_runtime_snapshot, collect_openclaw_runtime


class OpenClawRuntimeCollectorTest(unittest.TestCase):
    def test_snapshot_filters_non_domain_agents_and_session_keys(self):
        snapshot = build_runtime_snapshot(
            {
                "sessions": [
                    {"agentId": "finance", "key": "agent:finance:private-session", "model": "llama-cpp/local"},
                    {"agentId": "finance", "key": "agent:finance:other", "model": "openai/gpt"},
                    {"agentId": "personal", "key": "agent:personal:secret", "model": "private/model"},
                ]
            },
            {
                "jobs": [
                    {"id": "finance-hourly", "agentId": "finance", "name": "Finance hourly", "status": "ok"},
                    {"id": "private-job", "agentId": "personal", "name": "Do not publish", "status": "error"},
                ]
            },
            collected_at="2026-08-20T10:00:00Z",
        )
        finance = next(row for row in snapshot["agents"] if row["id"] == "finance")
        self.assertEqual(finance["sessionCount"], 2)
        self.assertEqual(finance["models"], ["llama-cpp/local", "openai/gpt"])
        self.assertEqual([job["id"] for job in snapshot["automations"]], ["finance-hourly"])
        serialized = json.dumps(snapshot)
        self.assertNotIn("private-session", serialized)
        self.assertNotIn("personal", serialized)
        self.assertNotIn("Do not publish", serialized)

    def test_unknown_automation_status_is_explicit(self):
        snapshot = build_runtime_snapshot(
            {"sessions": []},
            {"jobs": [{"id": "job", "agentId": "games", "name": "Games hourly", "status": "future-state"}]},
            collected_at="2026-08-20T10:00:00Z",
        )
        self.assertEqual(snapshot["automations"][0]["status"], "unknown")

    def test_collect_uses_machine_readable_openclaw_commands(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            payload = {"sessions": []} if command[1] == "sessions" else {"jobs": []}
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        collect_openclaw_runtime(runner=runner, collected_at="2026-08-20T10:00:00Z")
        self.assertEqual(
            calls,
            [
                ["openclaw", "sessions", "--all-agents", "--limit", "100", "--json"],
                ["openclaw", "automations", "list", "--all", "--json"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
