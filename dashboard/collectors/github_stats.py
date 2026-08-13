import argparse
import calendar
import os
import time
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, request_json

API_ROOT = "https://api.github.com/search"
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_START_MONTH = "2026-01"
DEFAULT_TIMEZONE = "Asia/Tokyo"
DEFAULT_REQUEST_INTERVAL = 2.2
DEFAULT_RATE_RETRIES = 2


def _header(headers, name):
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _rate_limit_wait(error, now_fn=time.time):
    if error.status not in {403, 429}:
        return None
    body = error.response_body.lower()
    if "rate limit" not in body and "abuse" not in body:
        return None

    retry_after = _header(error.headers, "retry-after")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            pass

    remaining = _header(error.headers, "x-ratelimit-remaining")
    reset = _header(error.headers, "x-ratelimit-reset")
    if remaining == "0" and reset:
        try:
            return max(1.0, float(reset) - now_fn() + 1.0)
        except ValueError:
            pass
    return 60.0


def _search_total(
    endpoint,
    query,
    token=None,
    request_fn=request_json,
    sleep_fn=time.sleep,
    now_fn=time.time,
    max_rate_retries=DEFAULT_RATE_RETRIES,
):
    if "is:public" not in query.split():
        raise GitHubApiError("public dashboard search must include is:public")

    url = f"{API_ROOT}/{endpoint}?{urlencode({'q': query, 'per_page': 1})}"
    attempt = 0
    while True:
        try:
            payload, _ = request_fn(url, token)
            break
        except GitHubApiError as exc:
            wait_seconds = _rate_limit_wait(exc, now_fn=now_fn)
            if wait_seconds is None or attempt >= max_rate_retries:
                raise
            sleep_fn(wait_seconds * (2**attempt))
            attempt += 1

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
    request_interval=0.0,
    sleep_fn=time.sleep,
):
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = now.astimezone(tz) if now is not None else datetime.now(tz)

    def search(endpoint, query):
        total = _search_total(
            endpoint,
            query,
            token=token,
            request_fn=request_fn,
            sleep_fn=sleep_fn,
        )
        if request_interval > 0:
            sleep_fn(request_interval)
        return total

    public_repositories = search("repositories", f"user:{owner} is:public")
    archived_public_repositories = search(
        "repositories", f"user:{owner} is:public archived:true"
    )

    monthly = []
    for year, month in _month_range(start_month, now):
        start, end, partial = _date_window(year, month, now)
        public = "is:public"
        monthly.append(
            {
                "month": f"{year:04d}-{month:02d}",
                "commits": search(
                    "commits", f"author:{owner} committer-date:{start}..{end} {public}"
                ),
                "prsCreated": search(
                    "issues", f"author:{owner} is:pr created:{start}..{end} {public}"
                ),
                "prsMerged": search(
                    "issues", f"author:{owner} is:pr merged:{start}..{end} {public}"
                ),
                "issuesCreated": search(
                    "issues", f"author:{owner} is:issue created:{start}..{end} {public}"
                ),
                "issuesClosed": search(
                    "issues", f"author:{owner} is:issue closed:{start}..{end} {public}"
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
    parser.add_argument("--request-interval", type=float, default=DEFAULT_REQUEST_INTERVAL)
    parser.add_argument("--output", default="dashboard/generated/github-stats.json")
    args = parser.parse_args()
    if args.request_interval < 0:
        parser.error("--request-interval must be non-negative")

    payload = collect_github_stats(
        owner=args.owner,
        start_month=args.start_month,
        token=os.environ.get("GITHUB_TOKEN"),
        request_interval=args.request_interval,
    )
    atomic_write_json(args.output, payload)


if __name__ == "__main__":
    main()
