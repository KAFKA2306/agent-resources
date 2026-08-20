from dataclasses import dataclass

from dashboard.collectors.github_api import GitHubApiError, fetch_paginated, request_json


@dataclass(frozen=True)
class MetricResult:
    status: str
    value: object
    reason: str | None = None


def _unavailable_reason(exc):
    if exc.status in (403, 404):
        return f"github_api_http_{exc.status}"
    raise exc


def _artifact_usage(owner, repo, token, request_fn, paginate_fn):
    try:
        artifacts = paginate_fn(
            f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=100",
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


def _cache_usage(owner, repo, token, request_fn):
    try:
        payload, _ = request_fn(
            f"https://api.github.com/repos/{owner}/{repo}/actions/cache/usage",
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
    caches = _cache_usage(owner, repo, token, request_fn)

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
        "actions_cache": {
            "status": caches.status,
            "usage": caches.value,
            "reason": caches.reason,
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
    unavailable_cache_repositories = [
        row["name"] for row in rows if row["actions_cache"]["status"] != "available"
    ]

    return {
        "schema_version": "storage-budget.v1",
        "repository_count": len(rows),
        "known_actions_artifact_bytes": known_artifact_bytes,
        "known_actions_cache_bytes": known_cache_bytes,
        "unavailable_actions_artifact_repositories": unavailable_artifact_repositories,
        "unavailable_actions_cache_repositories": unavailable_cache_repositories,
        "repositories": rows,
        "notes": {
            "unknown_is_zero": False,
            "pages_bandwidth": "unavailable",
            "git_lfs_usage": "unavailable",
        },
    }
