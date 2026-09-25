import json
from dashboard.oss_benchmark import merge_ledger, parse_trending


def test_parse_trending_extracts_ranked_unique_repositories():
    html = '''
    <h2 class="h3 lh-condensed"><a href="/alpha/one">alpha / one</a></h2>
    <h2 class="h3 lh-condensed"><a href="/beta/two">beta / two</a></h2>
    <h2 class="h3 lh-condensed"><a href="/alpha/one">alpha / one</a></h2>
    '''
    rows = parse_trending(html, window="daily", observed_at="2026-09-25T00:00:00+00:00")
    assert [(r.rank, r.repository) for r in rows] == [(1, "alpha/one"), (2, "beta/two")]
    assert all(r.local_status == "UNVERIFIED" for r in rows)


def test_merge_ledger_deduplicates_same_repo_window_revision_and_day(tmp_path):
    path = tmp_path / "ledger.json"
    html = '<h2 class="h3 lh-condensed"><a href="/alpha/one">alpha / one</a></h2>'
    rows = parse_trending(html, window="monthly", observed_at="2026-09-25T01:00:00+00:00")
    first = merge_ledger(path, rows)
    path.write_text(json.dumps(first), encoding="utf-8")
    second = merge_ledger(path, rows)
    assert len(second["entries"]) == 1
