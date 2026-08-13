import argparse
import calendar
import os
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, request_json

API_ROOT = "https://api.github.com/search"
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_START_MONTH = "2026-01"
DEFAULT_TIMEZONE = "Asia/Tokyo"


def _search_total(endpoint, query, token=None, request_fn=request_json):
    if "is:public" not in query.split():
        raise GitHubApiError("public dashboard search must include is:public")

    url = f"{API_ROOT}/{endpoint}?{urlencode({'q': query, 'per_page': 1})}"
    payload, _ = request_fn(url, token)
    if not isinstance(payload, dict):
        raise GitHubApiError("unexpected GitHub Search API response shape")
    if payload.get("incomplete_results") is not False:
        raise GitHubApiError("GitHub Search API returned incomplete results")
    total = payload.get("total_count")
    if not isinstance(total, int) or total < 0:
        raise GitHubApiError("GitHub Search API returned invalid total_count")
    return total


def _parse_start_month(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("start_month must use YYYY-MM") from exc
    return parsed.year, parsed.month


def _month_range(start_month, now):
    year, month = _parse_start_month(start_month)
    if (year, month) > (now.year, now.month):
        raise ValueError("start_month cannot be in the future")

    while (year, month) <= (now.year, now.month):
        yield year, month
        month += 1
        if month == 13:
            year += 1
            month = 1


def _date_window(year, month, now):
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    is_current = (year, month) == (now.year, now.month)
    end_day = now.day if is_current else last_day
    end = f"{year:04d}-{month:02d}-{end_day:02d}"
    partial = is_current and now.day < last_day
    return start, end, partial


def collect_github_stats(
    owner=DEFAULT_OWNER,
    start_month=DEFAULT_START_MONTH,
    now=None,
    token=None,
    request_fn=request_json,
):
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = now.astimezone(tz) if now is not None else datetime.now(tz)

    public_repositories = _search_total(
        "repositories", f"user:{owner} is:public", token=token, request_fn=request_fn
    )
    archived_public_repositories = _search_total(
        "repositories",
        f"user:{owner} is:public archived:true",
        token=token,
        request_fn=request_fn,
    )

    monthly = []
    for year, month in _month_range(start_month, now):
        start, end, partial = _date_window(year, month, now)
        public = "is:public"
        monthly.append(
            {
                "month": f"{year:04d}-{month:02d}",
                "commits": _search_total(
                    "commits",
                    f"author:{owner} committer-date:{start}..{end} {public}",
                    token=token,
                    request_fn=request_fn,
                ),
                "prsCreated": _search_total(
                    "issues",
                    f"author:{owner} is:pr created:{start}..{end} {public}",
                    token=token,
                    request_fn=request_fn,
                ),
                "prsMerged": _search_total(
                    "issues",
                    f"author:{owner} is:pr merged:{start}..{end} {public}",
                    token=token,
                    request_fn=request_fn,
                ),
                "issuesCreated": _search_total(
                    "issues",
                    f"author:{owner} is:issue created:{start}..{end} {public}",
                    token=token,
                    request_fn=request_fn,
                ),
                "issuesClosed": _search_total(
                    "issues",
                    f"author:{owner} is:issue closed:{start}..{end} {public}",
                    token=token,
                    request_fn=request_fn,
                ),
                "partial": partial,
            }
        )

    return {
        "generatedAt": now.isoformat(),
        "owner": owner,
        "scope": "public",
        "timezone": DEFAULT_TIMEZONE,
        "publicRepositories": public_repositories,
        "archivedPublicRepositories": archived_public_repositories,
        "monthly": monthly,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect public GitHub activity statistics")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--start-month", default=DEFAULT_START_MONTH)
    parser.add_argument("--output", default="dashboard/generated/github-stats.json")
    args = parser.parse_args()

    payload = collect_github_stats(
        owner=args.owner,
        start_month=args.start_month,
        token=os.environ.get("GITHUB_TOKEN"),
    )
    atomic_write_json(args.output, payload)


if __name__ == "__main__":
    main()
