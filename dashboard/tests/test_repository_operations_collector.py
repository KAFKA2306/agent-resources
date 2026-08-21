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
        assert token == "token"
        if url == "https://api.github.com/repos/KAFKA2306/alpha":
            return (
                {
                    "html_url": "https://github.com/KAFKA2306/alpha",
                    "topics": ["python", "agent-zone-research"],
                    "default_branch": "main",
                },
                {},
            )
        if url == "https://api.github.com/repos/KAFKA2306/alpha/compare/merged...main":
            return ({"behind_by": 0}, {})
        if url == "https://api.github.com/repos/KAFKA2306/alpha/compare/unmerged...main":
            return ({"behind_by": 2}, {})
        raise AssertionError(f"unexpected request: {url}")

    def pagination_fetcher(url, token=None):
        assert url.endswith("/branches?per_page=100")
        assert token == "token"
        return [
            {
                "name": "merged",
                "commit": {"sha": "2" * 40},
                "protected": False,
            },
            {
                "name": "protected-feature",
                "commit": {"sha": "3" * 40},
                "protected": True,
            },
            {
                "name": "unmerged",
                "commit": {"sha": "4" * 40},
                "protected": False,
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
    branches = {branch["name"]: branch for branch in repository["branches"]}
    assert branches["merged"] == {
        "name": "merged",
        "commitSha": "2" * 40,
        "isDefault": False,
        "protected": False,
        "deletionCandidate": True,
        "deletionConfirmed": False,
        "deleted": False,
        "blockedReason": None,
    }
    assert branches["unmerged"]["deletionCandidate"] is False
    assert branches["protected-feature"]["deletionCandidate"] is False
    assert branches["main"]["isDefault"] is True
    assert branches["main"]["deletionCandidate"] is False


def test_branch_names_are_url_encoded_for_compare():
    config = {"owner": "KAFKA2306"}
    requested_urls = []

    def repository_collector(_config, token=None):
        return [
            {
                "owner": "KAFKA2306",
                "name": "alpha",
                "url": "https://github.com/KAFKA2306/alpha",
            }
        ]

    def request_fn(url, token=None):
        requested_urls.append(url)
        if url.endswith("/alpha"):
            return (
                {
                    "html_url": "https://github.com/KAFKA2306/alpha",
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )
        return ({"behind_by": 0}, {})

    def pagination_fetcher(_url, token=None):
        return [
            {
                "name": "feature/cleanup",
                "commit": {"sha": "2" * 40},
                "protected": False,
            },
            {
                "name": "main",
                "commit": {"sha": "1" * 40},
                "protected": False,
            },
        ]

    snapshot = collect_repository_operations(
        config,
        run_id="run-encoded",
        generated_at="2026-08-21T00:00:00Z",
        repository_collector=repository_collector,
        request_fn=request_fn,
        pagination_fetcher=pagination_fetcher,
    )

    assert requested_urls[-1] == (
        "https://api.github.com/repos/KAFKA2306/alpha/compare/feature%2Fcleanup...main"
    )
    assert snapshot["repositories"][0]["branches"][0]["deletionCandidate"] is True


def test_invalid_compare_payload_fails_closed():
    config = {"owner": "KAFKA2306"}

    def repository_collector(_config, token=None):
        return [
            {
                "owner": "KAFKA2306",
                "name": "alpha",
                "url": "https://github.com/KAFKA2306/alpha",
            }
        ]

    def request_fn(url, token=None):
        if url.endswith("/alpha"):
            return (
                {
                    "html_url": "https://github.com/KAFKA2306/alpha",
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )
        return ({"behind_by": None}, {})

    def pagination_fetcher(_url, token=None):
        return [
            {
                "name": "feature",
                "commit": {"sha": "2" * 40},
                "protected": False,
            },
            {
                "name": "main",
                "commit": {"sha": "1" * 40},
                "protected": False,
            },
        ]

    try:
        collect_repository_operations(
            config,
            run_id="run-invalid",
            generated_at="2026-08-21T00:00:00Z",
            repository_collector=repository_collector,
            request_fn=request_fn,
            pagination_fetcher=pagination_fetcher,
        )
    except ValueError as exc:
        assert "compare payload is missing valid behind_by" in str(exc)
    else:
        raise AssertionError("invalid compare payload must fail closed")


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
