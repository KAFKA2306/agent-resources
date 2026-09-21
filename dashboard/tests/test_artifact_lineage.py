import unittest

from dashboard.artifact_lineage import verify_artifact_lineage


class ArtifactLineageTests(unittest.TestCase):
    def test_exact_revision_and_sha256_pass(self):
        result = verify_artifact_lineage(
            expected_revision="abc123",
            artifacts=[
                {
                    "path": "dist/app.apk",
                    "revision": "abc123",
                    "sha256": "a" * 64,
                },
                {
                    "path": "dist/app.apk.sha256",
                    "revision": "abc123",
                    "sha256": "b" * 64,
                },
            ],
        )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.reason, "artifact_lineage_verified")

    def test_stale_revision_fails_closed(self):
        result = verify_artifact_lineage(
            expected_revision="abc123",
            artifacts=[
                {
                    "path": "dist/app.apk",
                    "revision": "old",
                    "sha256": "a" * 64,
                }
            ],
        )

        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.reason, "revision_mismatch:dist/app.apk")

    def test_missing_or_malformed_digest_fails_closed(self):
        malformed = verify_artifact_lineage(
            expected_revision="abc123",
            artifacts=[
                {
                    "path": "dist/app.apk",
                    "revision": "abc123",
                    "sha256": "not-a-sha256",
                }
            ],
        )
        empty = verify_artifact_lineage(expected_revision="abc123", artifacts=[])

        self.assertEqual(malformed.status, "UNVERIFIED")
        self.assertEqual(malformed.reason, "invalid_sha256:dist/app.apk")
        self.assertEqual(empty.status, "UNVERIFIED")
        self.assertEqual(empty.reason, "missing_artifacts")

    def test_duplicate_artifact_path_fails_closed(self):
        artifact = {
            "path": "dist/app.apk",
            "revision": "abc123",
            "sha256": "a" * 64,
        }
        result = verify_artifact_lineage(
            expected_revision="abc123",
            artifacts=[artifact, dict(artifact)],
        )

        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.reason, "duplicate_path:dist/app.apk")


if __name__ == "__main__":
    unittest.main()
