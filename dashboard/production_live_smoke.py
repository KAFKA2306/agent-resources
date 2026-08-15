from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

LIVE_MAX_AGE_SECONDS = 150
LIVE_CLOCK_SKEW_TOLERANCE_SECONDS = 300
RETRY_ATTEMPTS = 6
RETRY_DELAY_SECONDS = 5


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("live payload fetchedAt is missing")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        raise ValueError("live payload fetchedAt must include a timezone")
    return timestamp.astimezone(timezone.utc)


def validate_live_payload(payload: object, *, now: datetime | None = None) -> float:
    if not isinstance(payload, dict):
        raise ValueError("live payload must be an object")
    if payload.get("scope") != "public":
        raise ValueError("live payload scope is not public")

    repositories = payload.get("repositories")
    work_items = payload.get("workItems")
    activity = payload.get("activity")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("live payload has zero repositories")
    if not isinstance(work_items, list) or not isinstance(activity, list):
        raise ValueError("live payload workItems/activity are invalid")
    if any(repo.get("visibility") != "public" or repo.get("archived") is True for repo in repositories):
        raise ValueError("live payload crossed the public repository boundary")

    repository_ids = {repo.get("id") for repo in repositories}
    if None in repository_ids or len(repository_ids) != len(repositories):
        raise ValueError("live payload repository ids are missing or duplicated")
    if any(item.get("repositoryId") not in repository_ids for item in [*work_items, *activity]):
        raise ValueError("live payload references a non-public repository")

    summary = payload.get("summary")
    if not isinstance(summary, dict) or summary.get("repositoryCount") != len(repositories):
        raise ValueError("live payload repository count diverged from summary")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    fetched_at = _parse_timestamp(payload.get("fetchedAt"))
    age_seconds = (current - fetched_at).total_seconds()
    if age_seconds < -LIVE_CLOCK_SKEW_TOLERANCE_SECONDS:
        raise ValueError(f"live payload fetchedAt is too far in the future: {age_seconds:.1f}s")
    if age_seconds > LIVE_MAX_AGE_SECONDS:
        raise ValueError(f"live payload is stale: {age_seconds:.1f}s")
    return age_seconds


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "Accept": "application/json", "User-Agent": "agent-resources-live-smoke"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_production_live(page_url: str, expected_sha: str) -> tuple[str, dict, float]:
    base = page_url.rstrip("/")
    config_url = f"{base}/dashboard/live-config.json?v={expected_sha}"
    config = _fetch_json(config_url)
    endpoint = config.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("deployed live-config.json has no HTTPS endpoint")
    payload = _fetch_json(endpoint)
    age_seconds = validate_live_payload(payload)
    return endpoint, payload, age_seconds


def main() -> None:
    page_url = os.environ["PAGE_URL"]
    expected_sha = os.environ["EXPECTED_SHA"]
    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            endpoint, payload, age_seconds = verify_production_live(page_url, expected_sha)
            print(f"live endpoint: {endpoint}")
            print(f"live repositories: {len(payload['repositories'])}")
            print(f"live fetchedAt: {payload['fetchedAt']}")
            print(f"live age seconds: {age_seconds:.1f}")
            return
        except Exception as error:
            last_error = error
            if attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("production live smoke exhausted retries") from last_error


if __name__ == "__main__":
    main()
