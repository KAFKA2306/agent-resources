from __future__ import annotations

import argparse
import json
import os
import re
from typing import Callable, Sequence
from urllib.parse import quote

from dashboard.collectors.github_api import request_json, request_mutation
from dashboard.factory_reflection import discover_recurrent_workflow_candidates

_MARKER_RE = re.compile(r"<!-- factory-reflection:(reflection:[0-9a-f]{24}) -->")


def reconcile_stale_reflection_issues(
    *,
    owner: str,
    repository: str,
    active_candidate_ids: set[str],
    token: str | None = None,
    request_fn: Callable = request_json,
    mutation_fn: Callable = request_mutation,
    execute: bool = True,
) -> list[int]:
    base = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
    issues, _ = request_fn(
        f"{base}/issues?state=open&per_page=100&sort=updated&direction=desc", token
    )
    if not isinstance(issues, list):
        raise ValueError("open issue list evidence is invalid")

    stale: list[int] = []
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        match = _MARKER_RE.search(str(issue.get("body") or ""))
        number = issue.get("number")
        if not match or not isinstance(number, int):
            continue
        if match.group(1) in active_candidate_ids:
            continue
        stale.append(number)
        if execute:
            mutation_fn(
                f"{base}/issues/{number}",
                token,
                method="PATCH",
                payload={"state": "closed", "state_reason": "not_planned"},
            )
    return stale


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="KAFKA2306/agent-resources")
    parser.add_argument("--observe-only", action="store_true")
    args = parser.parse_args(argv)
    owner, repository = args.repository.split("/", 1)
    token = os.getenv("GITHUB_TOKEN")
    candidates = discover_recurrent_workflow_candidates(
        owner=owner, repository=repository, token=token
    )
    active = {str(candidate["candidate_id"]) for candidate in candidates}
    stale = reconcile_stale_reflection_issues(
        owner=owner,
        repository=repository,
        active_candidate_ids=active,
        token=token,
        execute=not args.observe_only,
    )
    print(json.dumps({"active_candidate_ids": sorted(active), "closed_issue_numbers": stale}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
