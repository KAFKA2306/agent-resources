import json
import tempfile
import unittest
from pathlib import Path

from dashboard.collectors.github_api import GitHubApiError
from dashboard.repository_recall import (
    UNKNOWN_MATCH,
    UNKNOWN_PURPOSE,
    canonical_hash,
    collect_source_fact,
    inventory_names,
    merge_index,
    search_index,
    validate_coverage,
    validate_index,
)


class RepositoryRecallTests(unittest.TestCase):
    def repo(self, name, *, url=None):
        return {
            "id": f"R_{name}",
            "owner": "KAFKA2306",
            "name": name,
            "url": url or f"https://github.com/KAFKA2306/{name}",
            "visibility": "public",
            "archived": False,
            "updatedAt": "2026-08-18T00:00:00Z",
            "group": "unclassified",
            "publicLinks": [],
        }

    def facts(self, name, fingerprint="a" * 64):
        return {
            "name": name,
            "url": f"https://github.com/KAFKA2306/{name}",
            "sources": [
                {
                    "kind": "repository",
                    "url": f"https://github.com/KAFKA2306/{name}",
                    "status": "ok",
                    "fingerprint": "metadata-sha",
                },
                {
                    "kind": "readme",
                    "url": f"https://github.com/KAFKA2306/{name}/blob/main/README.md",
                    "status": "ok",
                    "fingerprint": "readme-sha",
                },
            ],
            "sourceFingerprint": fingerprint,
        }

    def entry(
        self,
        name,
        *,
        purpose="verified purpose",
        matches=None,
        not_for=None,
        fingerprint="a" * 64,
        checked_at="2026-08-18T00:00:00Z",
        needs_review=False,
    ):
        return {
            "name": name,
            "purpose": purpose,
            "matches": matches or ["verified requirement"],
            "notFor": not_for or [],
            "url": f"https://github.com/KAFKA2306/{name}",
            "sources": self.facts(name, fingerprint)["sources"],
            "sourceFingerprint": fingerprint,
            "checkedAt": checked_at,
            "needsReview": needs_review,
        }

    def test_inventory_names_are_unique_and_sorted(self):
        repositories = [self.repo("zeta"), self.repo("Alpha")]
        self.assertEqual(inventory_names(repositories), ["Alpha", "zeta"])
        with self.assertRaisesRegex(ValueError, "duplicate repository names"):
            inventory_names([self.repo("same"), self.repo("same")])

    def test_collect_source_fact_tracks_metadata_and_readme_fingerprints(self):
        repo = self.repo("unity-mcp")

        def request_fn(url, token):
            self.assertEqual(token, "token")
            if url.endswith("/readme"):
                return (
                    {
                        "sha": "readme-sha",
                        "html_url": "https://github.com/KAFKA2306/unity-mcp/blob/beta/README.md",
                    },
                    {},
                )
            return (
                {
                    "private": False,
                    "visibility": "public",
                    "archived": False,
                    "description": "Unity MCP",
                    "topics": ["unity", "mcp"],
                    "default_branch": "beta",
                },
                {},
            )

        result = collect_source_fact(repo, token="token", request_fn=request_fn)
        self.assertEqual(result["name"], "unity-mcp")
        self.assertEqual([source["status"] for source in result["sources"]], ["ok", "ok"])
        self.assertEqual(result["sources"][1]["fingerprint"], "readme-sha")
        self.assertRegex(result["sourceFingerprint"], r"^[0-9a-f]{64}$")

    def test_collect_source_fact_distinguishes_missing_readme_from_failure(self):
        repo = self.repo("empty")

        def no_readme(url, token):
            if url.endswith("/readme"):
                raise GitHubApiError("missing", status=404)
            return (
                {
                    "private": False,
                    "visibility": "public",
                    "archived": False,
                    "description": None,
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )

        absent = collect_source_fact(repo, request_fn=no_readme)
        self.assertEqual(absent["sources"][1]["status"], "absent")

        def failed_readme(url, token):
            if url.endswith("/readme"):
                raise GitHubApiError("rate limited", status=403)
            return (
                {
                    "private": False,
                    "visibility": "public",
                    "archived": False,
                    "description": None,
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )

        failed = collect_source_fact(repo, request_fn=failed_readme)
        self.assertEqual(failed["sources"][1]["status"], "error")
        self.assertNotEqual(absent["sourceFingerprint"], failed["sourceFingerprint"])

    def test_collect_source_fact_marks_boundary_change_as_error(self):
        repo = self.repo("public-before")

        def request_fn(url, token):
            if url.endswith("/readme"):
                raise GitHubApiError("missing", status=404)
            return (
                {
                    "private": True,
                    "visibility": "private",
                    "archived": False,
                    "description": "must not be trusted",
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )

        result = collect_source_fact(repo, request_fn=request_fn)
        self.assertEqual(result["sources"][0]["status"], "error")

    def test_merge_index_creates_unreviewed_entry_for_new_repository(self):
        repo = self.repo("new-repo")
        document = merge_index(
            [repo],
            {"new-repo": self.facts("new-repo")},
            existing={"repositories": []},
            now="2026-08-18T01:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertEqual(entry["purpose"], UNKNOWN_PURPOSE)
        self.assertEqual(entry["matches"], [UNKNOWN_MATCH])
        self.assertTrue(entry["needsReview"])
        self.assertIsNone(entry["checkedAt"])

    def test_merge_index_preserves_semantics_when_sources_are_unchanged(self):
        repo = self.repo("stable")
        old = self.entry("stable", purpose="keep me")
        document = merge_index(
            [repo],
            {"stable": self.facts("stable", "a" * 64)},
            existing={"repositories": [old]},
            now="2026-08-18T02:00:00Z",
        )
        self.assertEqual(document["repositories"][0]["purpose"], "keep me")
        self.assertFalse(document["repositories"][0]["needsReview"])
        self.assertEqual(document["repositories"][0]["checkedAt"], "2026-08-18T00:00:00Z")

    def test_merge_index_marks_changed_source_stale_without_rewriting_semantics(self):
        repo = self.repo("changed")
        old = self.entry("changed", purpose="known purpose", fingerprint="a" * 64)
        document = merge_index(
            [repo],
            {"changed": self.facts("changed", "b" * 64)},
            existing={"repositories": [old]},
            now="2026-08-18T02:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertEqual(entry["purpose"], "known purpose")
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["checkedAt"], "2026-08-18T00:00:00Z")

    def test_merge_index_applies_verified_override_and_drops_removed_inventory(self):
        repository = self.repo("unity-agent")
        existing = {
            "repositories": [
                self.entry("old-archived"),
                self.entry("unity-agent", purpose="old", fingerprint="a" * 64),
            ]
        }
        overrides = {
            "unity-agent": {
                "purpose": "VRChat avatar editor",
                "matches": ["Expression Menu / PhysBone"],
                "notFor": ["UdonSharp world"],
            }
        }
        document = merge_index(
            [repository],
            {"unity-agent": self.facts("unity-agent", "b" * 64)},
            existing=existing,
            overrides=overrides,
            now="2026-08-18T03:00:00Z",
        )
        self.assertEqual([entry["name"] for entry in document["repositories"]], ["unity-agent"])
        entry = document["repositories"][0]
        self.assertFalse(entry["needsReview"])
        self.assertEqual(entry["checkedAt"], "2026-08-18T03:00:00Z")
        self.assertEqual(entry["purpose"], "VRChat avatar editor")

    def test_validate_index_rejects_duplicates_and_invalid_entries(self):
        valid = self.entry("valid")
        self.assertEqual(validate_index({"repositories": [valid]})["repositories"][0]["name"], "valid")
        with self.assertRaisesRegex(ValueError, "duplicate repository names"):
            validate_index({"repositories": [valid, dict(valid)]})

        empty_purpose = dict(valid)
        empty_purpose["purpose"] = ""
        with self.assertRaisesRegex(ValueError, "purpose must be non-empty"):
            validate_index({"repositories": [empty_purpose]})

        no_sources = dict(valid)
        no_sources["sources"] = []
        with self.assertRaisesRegex(ValueError, "sources must be non-empty"):
            validate_index({"repositories": [no_sources]})

    def test_validate_coverage_reports_missing_and_extra_names(self):
        repositories = [self.repo("one"), self.repo("two")]
        valid_document = {"repositories": [self.entry("one"), self.entry("two")]}
        self.assertTrue(validate_coverage(repositories, valid_document))

        with self.assertRaisesRegex(ValueError, "missing=\['two'\]"):
            validate_coverage(repositories, {"repositories": [self.entry("one")]})

        with self.assertRaisesRegex(ValueError, "extra=\['three'\]"):
            validate_coverage(
                repositories,
                {"repositories": [self.entry("one"), self.entry("two"), self.entry("three")]},
            )

    def test_search_distinguishes_public_unity_repositories(self):
        document = {
            "repositories": [
                self.entry(
                    "unity-mcp",
                    purpose="LLMからUnity Editorのscene GameObject asset script test buildをMCPで操作する",
                    matches=["Unity scene/assetsをLLMから操作", "Unity EditorをMCPで操作"],
                    not_for=["Expression Menu PhysBone", "UdonSharp world"],
                ),
                self.entry(
                    "unity-agent",
                    purpose="VRChatアバター制作でExpression Menu PhysBone Contact Constraintを編集する",
                    matches=["Expression Menu / PhysBone", "VRChatアバターをAIで編集"],
                    not_for=["UdonSharp world", "汎用Unity EditorのMCPだけが必要"],
                ),
                self.entry(
                    "UnityMCP-VRC",
                    purpose="VRChatワールド制作でUdonSharpコード生成とUnity連携を支援する",
                    matches=["UdonSharp world", "VRChatワールドでUdonSharp生成を支援"],
                    not_for=["Expression Menu PhysBone", "アバター編集"],
                ),
            ]
        }
        self.assertEqual(search_index("Expression Menu / PhysBone", document)["selected"], "unity-agent")
        self.assertEqual(search_index("UdonSharp world", document)["selected"], "UnityMCP-VRC")
        self.assertEqual(search_index("Unity scene/assetsをLLMから操作", document)["selected"], "unity-mcp")
        self.assertIsNone(search_index("Unityのあの機能", document)["selected"])
        penetration = search_index("衣装が体を貫通する", document)
        self.assertIsNone(penetration["selected"])
        self.assertNotIn("unitymcppro", json.dumps(penetration, ensure_ascii=False))

    def test_unreviewed_entry_is_never_selected(self):
        document = {
            "repositories": [
                self.entry(
                    "stale",
                    purpose="Unity EditorをMCPで操作",
                    matches=["Unity EditorをMCPで操作"],
                    needs_review=True,
                )
            ]
        }
        result = search_index("Unity EditorをMCPで操作", document)
        self.assertIsNone(result["selected"])
        self.assertTrue(result["ambiguous"])

    def test_schema_declares_strict_repository_shape(self):
        schema_path = Path(__file__).resolve().parents[1] / "schema" / "repository-recall.schema.json"
        with schema_path.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        repository_schema = schema["$defs"]["repository"]
        self.assertFalse(repository_schema["additionalProperties"])
        self.assertEqual(
            set(repository_schema["required"]),
            {
                "name",
                "purpose",
                "matches",
                "notFor",
                "url",
                "sources",
                "sourceFingerprint",
                "checkedAt",
                "needsReview",
            },
        )

    def test_canonical_hash_is_order_independent_for_objects(self):
        self.assertEqual(canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
