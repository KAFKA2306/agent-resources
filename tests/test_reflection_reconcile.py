from dashboard.reflection_reconcile import reconcile_stale_reflection_issues


def test_reconcile_closes_only_inactive_reflection_issues():
    issues = [
        {"number": 10, "body": "<!-- factory-reflection:reflection:aaaaaaaaaaaaaaaaaaaaaaaa -->"},
        {"number": 11, "body": "<!-- factory-reflection:reflection:bbbbbbbbbbbbbbbbbbbbbbbb -->"},
        {"number": 12, "body": "ordinary issue"},
    ]
    mutations = []

    def request_fn(url, token):
        assert "state=open" in url
        return issues, {}

    def mutation_fn(url, token, *, method, payload):
        mutations.append((url, method, payload))
        return {"number": 11, "state": "closed"}, {}

    stale = reconcile_stale_reflection_issues(
        owner="KAFKA2306",
        repository="agent-resources",
        active_candidate_ids={"reflection:aaaaaaaaaaaaaaaaaaaaaaaa"},
        request_fn=request_fn,
        mutation_fn=mutation_fn,
    )

    assert stale == [11]
    assert mutations == [
        (
            "https://api.github.com/repos/KAFKA2306/agent-resources/issues/11",
            "PATCH",
            {"state": "closed", "state_reason": "not_planned"},
        )
    ]


def test_reconcile_observe_only_does_not_mutate():
    issues = [
        {"number": 11, "body": "<!-- factory-reflection:reflection:bbbbbbbbbbbbbbbbbbbbbbbb -->"}
    ]

    def request_fn(url, token):
        return issues, {}

    def mutation_fn(*args, **kwargs):
        raise AssertionError("observe-only must not mutate")

    stale = reconcile_stale_reflection_issues(
        owner="KAFKA2306",
        repository="agent-resources",
        active_candidate_ids=set(),
        request_fn=request_fn,
        mutation_fn=mutation_fn,
        execute=False,
    )

    assert stale == [11]
