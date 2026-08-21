import argparse
import json
import os
from datetime import datetime, timezone
from urllib.parse import quote

from dashboard.collectors.github_api import (
    API_VERSION,
    atomic_write_json,
    fetch_paginated,
    request_json,
)
from dashboard.collectors.repositories import (
    ZONE_TOPIC_PREFIX,
    collect_repositories,
    load_config,
    normalize_group_fragment,
)


def classification_from_repository(raw):
    topics = raw.get("topics") or []
    if not isinstance(topics, list):
        raise ValueError("repository topics must be a list")
    zones = sorted(
        normalize_group_fragment(topic[len(ZONE_TOPIC_PREFIX) :])
        for topic in topics
        if isinstance(topic, str)
        and topic.startswith(ZONE_TOPIC_PREFIX)
        and topic[len(ZONE_TOPIC_PREFIX) :]
    )
    evidence = [raw["html_url"]]
    if len(zones) == 1:
        return {"domain": zones[0], "source": "github-topic", "evidence": evidence}
    if len(zones) > 1:
        return {"domain": None, "source": "conflicting-github-topics", "evidence": evidence}
    return {"domain": None, "source": "no-agent-zone-topic", "evidence": evidence}


def normalize_branch(raw, default_branch):
    name = raw.get("name")
    commit_sha = (raw.get("commit") or {}).get("sha")
    protected = raw.get("protected")
    if not name or not commit_sha or not isinstance(protected, bool):
        raise ValueError("branch payload is missing name, commit sha, or protected flag")
    return {
        "name": name,
        "commitSha": commit_sha,
        "isDefault": name == default_branch,
        "protected": protected,
        "deletionCandidate": False,
        "deletionConfirmed": False,
        "deleted": False,
        "blockedReason": None,
    }


def collect_repository_operations(
    config,
    *,
    token=None,
    run_id,
    generated_at=None,
    repository_collector=collect_repositories,
    request_fn=request_json,
    pagination_fetcher=fetch_paginated,
):
    repositories = repository_collector(config, token=token)
    snapshots = []
    for repository in repositories:
        owner = quote(repository["owner"], safe="")
        name = quote(repository["name"], safe="")
        api_url = f"https://api.github.com/repos/{owner}/{name}"
        detail, _ = request_fn(api_url, token)
        default_branch = detail.get("default_branch")
        if not default_branch:
            raise ValueError(f"repository payload is missing default_branch: {repository['name']}")
        branches = pagination_fetcher(f"{api_url}/branches?per_page=100", token=token)
        normalized_branches = [normalize_branch(branch, default_branch) for branch in branches]
        normalized_branches.sort(key=lambda branch: branch["name"].lower())
        snapshots.append(
            {
                "name": repository["name"],
                "url": repository["url"],
                "classification": classification_from_repository(detail),
                "branches": normalized_branches,
            }
        )
    snapshots.sort(key=lambda repository: repository["name"].lower())
    generated = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "generatedAt": generated,
        "sourceRevision": f"github-rest-api-{API_VERSION}",
        "runId": run_id,
        "repositories": snapshots,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=False)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config) if args.config else load_config()
    snapshot = collect_repository_operations(
        config,
        token=os.getenv("GITHUB_TOKEN"),
        run_id=args.run_id,
    )
    atomic_write_json(args.output, snapshot)
    print(json.dumps({"repositories": len(snapshot["repositories"]), "output": args.output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
