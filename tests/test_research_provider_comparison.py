from __future__ import annotations

import copy
import hashlib
import unittest

from scripts.research_provider_comparison import ContractError, evaluate


def metrics(**overrides):
    base = {
        "primary_source_ratio": 1.0,
        "fresh_source_count": 1,
        "contradictions_detected": 0,
        "stale_or_duplicate_results": 0,
        "unverifiable_claims": 0,
        "newest_source_age_hours": 4,
        "input_context_bytes": 1000,
        "repeated_static_context_bytes": 100,
        "unnecessary_reads": 1,
        "heavy_research_invocations": 1,
        "human_interventions": 0,
        "handoff_failures": 0,
        "skipped_or_delayed_executions": 0,
        "duplicate_executions": 0,
    }
    base.update(overrides)
    return base


def provider(name, *, status="COMPLETED", result="MATERIAL_DELTA", observed_metrics=None):
    return {
        "name": name,
        "route": f"{name}-route",
        "status": status,
        "result": result,
        "observation_window": {
            "start": "2026-09-14T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
        },
        "sources": []
        if status != "COMPLETED"
        else [
            {
                "url": f"https://example.com/{name}",
                "revision": "rev-1",
                "primary": True,
                "contradiction": False,
            }
        ],
        "metrics": observed_metrics or metrics(),
    }


def payload():
    return {
        "version": 1,
        "task": {
            "id": "research-data-agent",
            "static_context_sha256": hashlib.sha256(b"bounded contract").hexdigest(),
            "current_delta_since": "2026-09-14T00:00:00Z",
            "owner_repository": "KAFKA2306/agent-resources",
            "handoff_issue": 344,
        },
        "observation_window": {
            "start": "2026-09-14T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
        },
        "current_provider": "chatgpt",
        "candidate_provider": "gemini",
        "providers": [provider("chatgpt"), provider("gemini")],
    }


class ResearchProviderComparisonTest(unittest.TestCase):
    def test_reallocate_only_when_candidate_dominates_and_schedule_switch_is_safe(self):
        data = payload()
        data["providers"][1]["metrics"] = metrics(
            input_context_bytes=800,
            repeated_static_context_bytes=0,
            unnecessary_reads=0,
        )
        data["schedule_transition"] = {
            "stop_schedule_id": "research-chatgpt",
            "start_schedule_id": "research-gemini",
            "stop_before_start": True,
        }
        self.assertEqual(evaluate(data)["decision"], "REALLOCATE")

    def test_provider_unavailable_is_explicit_and_not_silently_scored(self):
        data = payload()
        data["providers"][1] = provider(
            "gemini", status="UNAVAILABLE", result="UNAVAILABLE"
        )
        result = evaluate(data)
        self.assertEqual(result["decision"], "UNAVAILABLE")
        self.assertEqual(result["provider_states"]["gemini"]["status"], "UNAVAILABLE")

    def test_no_material_delta_is_valid_with_zero_fresh_sources(self):
        data = payload()
        for item in data["providers"]:
            item["result"] = "NO_MATERIAL_DELTA"
            item["metrics"] = metrics(
                primary_source_ratio=0,
                fresh_source_count=0,
                contradictions_detected=0,
            )
            item["sources"] = []
        self.assertEqual(evaluate(data)["decision"], "KEEP_CURRENT")

    def test_duplicate_source_revision_is_rejected_instead_of_double_counted(self):
        data = payload()
        data["providers"][0]["sources"].append(
            copy.deepcopy(data["providers"][0]["sources"][0])
        )
        with self.assertRaisesRegex(ContractError, "duplicate source/revision"):
            evaluate(data)

    def test_reallocate_rejects_duplicate_or_start_first_schedule_contract(self):
        data = payload()
        data["providers"][1]["metrics"] = metrics(input_context_bytes=800)
        data["schedule_transition"] = {
            "stop_schedule_id": "same",
            "start_schedule_id": "same",
            "stop_before_start": False,
        }
        with self.assertRaises(ContractError):
            evaluate(data)

    def test_previous_source_revision_cannot_be_recounted_as_current_delta(self):
        data = payload()
        source = data["providers"][0]["sources"][0]
        data["task"]["previous_source_revisions"] = [
            {"url": source["url"], "revision": source["revision"]}
        ]
        with self.assertRaisesRegex(ContractError, "cannot be recounted"):
            evaluate(data)

    def test_contradiction_evidence_survives_handoff(self):
        data = payload()
        source = data["providers"][0]["sources"][0]
        source["contradiction"] = True
        data["providers"][0]["metrics"]["contradictions_detected"] = 1
        result = evaluate(data)
        self.assertEqual(
            result["contradictions"],
            [
                {
                    "provider": "chatgpt",
                    "url": source["url"],
                    "revision": source["revision"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
