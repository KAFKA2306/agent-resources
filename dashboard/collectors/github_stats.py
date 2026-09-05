import argparse
import calendar
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, request_json

API_ROOT = "https://api.github.com/search"
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_START_MONTH = "2026-01"
DEFAULT_TIMEZONE = "Asia/Tokyo"
DEFAULT_REQUEST_INTERVAL = 2.2
DEFAULT_RATE_RETRIES = 2
DEFAULT_ISSUE_BACKLOG_OUTPUT = "dashboard/issue-backlog-history.json"
MONTHLY_METRIC_KEYS = (
    "commits",
    "prsCreated",
    "prsMerged",
    "issuesCreated",
    "issuesClosed",
)
DEFAULT_WEEK_COUNT = 12
WEEKLY_METRIC_KEYS = MONTHLY_METRIC_KEYS


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


def _canonical_previous_months(previous_stats, owner, start_month, now):
    if not isinstance(previous_stats, dict):
        return {}
    stats = previous_stats.get("stats", previous_stats)
    if not isinstance(stats, dict):
        return {}
    if (
        stats.get("owner") != owner
        or stats.get("scope") != "public"
        or stats.get("timezone") != DEFAULT_TIMEZONE
    ):
        return {}

    start_year, start_number = _parse_start_month(start_month)
    first_month = f"{start_year:04d}-{start_number:02d}"
    current_month = f"{now.year:04d}-{now.month:02d}"
    reusable = {}
    for row in stats.get("monthly", []):
        if not isinstance(row, dict):
            continue
        month = row.get("month")
        if not isinstance(month, str):
            continue
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            continue
        if month < first_month or month >= current_month or row.get("partial") is not False:
            continue
        values = [row.get(key) for key in MONTHLY_METRIC_KEYS]
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            continue
        reusable[month] = {
            "month": month,
            **{key: row[key] for key in MONTHLY_METRIC_KEYS},
            "partial": False,
        }
    return reusable


def _week_windows(now, week_count=DEFAULT_WEEK_COUNT):
    if not isinstance(week_count, int) or isinstance(week_count, bool) or week_count <= 0:
        raise ValueError("week_count must be a positive integer")

    current_monday = now.date() - timedelta(days=now.weekday())
    first_monday = current_monday - timedelta(weeks=week_count - 1)
    for offset in range(week_count):
        start_date = first_monday + timedelta(weeks=offset)
        scheduled_end = start_date + timedelta(days=6)
        is_current = start_date == current_monday
        end_date = min(scheduled_end, now.date()) if is_current else scheduled_end
        partial = is_current and end_date < scheduled_end
        yield start_date.isoformat(), end_date.isoformat(), partial


def _canonical_previous_weeks(previous_stats, owner, now, week_count):
    if not isinstance(previous_stats, dict):
        return {}
    stats = previous_stats.get("stats", previous_stats)
    if not isinstance(stats, dict):
        return {}
    if (
        stats.get("owner") != owner
        or stats.get("scope") != "public"
        or stats.get("timezone") != DEFAULT_TIMEZONE
    ):
        return {}

    expected = {
        start: end
        for start, end, partial in _week_windows(now, week_count)
        if not partial and end < now.date().isoformat()
    }
    reusable = {}
    for row in stats.get("weekly", []):
        if not isinstance(row, dict):
            continue
        start = row.get("weekStart")
        end = row.get("weekEnd")
        if start not in expected or end != expected[start] or row.get("partial") is not False:
            continue
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        values = [row.get(key) for key in WEEKLY_METRIC_KEYS]
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            continue
        reusable[start] = {
            "weekStart": start,
            "weekEnd": end,
            **{key: row[key] for key in WEEKLY_METRIC_KEYS},
            "partial": False,
        }
    return reusable


def _canonical_previous_issue_backlog(previous_history, owner):
    if not isinstance(previous_history, dict):
        return []
    if (
        previous_history.get("schemaVersion") != 1
        or previous_history.get("owner") != owner
        or previous_history.get("scope") != "public"
        or previous_history.get("timezone") != DEFAULT_TIMEZONE
    ):
        return []

    canonical = []
    seen_dates = set()
    for row in previous_history.get("snapshots", []):
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        observed_at = row.get("observedAt")
        all_open = row.get("allOpen")
        authored_open = row.get("authoredOpen")
        if not isinstance(date, str) or not isinstance(observed_at, str):
            continue
        try:
            datetime.strptime(date, "%Y-%m-%d")
            datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (
            not isinstance(all_open, int)
            or isinstance(all_open, bool)
            or all_open < 0
            or not isinstance(authored_open, int)
            or isinstance(authored_open, bool)
            or authored_open < 0
            or date in seen_dates
        ):
            continue
        seen_dates.add(date)
        canonical.append(
            {
                "date": date,
                "observedAt": observed_at,
                "allOpen": all_open,
                "authoredOpen": authored_open,
            }
        )
    canonical.sort(key=lambda row: row["date"])
    return canonical


def collect_issue_backlog_history(
    owner=DEFAULT_OWNER,
    now=None,
    token=None,
    request_fn=request_json,
    request_interval=0.0,
    sleep_fn=time.sleep,
    previous_history=None,
):
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = now.astimezone(tz) if now is not None else datetime.now(tz)

    def search(query):
        total = _search_total(
            "issues",
            query,
            token=token,
            request_fn=request_fn,
            sleep_fn=sleep_fn,
        )
        if request_interval > 0:
            sleep_fn(request_interval)
        return total

    all_open = search(f"user:{owner} is:issue is:open is:public")
    authored_open = search(f"author:{owner} is:issue is:open is:public")
    date = now.date().isoformat()
    snapshots = [
        row
        for row in _canonical_previous_issue_backlog(previous_history, owner)
        if row["date"] != date
    ]
    snapshots.append(
        {
            "date": date,
            "observedAt": now.isoformat(),
            "allOpen": all_open,
            "authoredOpen": authored_open,
        }
    )
    snapshots.sort(key=lambda row: row["date"])
    return {
        "schemaVersion": 1,
        "generatedAt": now.isoformat(),
        "owner": owner,
        "scope": "public",
        "timezone": DEFAULT_TIMEZONE,
        "snapshots": snapshots,
    }


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_previous_issue_backlog(url):
    request = Request(
        url,
        headers={"User-Agent": "KAFKA2306-agent-resources-dashboard"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise GitHubApiError(
            f"previous issue backlog request failed with HTTP {exc.code}: {url}"
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubApiError(f"previous issue backlog could not be read: {url}") from exc


def _repository_count(path):
    repositories = _load_json(path)
    if not isinstance(repositories, list):
        raise ValueError("repositories input must be a JSON array")
    if any(repository.get("visibility") != "public" for repository in repositories):
        raise ValueError("repositories input must be public-only")
    return len(repositories)


def collect_github_stats(
    owner=DEFAULT_OWNER,
    start_month=DEFAULT_START_MONTH,
    now=None,
    token=None,
    request_fn=request_json,
    request_interval=0.0,
    sleep_fn=time.sleep,
    previous_stats=None,
    public_repository_count=None,
    week_count=DEFAULT_WEEK_COUNT,
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

    if public_repository_count is None:
        public_repositories = search("repositories", f"user:{owner} is:public")
    else:
        if (
            not isinstance(public_repository_count, int)
            or isinstance(public_repository_count, bool)
            or public_repository_count < 0
        ):
            raise ValueError("public_repository_count must be a non-negative integer")
        public_repositories = public_repository_count

    archived_public_repositories = search(
        "repositories", f"user:{owner} is:public archived:true"
    )
    reusable_months = _canonical_previous_months(previous_stats, owner, start_month, now)
    reusable_weeks = _canonical_previous_weeks(previous_stats, owner, now, week_count)

    monthly = []
    for year, month in _month_range(start_month, now):
        month_key = f"{year:04d}-{month:02d}"
        if month_key in reusable_months:
            monthly.append(reusable_months[month_key])
            continue

        start, end, partial = _date_window(year, month, now)
        public = "is:public"
        monthly.append(
            {
                "month": month_key,
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

    weekly = []
    for start, end, partial in _week_windows(now, week_count):
        if start in reusable_weeks:
            weekly.append(reusable_weeks[start])
            continue

        public = "is:public"
        weekly.append(
            {
                "weekStart": start,
                "weekEnd": end,
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
        "weekly": weekly,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect public GitHub activity statistics")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--start-month", default=DEFAULT_START_MONTH)
    parser.add_argument("--request-interval", type=float, default=DEFAULT_REQUEST_INTERVAL)
    parser.add_argument("--week-count", type=int, default=DEFAULT_WEEK_COUNT)
    parser.add_argument("--repositories")
    parser.add_argument("--previous-dashboard")
    parser.add_argument("--output", default="dashboard/generated/github-stats.json")
    parser.add_argument("--issue-backlog-output")
    args = parser.parse_args()
    if args.request_interval < 0:
        parser.error("--request-interval must be non-negative")
    if args.week_count <= 0:
        parser.error("--week-count must be a positive integer")

    previous_stats = _load_json(args.previous_dashboard) if args.previous_dashboard else None
    public_repository_count = _repository_count(args.repositories) if args.repositories else None
    payload = collect_github_stats(
        owner=args.owner,
        start_month=args.start_month,
        token=os.environ.get("GITHUB_TOKEN"),
        request_interval=args.request_interval,
        previous_stats=previous_stats,
        public_repository_count=public_repository_count,
        week_count=args.week_count,
    )
    atomic_write_json(args.output, payload)

    public_snapshot_url = os.environ.get("DASHBOARD_PUBLIC_SNAPSHOT_URL")
    issue_backlog_output = args.issue_backlog_output
    if issue_backlog_output is None and public_snapshot_url:
        issue_backlog_output = DEFAULT_ISSUE_BACKLOG_OUTPUT
    if issue_backlog_output:
        history_url = os.environ.get("DASHBOARD_ISSUE_BACKLOG_HISTORY_URL")
        if history_url is None and public_snapshot_url:
            history_url = f"{public_snapshot_url.rsplit('/', 1)[0]}/issue-backlog-history.json"
        previous_history = _load_previous_issue_backlog(history_url) if history_url else None
        history = collect_issue_backlog_history(
            owner=args.owner,
            token=os.environ.get("GITHUB_TOKEN"),
            request_interval=args.request_interval,
            previous_history=previous_history,
        )
        atomic_write_json(issue_backlog_output, history)


if __name__ == "__main__":
    main()
