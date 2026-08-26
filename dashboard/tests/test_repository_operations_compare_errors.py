import pytest

from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.repository_operations import branch_is_fully_merged


def test_compare_404_is_not_a_deletion_candidate():
    def request_fn(_url, _token):
        raise GitHubApiError("compare not found", status=404)

    assert branch_is_fully_merged(
        "https://api.github.com/repos/KAFKA2306/anime",
        "gh-pages",
        "2" * 40,
        "main",
        token="token",
        request_fn=request_fn,
    ) is False


def test_compare_non_404_error_still_fails():
    def request_fn(_url, _token):
        raise GitHubApiError("server failure", status=500)

    with pytest.raises(GitHubApiError, match="server failure"):
        branch_is_fully_merged(
            "https://api.github.com/repos/KAFKA2306/anime",
            "gh-pages",
            "2" * 40,
            "main",
            token="token",
            request_fn=request_fn,
        )
