from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime

SNAPSHOT_POLL_INTERVAL_SECONDS = 5


class FactoryStateRevisionMismatch(ValueError):
    """The Pages snapshot exists but has not reached the expected revision yet."""


def _parse_generated_at(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("factory state generatedAt is missing")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("factory state generatedAt is invalid") from error
    if timestamp.tzinfo is None:
        raise ValueError("factory state generatedAt must include a timezone")
    return timestamp


def validate_factory_state(payload: object, *, expected_sha: str) -> None:
    if not isinstance(payload, dict):
        raise TypeError("factory state must be an object")
    _parse_generated_at(payload.get("generatedAt"))

    source_revision = payload.get("sourceRevision")
    if source_revision != expected_sha:
        raise FactoryStateRevisionMismatch(
            f"factory state revision mismatch: {source_revision!r} != {expected_sha!r}"
        )
    authority = payload.get("authority")
    if not isinstance(authority, dict) or authority.get("mainSha") != expected_sha:
        raise ValueError("factory state authority does not match expected main")
    pages = payload.get("pages")
    if (
        not isinstance(pages, dict)
        or pages.get("sourceRevision") != expected_sha
        or not pages.get("workflowRunId")
        or not pages.get("workflowRunUrl")
    ):
        raise ValueError("factory state Pages provenance is incomplete or mismatched")
    issue = payload.get("canonicalIssue")
    if not isinstance(issue, dict) or issue.get("number") != 381:
        raise ValueError("factory state canonical issue is missing")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("factory state capabilities are missing")


def verify_production_factory_state(page_url: str, expected_sha: str) -> dict:
    base = page_url.rstrip("/")
    payload = _fetch_json(f"{base}/dashboard/factory-state.json?v={expected_sha}")
    validate_factory_state(payload, expected_sha=expected_sha)
    return payload


def wait_for_production_factory_state(
    page_url: str,
    expected_sha: str,
    *,
    timeout_seconds: int = 0,
    fetch_json: Callable[[str], dict] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    if timeout_seconds < 0:
        raise ValueError("timeout_seconds must not be negative")
    fetcher = fetch_json or _fetch_json
    attempts = timeout_seconds // SNAPSHOT_POLL_INTERVAL_SECONDS + 1
    base = page_url.rstrip("/")
    url = f"{base}/dashboard/factory-state.json?v={expected_sha}"

    for attempt in range(1, attempts + 1):
        payload = fetcher(url)
        try:
            validate_factory_state(payload, expected_sha=expected_sha)
        except FactoryStateRevisionMismatch:
            if attempt == attempts:
                raise
            print(
                f"Pages factory snapshot is not at {expected_sha} yet "
                f"({attempt}/{attempts - 1} bounded waits).",
                flush=True,
            )
            sleep(SNAPSHOT_POLL_INTERVAL_SECONDS)
            continue
        return payload

    raise RuntimeError("bounded Pages snapshot wait ended without a result")


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Accept": "application/json",
            "User-Agent": "agent-resources-snapshot-smoke",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify the canonical static factory snapshot")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="bounded wait for Pages to publish EXPECTED_SHA; zero performs a single read",
    )
    arguments = parser.parse_args(argv)
    page_url = os.environ["PAGE_URL"]
    expected_sha = os.environ["EXPECTED_SHA"]
    factory = wait_for_production_factory_state(
        page_url,
        expected_sha,
        timeout_seconds=arguments.timeout_seconds,
    )
    print(f"factory snapshot revision: {factory['sourceRevision']}")
    print(f"factory snapshot generatedAt: {factory['generatedAt']}")
    print(f"Pages workflow run: {factory['pages']['workflowRunId']}")
    print(f"capability states: {len(factory['capabilities'])}")
    print("current production verification: UNVERIFIED by this static snapshot probe")


if __name__ == "__main__":
    main()
