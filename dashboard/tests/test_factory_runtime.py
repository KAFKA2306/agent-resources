import unittest

from dashboard.factory_runtime import (
    classify_workflow_failure,
    execute_remediation,
    remediate_workflow_run,
    workflow_run_to_signal,
)
from dashboard.factory_control import RemediationDecision, WorkItem


class FactoryRuntimeTests(unittest.TestCase):
    def test_flaky_failed_step_is_classified_for_single_rerun(self):
        run = {
            "id": 101,
            "name": "Factory Self-Heal Pilot",
            "status": "completed",
            "conclusion": "failure",
            "run_attempt": 1,
            "head_sha": "abc123",
            "html_url": "https://github.com/example/repo/actions/runs/101",
        }
        jobs = [
            {
                "steps": [
                    {
                        "name": "flaky-self-heal-probe",
                        "conclusion": "failure",
                    }
                ]
            }
        ]

        signal = workflow_run_to_signal(
            owner="example",
            repository="repo",
            run=run,
            jobs=jobs,
        )

        self.assertEqual(signal["kind"], "flaky_test")
        self.assertEqual(signal["source_id"], "101")
        self.assertEqual(signal["failed_steps"], ["flaky-self-heal-probe"])

    def test_unknown_failure_is_not_promoted_to_flaky(self):
        run = {
            "id": 102,
            "name": "CI",
            "status": "completed",
            "conclusion": "failure",
        }
        jobs = [{"steps": [{"name": "compile", "conclusion": "failure"}]}]

        self.assertEqual(classify_workflow_failure(run, jobs), "unknown")

    def test_timed_out_run_is_runner_unavailable(self):
        run = {
            "id": 103,
            "name": "CI",
            "status": "completed",
            "conclusion": "timed_out",
        }

        self.assertEqual(classify_workflow_failure(run, []), "runner_unavailable")

    def test_executor_only_mutates_allowlisted_workflow_actions(self):
        calls = []

        def mutation_fn(url, token=None, **kwargs):
            calls.append((url, token, kwargs))
            return {}, {}

        work_item = WorkItem(
            task_id="factory:1",
            owner="example",
            repository="repo",
            source_kind="workflow_run",
            source_id="123",
            fingerprint="fp",
            failure_class="flaky_test",
        )
        decision = RemediationDecision(
            action="rerun_once",
            terminal=False,
            reason="flaky_test",
        )

        result = execute_remediation(
            decision,
            work_item,
            token="token",
            mutation_fn=mutation_fn,
        )

        self.assertEqual(result.status, "EXECUTED")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith("/actions/runs/123/rerun-failed-jobs"))
        self.assertEqual(calls[0][2]["method"], "POST")

    def test_unknown_diagnosis_is_deferred_without_mutation(self):
        calls = []
        work_item = WorkItem(
            task_id="factory:2",
            owner="example",
            repository="repo",
            source_kind="workflow_run",
            source_id="124",
            fingerprint="fp",
            failure_class="unknown",
        )
        decision = RemediationDecision(
            action="diagnose",
            terminal=False,
            reason="unknown_failure_requires_bounded_diagnosis",
        )

        result = execute_remediation(
            decision,
            work_item,
            mutation_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        self.assertEqual(result.status, "DEFERRED")
        self.assertEqual(calls, [])

    def test_real_adapter_to_executor_reruns_first_flaky_attempt(self):
        run = {
            "id": 125,
            "name": "Factory Self-Heal Pilot",
            "status": "completed",
            "conclusion": "failure",
            "run_attempt": 1,
            "head_sha": "sha1",
            "html_url": "https://github.com/example/repo/actions/runs/125",
        }
        jobs = {
            "jobs": [
                {
                    "steps": [
                        {
                            "name": "flaky-self-heal-probe",
                            "conclusion": "failure",
                        }
                    ]
                }
            ]
        }
        calls = []

        def request_fn(url, token=None):
            if url.endswith("/actions/runs/125"):
                return run, {}
            if url.endswith("/actions/runs/125/jobs?per_page=100"):
                return jobs, {}
            raise AssertionError(url)

        result = remediate_workflow_run(
            owner="example",
            repository="repo",
            run_id=125,
            request_fn=request_fn,
            mutation_fn=lambda url, token=None, **kwargs: calls.append((url, kwargs)) or ({}, {}),
        )

        self.assertEqual(result["status"], "EXECUTED")
        self.assertEqual(result["decision"]["action"], "rerun_once")
        self.assertEqual(len(calls), 1)

    def test_second_flaky_failure_stops_instead_of_infinite_rerun(self):
        run = {
            "id": 126,
            "name": "Factory Self-Heal Pilot",
            "status": "completed",
            "conclusion": "failure",
            "run_attempt": 2,
            "head_sha": "sha2",
            "html_url": "https://github.com/example/repo/actions/runs/126",
        }
        jobs = {
            "jobs": [
                {
                    "steps": [
                        {
                            "name": "flaky-self-heal-probe",
                            "conclusion": "failure",
                        }
                    ]
                }
            ]
        }
        calls = []

        def request_fn(url, token=None):
            if url.endswith("/actions/runs/126"):
                return run, {}
            return jobs, {}

        result = remediate_workflow_run(
            owner="example",
            repository="repo",
            run_id=126,
            request_fn=request_fn,
            mutation_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        self.assertEqual(result["status"], "TERMINAL")
        self.assertEqual(result["decision"]["reason"], "retry_budget_exhausted")
        self.assertEqual(calls, [])

    def test_successful_rerun_produces_no_work(self):
        run = {
            "id": 127,
            "name": "Factory Self-Heal Pilot",
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 2,
            "head_sha": "sha3",
        }

        def request_fn(url, token=None):
            if url.endswith("/actions/runs/127"):
                return run, {}
            return {"jobs": []}, {}

        result = remediate_workflow_run(
            owner="example",
            repository="repo",
            run_id=127,
            request_fn=request_fn,
        )

        self.assertEqual(result["status"], "NO_WORK")


if __name__ == "__main__":
    unittest.main()
