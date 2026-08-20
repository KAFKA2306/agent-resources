import json
import unittest

from dashboard.operations.combine import combine_operations_snapshot


class RepositoryOperationsCombineTest(unittest.TestCase):
    def inventory(self):
        return {
            "schemaVersion": 1,
            "scope": "public-nonarchived-owned-repositories",
            "owner": "KAFKA2306",
            "collectedAt": "2026-08-21T00:00:00Z",
            "repositories": [
                {
                    "id": "R_1",
                    "name": "example",
                    "fullName": "KAFKA2306/example",
                    "url": "https://github.com/KAFKA2306/example",
                    "defaultBranch": "main",
                    "group": "agent-web",
                    "classificationSource": "agent-zone-topic",
                    "topics": ["agent-zone-agent-web"],
                    "updatedAt": "2026-08-20T00:00:00Z",
                }
            ],
            "summary": {"repositoryCount": 1, "classifiedCount": 1, "unclassifiedCount": 0},
        }

    def branches(self):
        return {
            "schemaVersion": 1,
            "scope": "public-nonarchived-owned-repositories",
            "owner": "KAFKA2306",
            "collectedAt": "2026-08-21T01:00:00Z",
            "apply": False,
            "policy": {},
            "branches": [
                {
                    "repository": "KAFKA2306/example",
                    "branch": "feature/old",
                    "tip_sha": "a" * 40,
                    "status": "candidate",
                    "reason": "awaiting_second_scan",
                    "commit_date": "2026-06-01T00:00:00Z",
                    "first_seen": "2026-08-21T01:00:00Z",
                    "confirmed_at": None,
                }
            ],
            "summary": {"candidateCount": 1, "confirmedCount": 0, "deletedCount": 0, "blockedCount": 0},
        }

    def test_snapshot_strips_tips_topics_and_other_internal_fields(self):
        result = combine_operations_snapshot(self.inventory(), self.branches())
        self.assertEqual(1, result["summary"]["repositoryCount"])
        self.assertEqual(1, result["summary"]["candidateCount"])
        rendered = json.dumps(result)
        self.assertNotIn("tip_sha", rendered)
        self.assertNotIn("topics", rendered)
        self.assertNotIn("defaultBranch", rendered)
        self.assertEqual("agent-zone-topic", result["repositories"][0]["classificationSource"])

    def test_branch_outside_inventory_fails_closed(self):
        branches = self.branches()
        branches["branches"][0]["repository"] = "KAFKA2306/private-repo"
        with self.assertRaises(ValueError):
            combine_operations_snapshot(self.inventory(), branches)


if __name__ == "__main__":
    unittest.main()
