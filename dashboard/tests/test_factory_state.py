import unittest

from dashboard.factory_state import build_factory_state, derive_workline_state


class FactoryStateTests(unittest.TestCase):
    def test_verified_requires_merge_deploy_and_probe(self):
        base = {"id": 1, "conclusion": "success", "merged": True, "deployed": True}
        self.assertEqual(derive_workline_state(base)["state"], "PROBING")
        self.assertEqual(derive_workline_state({**base, "probed": True})["state"], "VERIFIED")

    def test_failure_is_not_pass(self):
        item = derive_workline_state({"id": 390, "stage": "write_back", "conclusion": "failure", "failure_class": "permission_mismatch"})
        self.assertEqual(item["state"], "SELF_HEALING")
        self.assertEqual(item["stage"], "WRITE_BACK")

    def test_genuine_human_authority_is_explicit(self):
        item = derive_workline_state({"id": 2, "failure_class": "initial_external_auth"})
        self.assertEqual(item["state"], "HUMAN_AUTHORITY")

    def test_metrics_are_derived_not_decorative(self):
        state = build_factory_state([
            {"id": 1, "conclusion": "success", "merged": True, "deployed": True, "probed": True, "started_at": "2026-09-22T00:00:00Z", "updated_at": "2026-09-22T00:10:00Z"},
            {"id": 2, "conclusion": "failure", "failure_class": "flaky_test", "self_healed": True, "retried": True},
            {"id": 3, "conclusion": "failure", "failure_class": "permission_mismatch", "human_intervention": True},
        ], main_sha="abc", generated_at="2026-09-22T01:00:00Z")
        self.assertAlmostEqual(state["metrics"]["e2eYield"], 1/3)
        self.assertEqual(state["metrics"]["firstPassYield"], 1.0)
        self.assertEqual(state["metrics"]["selfHealRate"], 0.5)
        self.assertAlmostEqual(state["metrics"]["humanInterventionRate"], 1/3)
        self.assertEqual(state["metrics"]["meanLeadTimeSeconds"], 600)
        self.assertEqual(state["failurePareto"][0]["count"], 1)


if __name__ == "__main__":
    unittest.main()
