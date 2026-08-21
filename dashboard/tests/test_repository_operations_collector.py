from dashboard.collectors.repository_operations import collect_repository_operations


def test_collect_repository_operations_uses_topics_and_branch_facts():
    config = {"owner": "KAFKA2306"}

    def repository_collector(_config, token=None):
        assert token == "token"
        return [
            {
                "owner": "KAFKA2306",
                "name": "alpha",
                "url": "https://github.com/KAFKA2306/alpha",
            }
        ]

    def request_fn(url, token=None):
        assert url == "https://api.github.com/repos/KAFKA2306/alpha"
        assert token == "token"
        return (
            {
                "html_url": "https://github.com/KAFKA2306/alpha",
                "topics": ["python", "agent-zone-research"],
                "default_branch": "main",
            },
            {},
        )

    def pagination_fetcher(url, token=None):
        assert url.endswith("/branches?per_page=100")
        assert token == "token"
        return [
            {
                "name": "feature",
                "commit": {"sha": "2" * 40},
                "protected": True,
            },
            {
                "name": "main",
                "commit": {"sha": "1" * 40},
                "protected": False,
            },
        ]

    snapshot = collect_repository_operations(
        config,
        token="token",
        run_id="run-1",
        generated_at="2026-08-21T00:00:00Z",
        repository_collector=repository_collector,
        request_fn=request_fn,
        pagination_fetcher=pagination_fetcher,
    )

    assert snapshot["generatedAt"] == "2026-08-21T00:00:00Z"
    assert snapshot["sourceRevision"] == "github-rest-api-2026-03-10"
    assert snapshot["runId"] == "run-1"
    repository = snapshot["repositories"][0]
    assert repository["classification"] == {
        "domain": "research",
        "source": "github-topic",
        "evidence": ["https://github.com/KAFKA2306/alpha"],
    }
    assert repository["branches"][0] == {
        "name": "feature",
        "commitSha": "2" * 40,
        "isDefault": False,
        "protected": True,
        "deletionCandidate": False,
        "deletionConfirmed": False,
        "deleted": False,
        "blockedReason": None,
    }
    assert repository["branches"][1]["isDefault"] is True


def test_conflicting_agent_zone_topics_do_not_choose_a_domain():
    config = {"owner": "KAFKA2306"}

    def repository_collector(_config, token=None):
        return [
            {
                "owner": "KAFKA2306",
                "name": "alpha",
                "url": "https://github.com/KAFKA2306/alpha",
            }
        ]

    def request_fn(_url, token=None):
        return (
            {
                "html_url": "https://github.com/KAFKA2306/alpha",
                "topics": ["agent-zone-finance", "agent-zone-research"],
                "default_branch": "main",
            },
            {},
        )

    def pagination_fetcher(_url, token=None):
        return [
            {
                "name": "main",
                "commit": {"sha": "1" * 40},
                "protected": False,
            }
        ]

    snapshot = collect_repository_operations(
        config,
        run_id="run-2",
        generated_at="2026-08-21T00:00:00Z",
        repository_collector=repository_collector,
        request_fn=request_fn,
        pagination_fetcher=pagination_fetcher,
    )

    assert snapshot["repositories"][0]["classification"] == {
        "domain": None,
        "source": "conflicting-github-topics",
        "evidence": ["https://github.com/KAFKA2306/alpha"],
    }
