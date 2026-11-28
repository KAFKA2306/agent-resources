from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime


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
        raise ValueError(
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


def main() -> None:
    page_url = os.environ["PAGE_URL"]
    expected_sha = os.environ["EXPECTED_SHA"]
    factory = verify_production_factory_state(page_url, expected_sha)
    print(f"factory snapshot revision: {factory['sourceRevision']}")
    print(f"factory snapshot generatedAt: {factory['generatedAt']}")
    print(f"Pages workflow run: {factory['pages']['workflowRunId']}")
    print(f"capability states: {len(factory['capabilities'])}")
    print("current production verification: UNVERIFIED by this static snapshot probe")


if __name__ == "__main__":
    main()
