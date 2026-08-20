import argparse
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

from dashboard.collectors.github_api import (
    GitHubApiError,
    atomic_write_json,
    fetch_paginated,
    request_json,
)

API_ROOT = "https://api.github.com"
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_OUTPUT = "dashboard/generated/storage-budget.json"


@dataclass(frozen=True)
class MetricResult:
    status: str
    value: object
    reason: str | None = None


def _unavailable_reason(exc):
    if exc.status in (403, 404):
        return f"github_api_http_{exc.status}"
    raise exc


def _owned_repositories(owner, token, paginate_fn=fetch_paginated, request_fn=request_json):
    query = urlencode({"affiliation": "owner", "per_page": 100, "sort": "full_name"})
    repositories = paginate_fn(
        f"{API_ROOT}/user/repos?{query}",
        token=token,
        request_fn=request_fn,
    )
    result = []
    for repository in repositories:
        if not isinstance(repository, dict):
            continue
        repo_owner = repository.get("owner") or {}
        if repo_owner.get("login") != owner:
            continue
        name = repository.get("name")
        if not isinstance(name, str) or not name:
            continue
        result.append(repository)
    return sorted(result, key=lambda item: item["name"].lower())


def _artifact_usage(owner, repo, token, request_fn, paginate_fn):
    try:
        artifacts = paginate_fn(
            f"{API_ROOT}/repos/{owner}/{repo}/actions/artifacts?per_page=100",
            token,
            request_fn=request_fn,
            item_key="artifacts",
        )
    except GitHubApiError as exc:
        return MetricResult("unavailable", None, _unavailable_reason(exc))

    active = [item for item in artifacts if not item.get("expired", False)]
    return MetricResult(
        "available",
        {
            "count": len(active),
            "size_in_bytes": sum(int(item.get("size_in_bytes") or 0) for item in active),
            "expired_count": len(artifacts) - len(active),
        },
    )


def _artifact_log_retention(owner, repo, token, request_fn):
    try:
        payload, _ = request_fn(
            f"{API_ROOT}/repos/{owner}/{repo}/actions/permissions/artifact-and-log-retention",
            token,
        )
    except GitHubApiError as exc:
        return MetricResult("unavailable", None, _unavailable_reason(exc))

    days = payload.get("days") if isinstance(payload, dict) else None
    maximum_allowed_days = payload.get("maximum_allowed_days") if isinstance(payload, dict) else None
    if (
        not isinstance(days, int)
        or isinstance(days, bool)
        or days <= 0
        or not isinstance(maximum_allowed_days, int)
        or isinstance(maximum_allowed_days, bool)
        or maximum_allowed_days <= 0
    ):
        raise GitHubApiError("unexpected artifact and log retention response shape")

    return MetricResult(
        "available",
        {
            "days": days,
            "maximum_allowed_days": maximum_allowed_days,
        },
    )


def _cache_usage(owner, repo, token, request_fn):
    try:
        payload, _ = request_fn(
            f"{API_ROOT}/repos/{owner}/{repo}/actions/cache/usage",
            token,
        )
    except GitHubApiError as exc:
        return MetricResult("unavailable", None, _unavailable_reason(exc))

    return MetricResult(
        "available",
        {
            "count": int(payload.get("active_caches_count") or 0),
            "size_in_bytes": int(payload.get("active_caches_size_in_bytes") or 0),
        },
    )


def _cache_inventory(owner, repo, token, request_fn, paginate_fn):
    try:
        caches = paginate_fn(
            f"{API_ROOT}/repos/{owner}/{repo}/actions/caches?per_page=100",
            token,
            request_fn=request_fn,
            item_key="actions_caches",
        )
    except GitHubApiError as exc:
        return MetricResult("unavailable", None, _unavailable_reason(exc))

    entries = []
    key_ref_counts = Counter()
    for item in caches:
        key = item.get("key")
        ref = item.get("ref")
        if not isinstance(key, str) or not isinstance(ref, str):
            continue
        key_ref_counts[(key, ref)] += 1
        entries.append(
            {
                "key": key,
                "ref": ref,
                "version": item.get("version"),
                "created_at": item.get("created_at"),
                "last_accessed_at": item.get("last_accessed_at"),
                "size_in_bytes": int(item.get("size_in_bytes") or 0),
            }
        )

    last_accessed = sorted(
        entry["last_accessed_at"]
        for entry in entries
        if isinstance(entry.get("last_accessed_at"), str)
    )
    return MetricResult(
        "available",
        {
            "entry_count": len(entries),
            "unique_key_count": len({entry["key"] for entry in entries}),
            "unique_ref_count": len({entry["ref"] for entry in entries}),
            "key_ref_pairs_with_multiple_entries": sum(
                1 for count in key_ref_counts.values() if count > 1
            ),
            "max_entries_per_key_ref": max(key_ref_counts.values(), default=0),
            "oldest_last_accessed_at": last_accessed[0] if last_accessed else None,
            "newest_last_accessed_at": last_accessed[-1] if last_accessed else None,
            "entries": sorted(
                entries,
                key=lambda entry: (
                    entry["key"],
                    entry["ref"],
                    entry.get("created_at") or "",
                ),
            ),
        },
    )


def collect_repository_storage(
    repository,
    *,
    token,
    request_fn=request_json,
    paginate_fn=fetch_paginated,
):
    owner = repository["owner"]["login"]
    repo = repository["name"]
    artifacts = _artifact_usage(owner, repo, token, request_fn, paginate_fn)
    retention = _artifact_log_retention(owner, repo, token, request_fn)
    caches = _cache_usage(owner, repo, token, request_fn)
    cache_inventory = _cache_inventory(owner, repo, token, request_fn, paginate_fn)

    return {
        "name": f"{owner}/{repo}",
        "private": bool(repository.get("private")),
        "archived": bool(repository.get("archived")),
        "repository_size_kb": repository.get("size"),
        "pages_enabled": repository.get("has_pages"),
        "actions_artifacts": {
            "status": artifacts.status,
            "usage": artifacts.value,
            "reason": artifacts.reason,
        },
        "actions_artifact_log_retention": {
            "status": retention.status,
            "setting": retention.value,
            "reason": retention.reason,
        },
        "actions_cache": {
            "status": caches.status,
            "usage": caches.value,
            "reason": caches.reason,
            "inventory_status": cache_inventory.status,
            "inventory": cache_inventory.value,
            "inventory_reason": cache_inventory.reason,
        },
    }


def collect_storage_budget(
    repositories,
    *,
    token,
    request_fn=request_json,
    paginate_fn=fetch_paginated,
):
    rows = []
    for repository in repositories:
        if repository.get("archived"):
            continue
        rows.append(
            collect_repository_storage(
                repository,
                token=token,
                request_fn=request_fn,
                paginate_fn=paginate_fn,
            )
        )

    known_artifact_bytes = sum(
        row["actions_artifacts"]["usage"]["size_in_bytes"]
        for row in rows
        if row["actions_artifacts"]["status"] == "available"
    )
    known_cache_bytes = sum(
        row["actions_cache"]["usage"]["size_in_bytes"]
        for row in rows
        if row["actions_cache"]["status"] == "available"
    )
    unavailable_artifact_repositories = [
        row["name"] for row in rows if row["actions_artifacts"]["status"] != "available"
    ]
    unavailable_retention_repositories = [
        row["name"]
        for row in rows
        if row["actions_artifact_log_retention"]["status"] != "available"
    ]
    unavailable_cache_repositories = [
        row["name"] for row in rows if row["actions_cache"]["status"] != "available"
    ]
    unavailable_cache_inventory_repositories = [
        row["name"]
        for row in rows
        if row["actions_cache"]["inventory_status"] != "available"
    ]

    return {
        "schema_version": "storage-budget.v1",
        "repository_count": len(rows),
        "known_actions_artifact_bytes": known_artifact_bytes,
        "known_actions_cache_bytes": known_cache_bytes,
        "unavailable_actions_artifact_repositories": unavailable_artifact_repositories,
        "unavailable_actions_artifact_log_retention_repositories": unavailable_retention_repositories,
        "unavailable_actions_cache_repositories": unavailable_cache_repositories,
        "unavailable_actions_cache_inventory_repositories": unavailable_cache_inventory_repositories,
        "repositories": rows,
        "notes": {
            "unknown_is_zero": False,
            "pages_bandwidth": "unavailable",
            "git_lfs_usage": "unavailable",
        },
    }


def collect_owner_storage_budget(
    owner=DEFAULT_OWNER,
    *,
    token,
    request_fn=request_json,
    paginate_fn=fetch_paginated,
):
    if not token:
        raise ValueError("token is required to audit owned repositories")
    repositories = _owned_repositories(
        owner,
        token,
        paginate_fn=paginate_fn,
        request_fn=request_fn,
    )
    payload = collect_storage_budget(
        repositories,
        token=token,
        request_fn=request_fn,
        paginate_fn=paginate_fn,
    )
    return {
        **payload,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "owner": owner,
        "scope": "owned_active_repositories",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit Actions artifact/cache storage for all active repositories owned by an account"
    )
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN with repository access is required")
    payload = collect_owner_storage_budget(args.owner, token=token)
    atomic_write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
