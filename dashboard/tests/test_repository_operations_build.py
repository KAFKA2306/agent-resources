import json
import unittest
from pathlib import Path

from dashboard.build import build_snapshot, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "dashboard.schema.json").read_text(encoding="utf-8"))


class RepositoryOperationsBuildTest(unittest.TestCase):
    def repository(self):
        return {
            "id": "R_1",
            "owner": "KAFKA2306",
            "name": "example",
            "url": "https://github.com/KAFKA2306/example",
            "group": "agent-web",
            "visibility": "public",
            "updatedAt": "2026-08-20T00:00:00Z",
        }

    def operations(self):
        return {
            "schemaVersion": 1,
            "scope": "public-nonarchived-owned-repositories",
            "owner": "KAFKA2306",
            "collectedAt": "2026-08-21T00:00:00Z",
            "repositories": [
                {
                    "name": "example",
                    "fullName": "KAFKA2306/example",
                    "url": "https://github.com/KAFKA2306/example",
                    "group": "agent-web",
                    "classificationSource": "agent-zone-topic",
                }
            ],
            "branches": [
                {
                    "repository": "KAFKA2306/example",
                    "branch": "feature/old",
                    "status": "candidate",
                    "reason": "awaiting_second_scan",
                    "commit_date": "2026-06-01T00:00:00Z",
                    "first_seen": "2026-08-21T00:00:00Z",
                }
            ],
            "summary": {
                "repositoryCount": 999,
                "classifiedCount": 999,
                "unclassifiedCount": 999,
                "candidateCount": 999,
                "confirmedCount": 999,
                "deletedCount": 999,
                "blockedCount": 999,
            },
        }

    def test_build_recomputes_summary_and_strips_unknown_fields(self):
        operations = self.operations()
        operations["repositories"][0]["topics"] = ["do-not-publish"]
        operations["branches"][0]["tip_sha"] = "a" * 40
        snapshot = build_snapshot(
            [self.repository()],
            [],
            [],
            repository_operations=operations,
            generated_at="2026-08-21T00:01:00Z",
        )
        ops = snapshot["repositoryOperations"]
        self.assertEqual(1, ops["summary"]["repositoryCount"])
        self.assertEqual(1, ops["summary"]["candidateCount"])
        rendered = json.dumps(ops)
        self.assertNotIn("do-not-publish", rendered)
        self.assertNotIn("tip_sha", rendered)
        self.assertEqual("2026-06-01T00:00:00Z", ops["branches"][0]["commitDate"])
        validate_snapshot(snapshot, SCHEMA)

    def test_private_or_unknown_repository_reference_fails_closed(self):
        operations = self.operations()
        operations["branches"][0]["repository"] = "KAFKA2306/private"
        with self.assertRaises(ValueError):
            build_snapshot(
                [self.repository()],
                [],
                [],
                repository_operations=operations,
                generated_at="2026-08-21T00:01:00Z",
            )


if __name__ == "__main__":
    unittest.main()
