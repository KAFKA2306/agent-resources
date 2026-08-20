import unittest

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.storage_budget import collect_owner_storage_budget, collect_storage_budget


class FakeApi:
    def paginate(self, url, token=None, request_fn=None, item_key=None):
        self._assert_token(token)
        if url.endswith("/repo-a/actions/artifacts?per_page=100"):
            return [
                {"size_in_bytes": 100, "expired": False},
                {"size_in_bytes": 200, "expired": False},
                {"size_in_bytes": 999, "expired": True},
            ]
        if url.endswith("/repo-b/actions/artifacts?per_page=100"):
            raise GitHubApiError("forbidden", status=403)
        if url.endswith("/repo-a/actions/caches?per_page=100"):
            return [
                {
                    "key": "uv-linux-abc",
                    "ref": "refs/heads/main",
                    "version": "v1",
                    "created_at": "2026-08-01T00:00:00Z",
                    "last_accessed_at": "2026-08-10T00:00:00Z",
                    "size_in_bytes": 1000,
                },
                {
                    "key": "uv-linux-abc",
                    "ref": "refs/heads/main",
                    "version": "v2",
                    "created_at": "2026-08-11T00:00:00Z",
                    "last_accessed_at": "2026-08-20T00:00:00Z",
                    "size_in_bytes": 1100,
                },
                {
                    "key": "node-linux-def",
                    "ref": "refs/heads/feature",
                    "version": "v1",
                    "created_at": "2026-08-12T00:00:00Z",
                    "last_accessed_at": "2026-08-15T00:00:00Z",
                    "size_in_bytes": 2000,
                },
            ]
        if url.endswith("/repo-b/actions/caches?per_page=100"):
            raise GitHubApiError("not found", status=404)
        raise AssertionError(f"unexpected paginated URL: {url}")

    def request(self, url, token=None):
        self._assert_token(token)
        if url.endswith("/repo-a/actions/permissions/artifact-and-log-retention"):
            return ({"days": 14, "maximum_allowed_days": 400}, {})
        if url.endswith("/repo-b/actions/permissions/artifact-and-log-retention"):
            raise GitHubApiError("forbidden", status=403)
        if url.endswith("/repo-a/actions/cache/usage"):
            return (
                {
                    "active_caches_count": 3,
                    "active_caches_size_in_bytes": 4096,
                },
                {},
            )
        if url.endswith("/repo-b/actions/cache/usage"):
            raise GitHubApiError("not found", status=404)
        raise AssertionError(f"unexpected URL: {url}")

    @staticmethod
    def _assert_token(token):
        if token != "secret":
            raise AssertionError("storage collector must use the supplied token")


class FakeOwnerApi:
    def paginate(self, url, token=None, request_fn=None, item_key=None):
        if token != "secret":
            raise AssertionError("storage collector must use the supplied token")
        if url.startswith("https://api.github.com/user/repos?"):
            return [
                {
                    "name": "public-repo",
                    "owner": {"login": "KAFKA2306"},
                    "private": False,
                    "archived": False,
                    "size": 10,
                    "has_pages": True,
                },
                {
                    "name": "private-repo",
                    "owner": {"login": "KAFKA2306"},
                    "private": True,
                    "archived": False,
                    "size": 20,
                    "has_pages": False,
                },
                {
                    "name": "archived-repo",
                    "owner": {"login": "KAFKA2306"},
                    "private": False,
                    "archived": True,
                    "size": 30,
                    "has_pages": False,
                },
                {
                    "name": "other-owner",
                    "owner": {"login": "someone-else"},
                    "private": False,
                    "archived": False,
                },
            ]
        if "/actions/artifacts?per_page=100" in url:
            return []
        if "/actions/caches?per_page=100" in url:
            return []
        raise AssertionError(f"unexpected paginated URL: {url}")

    def request(self, url, token=None):
        if token != "secret":
            raise AssertionError("storage collector must use the supplied token")
        if url.endswith("/actions/permissions/artifact-and-log-retention"):
            maximum = 400 if "/private-repo/" in url else 90
            return ({"days": 7, "maximum_allowed_days": maximum}, {})
        if url.endswith("/actions/cache/usage"):
            return ({"active_caches_count": 0, "active_caches_size_in_bytes": 0}, {})
        raise AssertionError(f"unexpected URL: {url}")


class StorageBudgetCollectorTests(unittest.TestCase):
    def test_collects_known_usage_without_turning_unknown_into_zero(self):
        repositories = [
            {
                "name": "repo-a",
                "owner": {"login": "KAFKA2306"},
                "private": True,
                "archived": False,
                "size": 123,
                "has_pages": True,
            },
            {
                "name": "repo-b",
                "owner": {"login": "KAFKA2306"},
                "private": False,
                "archived": False,
                "size": 456,
                "has_pages": False,
            },
            {
                "name": "archived",
                "owner": {"login": "KAFKA2306"},
                "private": False,
                "archived": True,
            },
        ]
        api = FakeApi()

        payload = collect_storage_budget(
            repositories,
            token="secret",
            request_fn=api.request,
            paginate_fn=api.paginate,
        )

        self.assertEqual(payload["schema_version"], "storage-budget.v1")
        self.assertEqual(payload["repository_count"], 2)
        self.assertEqual(payload["known_actions_artifact_bytes"], 300)
        self.assertEqual(payload["known_actions_cache_bytes"], 4096)
        self.assertEqual(
            payload["unavailable_actions_artifact_repositories"],
            ["KAFKA2306/repo-b"],
        )
        self.assertEqual(
            payload["unavailable_actions_artifact_log_retention_repositories"],
            ["KAFKA2306/repo-b"],
        )
        self.assertEqual(
            payload["unavailable_actions_cache_repositories"],
            ["KAFKA2306/repo-b"],
        )
        self.assertEqual(
            payload["unavailable_actions_cache_inventory_repositories"],
            ["KAFKA2306/repo-b"],
        )
        self.assertFalse(payload["notes"]["unknown_is_zero"])
        self.assertEqual(payload["notes"]["pages_bandwidth"], "unavailable")
        self.assertEqual(payload["notes"]["git_lfs_usage"], "unavailable")

        repo_a = payload["repositories"][0]
        self.assertEqual(
            repo_a["actions_artifacts"],
            {
                "status": "available",
                "usage": {"count": 2, "size_in_bytes": 300, "expired_count": 1},
                "reason": None,
            },
        )
        self.assertEqual(
            repo_a["actions_artifact_log_retention"],
            {
                "status": "available",
                "setting": {"days": 14, "maximum_allowed_days": 400},
                "reason": None,
            },
        )
        self.assertEqual(repo_a["actions_cache"]["status"], "available")
        self.assertEqual(repo_a["actions_cache"]["usage"], {"count": 3, "size_in_bytes": 4096})
        self.assertEqual(repo_a["actions_cache"]["inventory_status"], "available")
        inventory = repo_a["actions_cache"]["inventory"]
        self.assertEqual(inventory["entry_count"], 3)
        self.assertEqual(inventory["unique_key_count"], 2)
        self.assertEqual(inventory["unique_ref_count"], 2)
        self.assertEqual(inventory["key_ref_pairs_with_multiple_entries"], 1)
        self.assertEqual(inventory["max_entries_per_key_ref"], 2)
        self.assertEqual(inventory["oldest_last_accessed_at"], "2026-08-10T00:00:00Z")
        self.assertEqual(inventory["newest_last_accessed_at"], "2026-08-20T00:00:00Z")
        self.assertEqual(len(inventory["entries"]), 3)
        self.assertEqual(repo_a["repository_size_kb"], 123)
        self.assertTrue(repo_a["pages_enabled"])

        repo_b = payload["repositories"][1]
        self.assertEqual(repo_b["actions_artifacts"]["status"], "unavailable")
        self.assertEqual(repo_b["actions_artifacts"]["reason"], "github_api_http_403")
        self.assertIsNone(repo_b["actions_artifacts"]["usage"])
        self.assertEqual(repo_b["actions_artifact_log_retention"]["status"], "unavailable")
        self.assertEqual(
            repo_b["actions_artifact_log_retention"]["reason"],
            "github_api_http_403",
        )
        self.assertIsNone(repo_b["actions_artifact_log_retention"]["setting"])
        self.assertEqual(repo_b["actions_cache"]["status"], "unavailable")
        self.assertEqual(repo_b["actions_cache"]["reason"], "github_api_http_404")
        self.assertIsNone(repo_b["actions_cache"]["usage"])
        self.assertEqual(repo_b["actions_cache"]["inventory_status"], "unavailable")
        self.assertEqual(repo_b["actions_cache"]["inventory_reason"], "github_api_http_404")
        self.assertIsNone(repo_b["actions_cache"]["inventory"])

    def test_owner_inventory_includes_public_and_private_active_repositories(self):
        api = FakeOwnerApi()

        payload = collect_owner_storage_budget(
            "KAFKA2306",
            token="secret",
            request_fn=api.request,
            paginate_fn=api.paginate,
        )

        self.assertEqual(payload["owner"], "KAFKA2306")
        self.assertEqual(payload["scope"], "owned_active_repositories")
        self.assertEqual(payload["repository_count"], 2)
        self.assertEqual(
            [row["name"] for row in payload["repositories"]],
            ["KAFKA2306/private-repo", "KAFKA2306/public-repo"],
        )
        self.assertTrue(payload["repositories"][0]["private"])
        self.assertFalse(payload["repositories"][1]["private"])
        self.assertEqual(
            payload["repositories"][0]["actions_artifact_log_retention"]["setting"],
            {"days": 7, "maximum_allowed_days": 400},
        )
        self.assertEqual(
            payload["repositories"][1]["actions_artifact_log_retention"]["setting"],
            {"days": 7, "maximum_allowed_days": 90},
        )
        for row in payload["repositories"]:
            self.assertEqual(row["actions_cache"]["inventory_status"], "available")
            self.assertEqual(row["actions_cache"]["inventory"]["entry_count"], 0)


if __name__ == "__main__":
    unittest.main()
