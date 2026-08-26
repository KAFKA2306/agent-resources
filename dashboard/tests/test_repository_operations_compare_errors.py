import unittest

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.repository_operations import branch_is_fully_merged


class RepositoryOperationsCompareErrorTest(unittest.TestCase):
    def test_compare_404_is_not_a_deletion_candidate(self):
        def request_fn(_url, _token):
            raise GitHubApiError("compare not found", status=404)

        self.assertFalse(
            branch_is_fully_merged(
                "https://api.github.com/repos/KAFKA2306/anime",
                "gh-pages",
                "2" * 40,
                "main",
                token="token",
                request_fn=request_fn,
            )
        )

    def test_compare_non_404_error_still_fails(self):
        def request_fn(_url, _token):
            raise GitHubApiError("server failure", status=500)

        with self.assertRaisesRegex(GitHubApiError, "server failure"):
            branch_is_fully_merged(
                "https://api.github.com/repos/KAFKA2306/anime",
                "gh-pages",
                "2" * 40,
                "main",
                token="token",
                request_fn=request_fn,
            )


if __name__ == "__main__":
    unittest.main()
