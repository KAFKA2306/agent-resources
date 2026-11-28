import unittest

from dashboard.production_snapshot_smoke import (
    FactoryStateRevisionMismatch,
    validate_factory_state,
    wait_for_production_factory_state,
)


def make_factory_state(*, revision="abc123", generated_at="2026-08-15T08:15:00Z"):
    return {
        "generatedAt": generated_at,
        "sourceRevision": revision,
        "authority": {"mainSha": revision},
        "pages": {
            "sourceRevision": revision,
            "workflowRunId": "1234",
            "workflowRunUrl": "https://github.com/KAFKA2306/agent-resources/actions/runs/1234",
        },
        "canonicalIssue": {"number": 381},
        "capabilities": [
            {"id": "observe-classify", "state": "UNVERIFIED"},
            {"id": "autonomous-merge", "state": "VERIFIED"},
        ],
    }


class ProductionSnapshotSmokeTest(unittest.TestCase):
    def test_accepts_snapshot_bound_to_expected_revision(self):
        validate_factory_state(make_factory_state(), expected_sha="abc123")

    def test_rejects_snapshot_from_another_revision(self):
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            validate_factory_state(make_factory_state(revision="old"), expected_sha="abc123")

    def test_rejects_snapshot_with_wrong_authority(self):
        payload = make_factory_state()
        payload["authority"]["mainSha"] = "other"
        with self.assertRaisesRegex(ValueError, "authority"):
            validate_factory_state(payload, expected_sha="abc123")

    def test_rejects_missing_or_invalid_generation_time(self):
        for generated_at in (None, "", "not-a-date", "2026-08-15T08:15:00"):
            with (
                self.subTest(generated_at=generated_at),
                self.assertRaisesRegex(ValueError, "generatedAt"),
            ):
                validate_factory_state(
                    make_factory_state(generated_at=generated_at), expected_sha="abc123"
                )

    def test_rejects_incomplete_pages_provenance(self):
        payload = make_factory_state()
        del payload["pages"]["workflowRunId"]
        with self.assertRaisesRegex(ValueError, "Pages provenance"):
            validate_factory_state(payload, expected_sha="abc123")

    def test_keeps_unverified_capability_as_recorded(self):
        payload = make_factory_state()
        validate_factory_state(payload, expected_sha="abc123")
        self.assertEqual(payload["capabilities"][0]["state"], "UNVERIFIED")

    def test_wait_retries_only_until_pages_reaches_the_expected_revision(self):
        responses = [
            make_factory_state(revision="old"),
            make_factory_state(revision="abc123"),
        ]
        sleeps = []

        def fetch_json(_url):
            return responses.pop(0)

        factory = wait_for_production_factory_state(
            "https://agent-resources-one.vercel.app",
            "abc123",
            timeout_seconds=5,
            fetch_json=fetch_json,
            sleep=sleeps.append,
        )

        self.assertEqual(factory["sourceRevision"], "abc123")
        self.assertEqual(sleeps, [5])

    def test_timeout_does_not_promote_a_stale_pages_snapshot(self):
        with self.assertRaises(FactoryStateRevisionMismatch):
            wait_for_production_factory_state(
                "https://agent-resources-one.vercel.app",
                "abc123",
                timeout_seconds=0,
                fetch_json=lambda _url: make_factory_state(revision="old"),
                sleep=lambda _seconds: self.fail("zero-timeout wait must not sleep"),
            )


if __name__ == "__main__":
    unittest.main()
