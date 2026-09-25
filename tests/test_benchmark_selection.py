from dashboard.benchmark_selection import select_benchmark_candidates


def test_selects_only_new_relevant_exact_revisions_deterministically():
    rows = [
        {"repository": "z/new", "benchmark_revision": "bbb", "capability": "repair", "local_status": "MISSING", "last_evaluated_revision": None},
        {"repository": "a/old", "benchmark_revision": "aaa", "capability": "repair", "local_status": "MISSING", "last_evaluated_revision": "aaa"},
        {"repository": "x/unpinned", "benchmark_revision": None, "capability": "repair", "local_status": "MISSING"},
        {"repository": "b/other", "benchmark_revision": "ccc", "capability": "docs", "local_status": "MISSING"},
        {"repository": "z/new", "benchmark_revision": "bbb", "capability": "repair", "local_status": "MISSING", "last_evaluated_revision": None},
    ]

    decisions = select_benchmark_candidates(reversed(rows), relevant_capabilities=["repair"])

    assert [(item.repository, item.benchmark_revision, item.capability) for item in decisions] == [
        ("z/new", "bbb", "repair")
    ]
    assert decisions[0].decision == "EVALUATE"
    assert decisions[0].reason == "new_relevant_benchmark_revision"
