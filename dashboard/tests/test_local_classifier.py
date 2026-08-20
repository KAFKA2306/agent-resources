import unittest

from dashboard.operations.local_classifier import (
    LocalClassificationError,
    classify_inventory,
    repository_fingerprint,
    validate_classification,
)


class LocalClassifierTest(unittest.TestCase):
    def inventory(self):
        return {
            "schemaVersion": 1,
            "scope": "public-nonarchived-owned-repositories",
            "owner": "KAFKA2306",
            "repositories": [
                {
                    "name": "finance-repo",
                    "fullName": "KAFKA2306/finance-repo",
                    "group": "finance",
                    "classificationSource": "agent-zone-topic",
                    "description": "financial data",
                    "language": "Python",
                    "fork": False,
                    "topics": ["agent-zone-finance"],
                    "updatedAt": "2026-08-20T00:00:00Z",
                },
                {
                    "name": "vr-repo",
                    "fullName": "KAFKA2306/vr-repo",
                    "group": "vr-3d",
                    "classificationSource": "agent-zone-topic",
                    "description": "Unity VR",
                    "language": "C#",
                    "fork": False,
                    "topics": ["agent-zone-vr-3d"],
                    "updatedAt": "2026-08-20T00:00:00Z",
                },
                {
                    "name": "new-repo",
                    "fullName": "KAFKA2306/new-repo",
                    "group": "unclassified",
                    "classificationSource": "unclassified",
                    "description": "portfolio analysis and market data",
                    "language": "Python",
                    "fork": False,
                    "topics": ["stocks"],
                    "updatedAt": "2026-08-20T00:00:00Z",
                },
            ],
        }

    def runtime(self):
        return {
            "status": "READY",
            "base_url": "http://127.0.0.1:8080/v1",
            "served_model_id": "ornith-9b-q4",
            "revision": "a" * 40,
        }

    def test_only_unclassified_repository_is_inferred(self):
        calls = []

        def classifier(base_url, model, prompt):
            calls.append((base_url, model, prompt))
            return {"domain": "finance", "confidence": 0.94, "reason": "market metadata"}

        snapshot, state = classify_inventory(
            self.inventory(),
            self.runtime(),
            {"schemaVersion": 1, "entries": {}},
            classifier=classifier,
        )
        self.assertEqual(1, snapshot["summary"]["inferredCount"])
        self.assertEqual(2, snapshot["summary"]["explicitSkippedCount"])
        self.assertEqual(1, len(calls))
        self.assertEqual("KAFKA2306/new-repo", snapshot["classifications"][0]["repository"])
        self.assertEqual("finance", snapshot["classifications"][0]["suggestedGroup"])
        self.assertTrue(snapshot["classifications"][0]["acceptedForView"])
        self.assertIn("KAFKA2306/new-repo", state["entries"])

    def test_unchanged_unclassified_repository_reuses_cached_result(self):
        inventory = self.inventory()
        domains = ["finance", "vr-3d"]
        row = inventory["repositories"][2]
        fingerprint = repository_fingerprint(row, domains, "a" * 40)
        previous = {
            "repository": "KAFKA2306/new-repo",
            "fingerprint": fingerprint,
            "suggestedGroup": "finance",
            "confidence": 0.91,
            "acceptedForView": True,
            "reason": "cached",
            "modelRevision": "a" * 40,
            "classifiedAt": "2026-08-20T00:00:00Z",
        }

        def should_not_run(*args):
            raise AssertionError("classifier should not run for unchanged metadata")

        snapshot, _ = classify_inventory(
            inventory,
            self.runtime(),
            {"schemaVersion": 1, "entries": {"KAFKA2306/new-repo": previous}},
            classifier=should_not_run,
        )
        self.assertEqual(0, snapshot["summary"]["inferredCount"])
        self.assertEqual(1, snapshot["summary"]["reusedCount"])
        self.assertEqual("cached", snapshot["classifications"][0]["reason"])

    def test_model_revision_change_invalidates_cache(self):
        inventory = self.inventory()
        row = inventory["repositories"][2]
        previous = {
            "repository": "KAFKA2306/new-repo",
            "fingerprint": repository_fingerprint(row, ["finance", "vr-3d"], "b" * 40),
            "suggestedGroup": "finance",
            "confidence": 0.91,
            "acceptedForView": True,
            "reason": "old model",
            "modelRevision": "b" * 40,
            "classifiedAt": "2026-08-20T00:00:00Z",
        }
        calls = []

        def classifier(*args):
            calls.append(args)
            return {"domain": "finance", "confidence": 0.88, "reason": "new model"}

        snapshot, _ = classify_inventory(
            inventory,
            self.runtime(),
            {"schemaVersion": 1, "entries": {"KAFKA2306/new-repo": previous}},
            classifier=classifier,
        )
        self.assertEqual(1, len(calls))
        self.assertEqual(1, snapshot["summary"]["inferredCount"])

    def test_invalid_domain_is_rejected(self):
        with self.assertRaises(LocalClassificationError):
            validate_classification(
                {"domain": "not-allowed", "confidence": 1.0, "reason": "bad"},
                ["finance", "vr-3d"],
            )

    def test_low_confidence_suggestion_is_not_accepted_for_view(self):
        snapshot, _ = classify_inventory(
            self.inventory(),
            self.runtime(),
            {"schemaVersion": 1, "entries": {}},
            classifier=lambda *_: {
                "domain": "finance",
                "confidence": 0.42,
                "reason": "weak evidence",
            },
            threshold=0.8,
        )
        self.assertFalse(snapshot["classifications"][0]["acceptedForView"])


if __name__ == "__main__":
    unittest.main()
