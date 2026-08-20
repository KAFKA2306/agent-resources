import unittest

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.storage_budget import collect_storage_budget


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
        raise AssertionError(f"unexpected paginated URL: {url}")

    def request(self, url, token=None):
        self._assert_token(token)
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
            payload["unavailable_actions_cache_repositories"],
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
            repo_a["actions_cache"],
            {
                "status": "available",
                "usage": {"count": 3, "size_in_bytes": 4096},
                "reason": None,
            },
        )
        self.assertEqual(repo_a["repository_size_kb"], 123)
        self.assertTrue(repo_a["pages_enabled"])

        repo_b = payload["repositories"][1]
        self.assertEqual(repo_b["actions_artifacts"]["status"], "unavailable")
        self.assertEqual(repo_b["actions_artifacts"]["reason"], "github_api_http_403")
        self.assertIsNone(repo_b["actions_artifacts"]["usage"])
        self.assertEqual(repo_b["actions_cache"]["status"], "unavailable")
        self.assertEqual(repo_b["actions_cache"]["reason"], "github_api_http_404")
        self.assertIsNone(repo_b["actions_cache"]["usage"])


if __name__ == "__main__":
    unittest.main()
