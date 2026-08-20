import argparse
import calendar
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, fetch_paginated, request_json

API_ROOT = "https://api.github.com"
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_INCLUDED_MINUTES = 2000
DEFAULT_WARNING_MINUTES = 1200
DEFAULT_CRITICAL_MINUTES = 1600
DEFAULT_HARD_REMEDIATION_MINUTES = 1800


def _as_date(value):
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("today must be a date or datetime")


def _month_window(today):
    start = today.replace(day=1)
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return start, end


def _query_total(url, token, request_fn=request_json):
    payload, _ = request_fn(url, token)
    if not isinstance(payload, dict):
        raise GitHubApiError("unexpected GitHub API response shape")
    total = payload.get("total_count")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise GitHubApiError("GitHub API returned invalid total_count")
    return total


def _private_repositories(owner, token, request_fn=request_json, paginate_fn=fetch_paginated):
    url = f"{API_ROOT}/user/repos?{urlencode({'visibility': 'private', 'affiliation': 'owner', 'per_page': 100})}"
    repositories = paginate_fn(url, token=token, request_fn=request_fn)
    result = []
    for repository in repositories:
        if not isinstance(repository, dict):
            continue
        if repository.get("private") is not True:
            continue
        repo_owner = repository.get("owner") or {}
        if repo_owner.get("login") != owner:
            continue
        name = repository.get("name")
        if not isinstance(name, str) or not name:
            continue
        result.append(
            {
                "name": name,
                "full_name": f"{owner}/{name}",
                "archived": repository.get("archived") is True,
            }
        )
    return sorted(result, key=lambda item: item["full_name"].lower())


def _active_workflows(owner, repo, token, request_fn=request_json):
    payload, _ = request_fn(f"{API_ROOT}/repos/{owner}/{repo}/actions/workflows?per_page=100", token)
    if not isinstance(payload, dict) or not isinstance(payload.get("workflows"), list):
        raise GitHubApiError("unexpected Actions workflows response shape")

    workflows = []
    for workflow in payload["workflows"]:
        if not isinstance(workflow, dict) or workflow.get("state") != "active":
            continue
        name = workflow.get("name")
        path = workflow.get("path")
        if not isinstance(name, str) or not name or not isinstance(path, str) or not path:
            raise GitHubApiError("active Actions workflow is missing name or path")
        workflows.append({"name": name, "path": path})
    return sorted(workflows, key=lambda item: (item["path"].lower(), item["name"].lower()))


def _run_count(owner, repo, start, end, token, request_fn=request_json):
    query = urlencode({"created": f"{start.isoformat()}..{end.isoformat()}", "per_page": 1})
    url = f"{API_ROOT}/repos/{owner}/{repo}/actions/runs?{query}"
    return _query_total(url, token, request_fn=request_fn)


def _billing_usage(owner, today, token, request_fn=request_json):
    query = urlencode({"year": today.year, "month": today.month})
    url = f"{API_ROOT}/users/{owner}/settings/billing/usage?{query}"
    try:
        payload, _ = request_fn(url, token)
    except GitHubApiError as exc:
        if exc.status in {403, 404}:
            return {
                "status": "unavailable",
                "reason": f"github_api_http_{exc.status}",
                "reported_actions_minutes": None,
                "reported_actions_minutes_by_repository": None,
                "reported_actions_minutes_by_sku": None,
            }
        raise

    items = payload.get("usageItems") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise GitHubApiError("unexpected billing usage response shape")

    minutes = 0.0
    by_repository = defaultdict(float)
    by_sku = defaultdict(float)
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("product", "")).lower() != "actions":
            continue
        if str(item.get("unitType", "")).lower() != "minutes":
            continue
        quantity = item.get("quantity")
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity < 0:
            raise GitHubApiError("invalid Actions billing quantity")
        quantity = float(quantity)
        minutes += quantity

        repository_name = item.get("repositoryName")
        if isinstance(repository_name, str) and repository_name:
            by_repository[repository_name] += quantity
        sku = item.get("sku")
        if isinstance(sku, str) and sku:
            by_sku[sku] += quantity

    def sorted_breakdown(values):
        return [
            {"name": name, "minutes": value}
            for name, value in sorted(values.items(), key=lambda pair: (-pair[1], pair[0].lower()))
        ]

    return {
        "status": "available",
        "reason": None,
        "reported_actions_minutes": minutes,
        "reported_actions_minutes_by_repository": sorted_breakdown(by_repository),
        "reported_actions_minutes_by_sku": sorted_breakdown(by_sku),
    }


def _budget_state(minutes, warning, critical, hard):
    if minutes is None:
        return "unknown"
    if minutes >= hard:
        return "hard_remediation"
    if minutes >= critical:
        return "critical"
    if minutes >= warning:
        return "warning"
    return "green"


def collect_actions_budget(
    owner=DEFAULT_OWNER,
    today=None,
    token=None,
    request_fn=request_json,
    paginate_fn=fetch_paginated,
    included_minutes=DEFAULT_INCLUDED_MINUTES,
    warning_minutes=DEFAULT_WARNING_MINUTES,
    critical_minutes=DEFAULT_CRITICAL_MINUTES,
    hard_remediation_minutes=DEFAULT_HARD_REMEDIATION_MINUTES,
):
    today = _as_date(today)
    if token is None:
        raise ValueError("token is required to audit private repositories")
    thresholds = [warning_minutes, critical_minutes, hard_remediation_minutes, included_minutes]
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in thresholds):
        raise ValueError("budget thresholds must be positive integers")
    if not (warning_minutes < critical_minutes < hard_remediation_minutes <= included_minutes):
        raise ValueError("budget thresholds must be strictly increasing through included minutes")

    month_start, month_end = _month_window(today)
    rolling_start = max(month_start, today - timedelta(days=6))
    repositories = _private_repositories(owner, token, request_fn=request_fn, paginate_fn=paginate_fn)

    rows = []
    for repository in repositories:
        if repository["archived"]:
            rows.append(
                {
                    **repository,
                    "active_workflows": 0,
                    "active_workflow_inventory": [],
                    "month_to_date_runs": 0,
                    "rolling_7d_runs": 0,
                    "forward_active": False,
                }
            )
            continue
        active_workflow_inventory = _active_workflows(owner, repository["name"], token, request_fn=request_fn)
        month_runs = _run_count(owner, repository["name"], month_start, today, token, request_fn=request_fn)
        rolling_runs = _run_count(owner, repository["name"], rolling_start, today, token, request_fn=request_fn)
        rows.append(
            {
                **repository,
                "active_workflows": len(active_workflow_inventory),
                "active_workflow_inventory": active_workflow_inventory,
                "month_to_date_runs": month_runs,
                "rolling_7d_runs": rolling_runs,
                "forward_active": bool(active_workflow_inventory) and rolling_runs > 0,
            }
        )

    billing = _billing_usage(owner, today, token, request_fn=request_fn)
    reported_minutes = billing["reported_actions_minutes"]
    state = _budget_state(reported_minutes, warning_minutes, critical_minutes, hard_remediation_minutes)
    remaining = None if reported_minutes is None else max(0.0, included_minutes - reported_minutes)

    active_rows = [row for row in rows if row["forward_active"]]
    rolling_runs = sum(row["rolling_7d_runs"] for row in active_rows)
    projected_runs = round((rolling_runs / max(1, (today - rolling_start).days + 1)) * month_end.day, 2)

    return {
        "schema_version": "actions-budget.v1",
        "generated_at": datetime.combine(today, datetime.min.time()).isoformat(),
        "owner": owner,
        "scope": "private_repositories",
        "policy": {
            "plan_contract": "github_free_personal",
            "included_actions_minutes_per_month": included_minutes,
            "warning_minutes": warning_minutes,
            "critical_minutes": critical_minutes,
            "hard_remediation_minutes": hard_remediation_minutes,
            "primary_source": "https://docs.github.com/en/billing/reference/product-usage-included",
        },
        "billing": {
            **billing,
            "remaining_included_minutes": remaining,
            "budget_state": state,
            "usage_source": "https://docs.github.com/en/rest/billing/usage",
        },
        "activity": {
            "month": f"{today.year:04d}-{today.month:02d}",
            "private_repository_count": len(rows),
            "forward_active_repository_count": len(active_rows),
            "month_to_date_runs": sum(row["month_to_date_runs"] for row in rows),
            "rolling_7d_runs": rolling_runs,
            "projected_monthly_runs_from_active_repositories": projected_runs,
            "projection_is_billed_minutes": False,
        },
        "repositories": sorted(
            rows,
            key=lambda row: (row["month_to_date_runs"], row["rolling_7d_runs"], row["full_name"]),
            reverse=True,
        ),
        "decision": {
            "can_assert_remaining_minutes": reported_minutes is not None,
            "highest_run_repository": max(rows, key=lambda row: row["month_to_date_runs"])["full_name"] if rows else None,
            "highest_billed_repository": (
                billing["reported_actions_minutes_by_repository"][0]["name"]
                if billing.get("reported_actions_minutes_by_repository")
                else None
            ),
            "next_action": (
                "inspect highest-run active private workflows before adding scheduled jobs"
                if active_rows
                else "no recent active private workflow burn detected"
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Audit private GitHub Actions budget without treating run counts as billed minutes")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--output", default="dashboard/generated/actions-budget.json")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN with private-repository access is required")
    payload = collect_actions_budget(owner=args.owner, token=token)
    atomic_write_json(args.output, payload)


if __name__ == "__main__":
    main()
