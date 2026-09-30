from dashboard.collectors.github_api import GitHubApiError
from dashboard.collectors.repository_operations import branch_is_fully_merged


def test_uncomparable_branch_is_not_a_deletion_candidate():
    def request_fn(url, token):
        raise GitHubApiError(422, url, "unprocessable comparison")

    assert branch_is_fully_merged(
        "https://api.github.com/repos/KAFKA2306/kafin3",
        "agent/issue-15-prepush-canonical-gate",
        "deadbeef",
        "main",
        token="token",
        request_fn=request_fn,
    ) is False
