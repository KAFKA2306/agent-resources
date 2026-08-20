from __future__ import annotations

import argparse
import json
from pathlib import Path

from dashboard.collectors.github_api import atomic_write_json

ALLOWED_BRANCH_STATUSES = {"candidate", "confirmed", "deleted", "blocked"}
ALLOWED_CLASSIFICATION_SOURCES = {
    "agent-zone-topic",
    "local-model-suggestion",
    "unclassified",
}


def _classification_suggestions(payload: dict | None, scope: str, owner: str) -> dict[str, dict]:
    if payload is None or payload.get("status") == "SKIPPED":
        return {}
    if payload.get("scope") != scope or payload.get("owner") != owner:
        raise ValueError("classification suggestions scope/owner mismatch")
    suggestions = {}
    for row in payload.get("classifications", []):
        repository = row.get("repository")
        if not isinstance(repository, str) or not repository:
            continue
        if row.get("status") == "FAILED" or row.get("acceptedForView") is not True:
            continue
        group = row.get("suggestedGroup")
        confidence = row.get("confidence")
        if not isinstance(group, str) or not group:
            raise ValueError("accepted classification suggestion has no group")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("accepted classification suggestion has invalid confidence")
        confidence = float(confidence)
        if not 0 <= confidence <= 1:
            raise ValueError("accepted classification suggestion confidence is outside 0..1")
        suggestions[repository] = {
            "group": group,
            "confidence": confidence,
        }
    return suggestions


def combine_operations_snapshot(
    inventory: dict,
    branch_report: dict,
    classification_suggestions: dict | None = None,
) -> dict:
    scope = "public-nonarchived-owned-repositories"
    if inventory.get("scope") != scope or branch_report.get("scope") != scope:
        raise ValueError("operations inputs must use the public non-archived repository scope")
    if inventory.get("owner") != branch_report.get("owner"):
        raise ValueError("operations inputs have different owners")
    owner = inventory["owner"]
    suggestions = _classification_suggestions(classification_suggestions, scope, owner)

    explicit_domains = {
        row.get("group")
        for row in inventory.get("repositories", [])
        if row.get("classificationSource") == "agent-zone-topic"
        and isinstance(row.get("group"), str)
        and row.get("group")
    }

    repositories = []
    valid_names = set()
    for row in inventory.get("repositories", []):
        full_name = row.get("fullName")
        name = row.get("name")
        group = row.get("group")
        source = row.get("classificationSource")
        url = row.get("url")
        if not all(
            isinstance(value, str) and value for value in (full_name, name, group, source, url)
        ):
            raise ValueError("repository operations row is incomplete")
        if source not in {"agent-zone-topic", "unclassified"}:
            raise ValueError("repository classification source is invalid")
        valid_names.add(full_name)
        item = {
            "name": name,
            "fullName": full_name,
            "url": url,
            "group": group,
            "classificationSource": source,
        }
        suggestion = suggestions.get(full_name)
        if source == "unclassified" and suggestion is not None:
            if suggestion["group"] not in explicit_domains:
                raise ValueError("local-model suggestion uses a domain with no explicit repository anchor")
            item["group"] = suggestion["group"]
            item["classificationSource"] = "local-model-suggestion"
            item["classificationConfidence"] = suggestion["confidence"]
        repositories.append(item)
    repositories.sort(key=lambda row: row["fullName"].casefold())

    branches = []
    for row in branch_report.get("branches", []):
        repository = row.get("repository")
        branch = row.get("branch")
        status = row.get("status")
        reason = row.get("reason")
        if repository not in valid_names:
            raise ValueError("branch operation references a repository outside the sanitized inventory")
        if not all(isinstance(value, str) and value for value in (branch, status, reason)):
            raise ValueError("branch operation row is incomplete")
        if status not in ALLOWED_BRANCH_STATUSES:
            raise ValueError("branch operation status is invalid")
        item = {
            "repository": repository,
            "branch": branch,
            "status": status,
            "reason": reason,
        }
        for key in ("commit_date", "first_seen", "confirmed_at"):
            value = row.get(key)
            if isinstance(value, str) and value:
                item[key] = value
        branches.append(item)
    branches.sort(key=lambda row: (row["repository"].casefold(), row["branch"].casefold()))

    summary = {
        "repositoryCount": len(repositories),
        "classifiedCount": sum(
            row["classificationSource"] != "unclassified" for row in repositories
        ),
        "explicitClassifiedCount": sum(
            row["classificationSource"] == "agent-zone-topic" for row in repositories
        ),
        "modelSuggestedCount": sum(
            row["classificationSource"] == "local-model-suggestion" for row in repositories
        ),
        "unclassifiedCount": sum(
            row["classificationSource"] == "unclassified" for row in repositories
        ),
        "candidateCount": sum(row["status"] == "candidate" for row in branches),
        "confirmedCount": sum(row["status"] == "confirmed" for row in branches),
        "deletedCount": sum(row["status"] == "deleted" for row in branches),
        "blockedCount": sum(row["status"] == "blocked" for row in branches),
    }
    return {
        "schemaVersion": 1,
        "scope": scope,
        "owner": owner,
        "collectedAt": branch_report.get("collectedAt") or inventory.get("collectedAt"),
        "repositories": repositories,
        "branches": branches,
        "summary": summary,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--branches", required=True)
    parser.add_argument("--classification-suggestions")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    branch_report = json.loads(Path(args.branches).read_text(encoding="utf-8"))
    suggestions = (
        json.loads(Path(args.classification_suggestions).read_text(encoding="utf-8"))
        if args.classification_suggestions
        else None
    )
    snapshot = combine_operations_snapshot(inventory, branch_report, suggestions)
    atomic_write_json(args.output, snapshot)
    print(json.dumps(snapshot["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
