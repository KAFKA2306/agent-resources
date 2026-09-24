import unittest

from dashboard.release_provenance import build_release_provenance, verify_release_provenance


class ReleaseProvenanceTests(unittest.TestCase):
    def test_manifest_binds_exact_revision_and_checksum(self):
        payload = build_release_provenance(revision="abc123", deployment_url="https://example.test", environment="production", run_id="42")
        self.assertEqual(payload["revision"], "abc123")
        self.assertEqual(len(payload["sha256"]), 64)
        verify_release_provenance(payload, expected_revision="abc123")

    def test_revision_mismatch_fails_closed(self):
        payload = build_release_provenance(revision="abc123", deployment_url="https://example.test", environment="production", run_id="42")
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            verify_release_provenance(payload, expected_revision="def456")

    def test_checksum_tampering_fails_closed(self):
        payload = build_release_provenance(revision="abc123", deployment_url="https://example.test", environment="production", run_id="42")
        payload["deploymentUrl"] = "https://tampered.test"
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            verify_release_provenance(payload, expected_revision="abc123")


if __name__ == "__main__":
    unittest.main()
