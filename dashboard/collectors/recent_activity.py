import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from dashboard.collectors.github_api import atomic_write_json, fetch_paginated

DEFAULT_WINDOW_DAYS = 7


def _utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_z(value):
    return _utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize_issue_activity(raw, repository):
    if repository.get("visibility") != "public":
        return None
    kind = "pull_request" if "pull_request" in raw else "issue"
    number = raw.get("number")
    title = raw.get("title")
    url = raw.get("html_url")
    updated_at = raw.get("updated_at")
    if not isinstance(number, int) or number < 1 or not title or not url or not updated_at:
        raise ValueError("recent issue activity payload is incomplete")
    return {
        "id": f"activity:{repository['id']}:{kind}:{number}",
        "repositoryId": repository["id"],
        "kind": kind,
        "occurredAt": updated_at,
        "url": url,
        "summary": title,
    }


def normalize_workflow_activity(raw, repository):
    if repository.get("visibility") != "public":
        return None
    run_id = raw.get("id")
    workflow_name = raw.get("name")
    url = raw.get("html_url")
    created_at = raw.get("created_at")
    if not isinstance(run_id, int) or run_id < 1 or not workflow_name or not url or not created_at:
        raise ValueError("recent workflow activity payload is incomplete")
    return {
        "id": f"activity:{repository['id']}:workflow_run:{run_id}",
        "repositoryId": repository["id"],
        "kind": "workflow_run",
        "occurredAt": created_at,
        "url": url,
        "summary": workflow_name,
    }


def collect_recent_activity(
    repositories,
    token=None,
    fetcher=fetch_paginated,
    now=None,
    window_days=DEFAULT_WINDOW_DAYS,
):
    if not isinstance(window_days, int) or window_days < 1:
        raise ValueError("window_days must be a positive integer")
    now = _utc(now or datetime.now(timezone.utc))
    cutoff = now - timedelta(days=window_days)
    since = _iso_z(cutoff)
    until = _iso_z(now)
    activity_by_id = {}

    for repository in repositories:
        if repository.get("visibility") != "public":
            continue
        owner = quote(repository["owner"], safe="")
        name = quote(repository["name"], safe="")
        issue_query = urlencode({"state": "all", "per_page": 100, "sort": "updated", "direction": "desc", "since": since})
        issue_url = f"https://api.github.com/repos/{owner}/{name}/issues?{issue_query}"
        for raw in fetcher(issue_url, token=token):
            event = normalize_issue_activity(raw, repository)
            if event is None:
                continue
            occurred_at = _parse_time(event["occurredAt"])
            if cutoff <= occurred_at <= now:
                current = activity_by_id.get(event["id"])
                if current is None or event["occurredAt"] > current["occurredAt"]:
                    activity_by_id[event["id"]] = event

        run_query = urlencode({"per_page": 100, "created": f"{since}..{until}"})
        run_url = f"https://api.github.com/repos/{owner}/{name}/actions/runs?{run_query}"
        for raw in fetcher(run_url, token=token, item_key="workflow_runs"):
            event = normalize_workflow_activity(raw, repository)
            if event is None:
                continue
            occurred_at = _parse_time(event["occurredAt"])
            if cutoff <= occurred_at <= now:
                activity_by_id[event["id"]] = event

    return sorted(activity_by_id.values(), key=lambda event: (event["occurredAt"], event["id"]), reverse=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repositories", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = parser.parse_args(argv)
    repositories = json.loads(Path(args.repositories).read_text(encoding="utf-8"))
    activity = collect_recent_activity(repositories, token=os.getenv("GITHUB_TOKEN"), window_days=args.window_days)
    atomic_write_json(args.output, activity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
