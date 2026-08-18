import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.collectors.github_api import GitHubApiError
from dashboard.repository_recall import (
    UNKNOWN_MATCH,
    UNKNOWN_PURPOSE,
    canonical_hash,
    collect_source_fact,
    inventory_names,
    merge_index,
    refresh_index,
    search_index,
    semantic_coverage,
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

    def facts(
        self,
        name,
        fingerprint="a" * 64,
        *,
        description=None,
        topics=None,
    ):
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
            "description": description,
            "topics": topics or [],
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
        self.assertEqual(result["description"], "Unity MCP")
        self.assertEqual(result["topics"], ["mcp", "unity"])
        self.assertRegex(result["sourceFingerprint"], r"^[0-9a-f]{64}$")

    def test_collect_source_fact_treats_missing_readme_as_absent(self):
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

        result = collect_source_fact(repo, request_fn=no_readme)
        self.assertEqual(result["sources"][1]["status"], "absent")

    def test_collect_source_fact_propagates_transient_failure(self):
        repo = self.repo("empty")

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

        with self.assertRaises(GitHubApiError):
            collect_source_fact(repo, request_fn=failed_readme)

    def test_collect_source_fact_rejects_boundary_change(self):
        repo = self.repo("public-before")

        def request_fn(url, token):
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

        with self.assertRaisesRegex(ValueError, "source boundary changed"):
            collect_source_fact(repo, request_fn=request_fn)

    def test_merge_index_creates_unreviewed_entry_without_semantic_evidence(self):
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

    def test_merge_index_uses_public_description_as_verified_semantic_evidence(self):
        repo = self.repo("described")
        document = merge_index(
            [repo],
            {
                "described": self.facts(
                    "described",
                    description="Collect semiconductor earnings evidence",
                    topics=["finance", "semiconductor"],
                )
            },
            existing={"repositories": []},
            now="2026-08-18T01:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertEqual(entry["purpose"], "Collect semiconductor earnings evidence")
        self.assertEqual(
            entry["matches"],
            ["Collect semiconductor earnings evidence", "finance", "semiconductor"],
        )
        self.assertFalse(entry["needsReview"])
        self.assertEqual(entry["checkedAt"], "2026-08-18T01:00:00Z")

    def test_merge_index_backfills_existing_placeholder_when_description_exists(self):
        repo = self.repo("described")
        old = self.entry(
            "described",
            purpose=UNKNOWN_PURPOSE,
            matches=[UNKNOWN_MATCH],
            checked_at=None,
            needs_review=True,
        )
        document = merge_index(
            [repo],
            {
                "described": self.facts(
                    "described",
                    description="Public evidence index",
                    topics=["evidence"],
                )
            },
            existing={"repositories": [old]},
            now="2026-08-18T01:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertEqual(entry["purpose"], "Public evidence index")
        self.assertFalse(entry["needsReview"])

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

    def test_merge_index_preserves_checked_at_for_unchanged_override(self):
        repository = self.repo("unity-agent")
        override = {
            "purpose": "VRChat avatar editor",
            "matches": ["Expression Menu / PhysBone"],
            "notFor": ["UdonSharp world"],
        }
        old = self.entry(
            "unity-agent",
            purpose=override["purpose"],
            matches=override["matches"],
            not_for=override["notFor"],
            checked_at="2026-08-18T00:00:00Z",
        )
        document = merge_index(
            [repository],
            {"unity-agent": self.facts("unity-agent", "a" * 64)},
            existing={"repositories": [old]},
            overrides={"unity-agent": override},
            now="2026-08-19T00:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertEqual(entry["checkedAt"], "2026-08-18T00:00:00Z")
        self.assertFalse(entry["needsReview"])

    def test_merge_index_marks_unchanged_override_stale_when_source_changes(self):
        repository = self.repo("unity-agent")
        override = {
            "purpose": "VRChat avatar editor",
            "matches": ["Expression Menu / PhysBone"],
            "notFor": ["UdonSharp world"],
        }
        old = self.entry(
            "unity-agent",
            purpose=override["purpose"],
            matches=override["matches"],
            not_for=override["notFor"],
            fingerprint="a" * 64,
            checked_at="2026-08-18T00:00:00Z",
        )
        document = merge_index(
            [repository],
            {"unity-agent": self.facts("unity-agent", "b" * 64)},
            existing={"repositories": [old]},
            overrides={"unity-agent": override},
            now="2026-08-19T00:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["checkedAt"], "2026-08-18T00:00:00Z")

    def test_stale_override_remains_stale_until_override_changes(self):
        repository = self.repo("unity-agent")
        override = {
            "purpose": "VRChat avatar editor",
            "matches": ["Expression Menu / PhysBone"],
            "notFor": ["UdonSharp world"],
        }
        stale = self.entry(
            "unity-agent",
            purpose=override["purpose"],
            matches=override["matches"],
            not_for=override["notFor"],
            fingerprint="b" * 64,
            checked_at="2026-08-18T00:00:00Z",
            needs_review=True,
        )
        document = merge_index(
            [repository],
            {"unity-agent": self.facts("unity-agent", "b" * 64)},
            existing={"repositories": [stale]},
            overrides={"unity-agent": override},
            now="2026-08-20T00:00:00Z",
        )
        entry = document["repositories"][0]
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["checkedAt"], "2026-08-18T00:00:00Z")

    def test_validate_index_rejects_duplicates_invalid_entries_and_verified_placeholder(self):
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

        placeholder = self.entry(
            "placeholder",
            purpose=UNKNOWN_PURPOSE,
            matches=[UNKNOWN_MATCH],
            needs_review=False,
        )
        with self.assertRaisesRegex(ValueError, "placeholder semantics"):
            validate_index({"repositories": [placeholder]})

    def test_validate_coverage_reports_missing_and_extra_names(self):
        repositories = [self.repo("one"), self.repo("two")]
        valid_document = {"repositories": [self.entry("one"), self.entry("two")]}
        self.assertTrue(validate_coverage(repositories, valid_document))

        with self.assertRaisesRegex(ValueError, "missing=\\['two'\\]"):
            validate_coverage(repositories, {"repositories": [self.entry("one")]})

        with self.assertRaisesRegex(ValueError, "extra=\\['three'\\]"):
            validate_coverage(
                repositories,
                {"repositories": [self.entry("one"), self.entry("two"), self.entry("three")]},
            )

    def unity_document(self):
        return {
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

    def test_search_distinguishes_public_unity_repositories(self):
        document = self.unity_document()
        self.assertEqual(search_index("Expression Menu / PhysBone", document)["selected"], "unity-agent")
        self.assertEqual(search_index("UdonSharp world", document)["selected"], "UnityMCP-VRC")
        self.assertEqual(search_index("Unity scene/assetsをLLMから操作", document)["selected"], "unity-mcp")
        self.assertIsNone(search_index("Unityのあの機能", document)["selected"])
        penetration = search_index("衣装が体を貫通する", document)
        self.assertIsNone(penetration["selected"])
        self.assertNotIn("unitymcppro", json.dumps(penetration, ensure_ascii=False))

    def test_parent_issue_natural_language_regressions(self):
        document = self.unity_document()
        cases = {
            "LLMからUnity Editorのscene/assetsを操作する": "unity-mcp",
            "VRChatアバターのExpression MenuやPhysBoneをAIで編集する": "unity-agent",
            "VRChatワールドでUdonSharp生成を支援する": "UnityMCP-VRC",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(search_index(query, document)["selected"], expected)

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

    def test_semantic_coverage_reports_verified_and_review_counts(self):
        document = {
            "repositories": [
                self.entry("verified"),
                self.entry(
                    "pending",
                    purpose=UNKNOWN_PURPOSE,
                    matches=[UNKNOWN_MATCH],
                    checked_at=None,
                    needs_review=True,
                ),
            ]
        }
        self.assertEqual(
            semantic_coverage(document),
            {"repositories": 2, "verified": 1, "needsReview": 1, "placeholders": 1},
        )

    def test_refresh_index_is_idempotent_for_stable_override(self):
        repository = self.repo("unity-agent")
        override = {
            "unity-agent": {
                "purpose": "VRChat avatar editor",
                "matches": ["Expression Menu / PhysBone"],
                "notFor": ["UdonSharp world"],
            }
        }
        facts = {"unity-agent": self.facts("unity-agent", "a" * 64)}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "repositories.json"
            index_path = root / "repository-index.json"
            overrides_path = root / "overrides.json"
            config_path.write_text('{"owner":"KAFKA2306"}', encoding="utf-8")
            index_path.write_text('{"repositories":[]}', encoding="utf-8")
            overrides_path.write_text(json.dumps(override, ensure_ascii=False), encoding="utf-8")

            with (
                patch("dashboard.repository_recall.collect_repositories", return_value=[repository]),
                patch("dashboard.repository_recall.collect_source_facts", return_value=facts),
            ):
                first_changed, first = refresh_index(config_path, index_path, overrides_path)
                second_changed, second = refresh_index(config_path, index_path, overrides_path)

        self.assertTrue(first_changed)
        self.assertFalse(second_changed)
        self.assertEqual(first, second)

    def test_refresh_failure_does_not_mutate_existing_index(self):
        repository = self.repo("stable")
        existing = {"repositories": [self.entry("stable")]}
        before = json.dumps(existing, ensure_ascii=False, sort_keys=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "repositories.json"
            index_path = root / "repository-index.json"
            overrides_path = root / "overrides.json"
            config_path.write_text('{"owner":"KAFKA2306"}', encoding="utf-8")
            index_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
            overrides_path.write_text("{}", encoding="utf-8")

            with (
                patch("dashboard.repository_recall.collect_repositories", return_value=[repository]),
                patch(
                    "dashboard.repository_recall.collect_source_facts",
                    side_effect=GitHubApiError("rate limited", status=403),
                ),
            ):
                with self.assertRaises(GitHubApiError):
                    refresh_index(config_path, index_path, overrides_path)

            after = json.dumps(
                json.loads(index_path.read_text(encoding="utf-8")),
                ensure_ascii=False,
                sort_keys=True,
            )

        self.assertEqual(before, after)

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
