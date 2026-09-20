import unittest

from dashboard.factory_control import (
    RouteCandidate,
    classify_failure,
    decide_remediation,
    intervention_is_automation_gap,
    stable_task_id,
)


class FactoryControlTests(unittest.TestCase):
    def test_same_evidence_has_same_task_id_and_different_failure_does_not(self):
        base = dict(
            owner="KAFKA2306",
            repository="agent-resources",
            source_kind="workflow_run",
            source_id="34043147234",
        )
        first = stable_task_id(**base, fingerprint="unsupported-model")
        repeated = stable_task_id(**base, fingerprint="unsupported-model")
        changed = stable_task_id(**base, fingerprint="runner-offline")

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, changed)

    def test_unknown_state_never_becomes_success(self):
        self.assertEqual(classify_failure({}), "unknown")
        decision = decide_remediation(failure_class="unknown", attempt=0)

        self.assertFalse(decision.terminal)
        self.assertEqual(decision.action, "diagnose")

    def test_transient_failure_has_bounded_retry_budget(self):
        first = decide_remediation(failure_class="transient_network", attempt=0)
        second = decide_remediation(failure_class="transient_network", attempt=1)
        exhausted = decide_remediation(failure_class="transient_network", attempt=2)

        self.assertEqual(first.action, "retry_with_backoff")
        self.assertEqual(second.action, "retry_with_backoff")
        self.assertTrue(exhausted.terminal)
        self.assertEqual(exhausted.reason, "retry_budget_exhausted")

    def test_unsupported_model_reroutes_only_to_approved_available_capable_route(self):
        routes = [
            RouteCandidate(
                "blocked-fast",
                frozenset({"coding"}),
                available=False,
                priority=1,
            ),
            RouteCandidate(
                "unapproved",
                frozenset({"coding"}),
                approved=False,
                priority=2,
            ),
            RouteCandidate(
                "approved-coding",
                frozenset({"coding", "tools"}),
                priority=3,
            ),
            RouteCandidate(
                "approved-research",
                frozenset({"research"}),
                priority=1,
            ),
        ]

        decision = decide_remediation(
            failure_class="unsupported_model",
            attempt=0,
            routes=routes,
            required_capabilities={"coding"},
            failed_route="old-model",
        )

        self.assertFalse(decision.terminal)
        self.assertEqual(decision.action, "reroute")
        self.assertEqual(decision.route, "approved-coding")

    def test_route_failure_stops_unverified_when_no_safe_alternate_exists(self):
        decision = decide_remediation(
            failure_class="provider_unavailable",
            attempt=0,
            routes=[
                RouteCandidate(
                    "unapproved-fallback",
                    frozenset({"coding"}),
                    approved=False,
                )
            ],
            required_capabilities={"coding"},
        )

        self.assertTrue(decision.terminal)
        self.assertEqual(decision.action, "terminal_unverified")

    def test_permission_mismatch_is_repairable_not_human_input(self):
        decision = decide_remediation(failure_class="permission_mismatch", attempt=0)

        self.assertFalse(decision.terminal)
        self.assertEqual(decision.action, "capability_readback")
        self.assertTrue(intervention_is_automation_gap("permission_mismatch"))

    def test_genuine_human_authority_is_terminal_exception(self):
        decision = decide_remediation(failure_class="legal_decision", attempt=0)

        self.assertTrue(decision.terminal)
        self.assertEqual(decision.action, "external_authority")
        self.assertFalse(intervention_is_automation_gap("legal_decision"))


if __name__ == "__main__":
    unittest.main()
