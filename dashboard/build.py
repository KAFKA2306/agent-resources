import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from dashboard.collectors.github_api import atomic_write_json
from dashboard.domain.lanes import add_lane

ACTIVITY_WINDOW_DAYS = 7
OPENCLAW_AUTOMATION_STATUSES = {
    "disabled",
    "running",
    "ok",
    "error",
    "skipped",
    "idle",
    "unknown",
}
REPOSITORY_OPERATION_STATUSES = {"candidate", "confirmed", "deleted", "blocked"}
REPOSITORY_CLASSIFICATION_SOURCES = {
    "agent-zone-topic",
    "local-model-suggestion",
    "unclassified",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_repository(repository):
    if repository.get("visibility") != "public":
        return None
    canonical = {
        key: repository[key]
        for key in ("id", "owner", "name", "url", "group", "visibility", "updatedAt")
    }
    if "publicLinks" in repository:
        canonical["publicLinks"] = repository["publicLinks"]
    return canonical


def canonical_stats(stats, public_repository_count):
    if stats is None:
        return None
    if stats.get("scope") != "public":
        raise ValueError("dashboard stats must be public-only")
    monthly = []
    for row in stats.get("monthly", []):
        monthly.append(
            {
                key: row[key]
                for key in (
                    "month",
                    "commits",
                    "prsCreated",
                    "prsMerged",
                    "issuesCreated",
                    "issuesClosed",
                    "partial",
                )
            }
        )
    monthly.sort(key=lambda row: row["month"])
    return {
        "owner": stats["owner"],
        "scope": "public",
        "timezone": stats["timezone"],
        "publicRepositories": public_repository_count,
        "archivedPublicRepositories": stats["archivedPublicRepositories"],
        "monthly": monthly,
    }


def canonical_openclaw_runtime(runtime):
    if runtime is None:
        return None
    if runtime.get("scope") != "domain-agents":
        raise ValueError("OpenClaw runtime input must be limited to domain-agents")

    agents = []
    for row in runtime.get("agents", []):
        agent_id = row.get("id")
        session_count = row.get("sessionCount")
        models = row.get("models", [])
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("OpenClaw runtime agent id is invalid")
        if not isinstance(session_count, int) or session_count < 0:
            raise ValueError("OpenClaw runtime sessionCount is invalid")
        if not isinstance(models, list) or any(
            not isinstance(model, str) or not model for model in models
        ):
            raise ValueError("OpenClaw runtime model list is invalid")
        agents.append(
            {"id": agent_id, "sessionCount": session_count, "models": sorted(set(models))}
        )
    agents.sort(key=lambda row: row["id"])

    automations = []
    for row in runtime.get("automations", []):
        required = ("id", "agentId", "name", "status")
        if any(not isinstance(row.get(key), str) or not row.get(key) for key in required):
            raise ValueError("OpenClaw runtime automation is incomplete")
        if row["status"] not in OPENCLAW_AUTOMATION_STATUSES:
            raise ValueError("OpenClaw runtime automation status is invalid")
        automations.append({key: row[key] for key in required})
    automations.sort(key=lambda row: (row["agentId"], row["name"], row["id"]))

    return {
        "scope": "domain-agents",
        "collectedAt": runtime["collectedAt"],
        "agents": agents,
        "automations": automations,
    }


def canonical_repository_operations(operations, public_repositories):
    if operations is None:
        return None
    if operations.get("scope") != "public-nonarchived-owned-repositories":
        raise ValueError("repository operations input must be public/non-archived only")
    owner = operations.get("owner")
    collected_at = operations.get("collectedAt")
    if not isinstance(owner, str) or not owner or not isinstance(collected_at, str) or not collected_at:
        raise ValueError("repository operations owner/collectedAt is invalid")

    public_names = {f"{repo['owner']}/{repo['name']}" for repo in public_repositories}
    repositories = []
    for row in operations.get("repositories", []):
        required = ("name", "fullName", "url", "group", "classificationSource")
        if any(not isinstance(row.get(key), str) or not row.get(key) for key in required):
            raise ValueError("repository operations repository row is incomplete")
        if row["fullName"] not in public_names:
            raise ValueError("repository operations references a non-canonical repository")
        if row["classificationSource"] not in REPOSITORY_CLASSIFICATION_SOURCES:
            raise ValueError("repository operations classification source is invalid")
        item = {key: row[key] for key in required}
        confidence = row.get("classificationConfidence")
        if row["classificationSource"] == "local-model-suggestion":
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise ValueError("local-model repository classification requires numeric confidence")
            confidence = float(confidence)
            if not 0 <= confidence <= 1:
                raise ValueError("repository classification confidence is outside 0..1")
            item["classificationConfidence"] = confidence
        repositories.append(item)
    repositories.sort(key=lambda row: row["fullName"].casefold())

    branches = []
    for row in operations.get("branches", []):
        required = ("repository", "branch", "status", "reason")
        if any(not isinstance(row.get(key), str) or not row.get(key) for key in required):
            raise ValueError("repository operations branch row is incomplete")
        if row["repository"] not in public_names:
            raise ValueError("repository operations branch references a non-canonical repository")
        if row["status"] not in REPOSITORY_OPERATION_STATUSES:
            raise ValueError("repository operations branch status is invalid")
        item = {key: row[key] for key in required}
        for source_key, target_key in (
            ("commit_date", "commitDate"),
            ("first_seen", "firstSeen"),
            ("confirmed_at", "confirmedAt"),
        ):
            value = row.get(source_key)
            if isinstance(value, str) and value:
                item[target_key] = value
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
        "scope": "public-nonarchived-owned-repositories",
        "owner": owner,
        "collectedAt": collected_at,
        "repositories": repositories,
        "branches": branches,
        "summary": summary,
    }


def workflow_state(run):
    status = run.get("status")
    conclusion = run.get("conclusion")
    if status in {"queued", "requested", "waiting", "pending"}:
        return "queued"
    if status == "in_progress":
        return "in_progress"
    if status != "completed":
        raise ValueError(f"unknown workflow status: {status!r}")
    if conclusion == "success":
        return "completed"
    if conclusion in {"neutral", "skipped"}:
        return "skipped"
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion in {"failure", "timed_out", "action_required", "stale"}:
        return "failed"
    raise ValueError(f"unknown completed workflow conclusion: {conclusion!r}")


def workflow_to_work_item(run):
    return {
        "id": run["id"],
        "repositoryId": run["repositoryId"],
        "kind": "workflow_run",
        "number": run["runNumber"],
        "title": run["workflowName"],
        "url": run["url"],
        "state": workflow_state(run),
        "updatedAt": run["updatedAt"],
    }


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _canonical_activity(item, public_ids):
    if item.get("repositoryId") not in public_ids:
        return None
    required = ("id", "repositoryId", "kind", "occurredAt", "url")
    if any(not item.get(key) for key in required):
        raise ValueError("activity payload is incomplete")
    canonical = {key: item[key] for key in required}
    if item.get("summary"):
        canonical["summary"] = item["summary"]
    return canonical


def build_activity(work_items, recent_activity=None, public_ids=None, generated_at=None):
    public_ids = public_ids or {item["repositoryId"] for item in work_items}
    activity_by_id = {}
    for item in work_items:
        event = {
            "id": f"activity:{item['id']}",
            "repositoryId": item["repositoryId"],
            "kind": item["kind"],
            "occurredAt": item["updatedAt"],
            "url": item["url"],
            "summary": item["title"],
        }
        activity_by_id[event["id"]] = event

    for raw in recent_activity or []:
        event = _canonical_activity(raw, public_ids)
        if event is None:
            continue
        current = activity_by_id.get(event["id"])
        if current is None or event["occurredAt"] > current["occurredAt"]:
            activity_by_id[event["id"]] = event

    if generated_at is not None:
        upper_bound = _parse_time(generated_at)
        lower_bound = upper_bound - timedelta(days=ACTIVITY_WINDOW_DAYS)
        activity_by_id = {
            event_id: event
            for event_id, event in activity_by_id.items()
            if lower_bound <= _parse_time(event["occurredAt"]) <= upper_bound
        }

    return sorted(
        activity_by_id.values(),
        key=lambda event: (event["occurredAt"], event["id"]),
        reverse=True,
    )


def build_snapshot(
    repositories,
    work_items,
    workflow_runs,
    activity_items=None,
    stats=None,
    openclaw_runtime=None,
    repository_operations=None,
    generated_at=None,
):
    public_repositories = [
        canonical
        for repository in repositories
        if (canonical := canonical_repository(repository)) is not None
    ]
    public_repositories.sort(key=lambda repo: (repo["owner"].lower(), repo["name"].lower()))
    public_ids = {repository["id"] for repository in public_repositories}

    canonical_items = []
    for item in work_items:
        if item.get("repositoryId") in public_ids:
            canonical_items.append(add_lane(item))
    for run in workflow_runs:
        if run.get("repositoryId") in public_ids:
            canonical_items.append(add_lane(workflow_to_work_item(run)))

    items_by_id = {}
    for item in canonical_items:
        current = items_by_id.get(item["id"])
        if current is None or item["updatedAt"] > current["updatedAt"]:
            items_by_id[item["id"]] = item
    canonical_items = sorted(
        items_by_id.values(),
        key=lambda item: (item["repositoryId"], item["kind"], item["number"]),
    )

    timestamp = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    activity = build_activity(
        canonical_items,
        recent_activity=activity_items,
        public_ids=public_ids,
        generated_at=timestamp,
    )
    snapshot = {
        "schemaVersion": "1.0.0",
        "generatedAt": timestamp,
        "summary": {
            "repositoryCount": len(public_repositories),
            "workItemCount": len(canonical_items),
            "activityCount": len(activity),
        },
        "repositories": public_repositories,
        "workItems": canonical_items,
        "activity": activity,
    }
    if stats is not None:
        snapshot["stats"] = canonical_stats(stats, len(public_repositories))
    if openclaw_runtime is not None:
        snapshot["openclawRuntime"] = canonical_openclaw_runtime(openclaw_runtime)
    if repository_operations is not None:
        snapshot["repositoryOperations"] = canonical_repository_operations(
            repository_operations, public_repositories
        )
    return snapshot


def validate_snapshot(snapshot, schema):
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors[:5])
        raise ValueError(f"dashboard schema validation failed: {details}")

    counts = (
        ("repositoryCount", "repositories"),
        ("workItemCount", "workItems"),
        ("activityCount", "activity"),
    )
    if any(snapshot["summary"][key] != len(snapshot[field]) for key, field in counts):
        raise ValueError("dashboard summary counts diverged from canonical collections")
    repository_ids = {repository["id"] for repository in snapshot["repositories"]}
    if any(
        item["repositoryId"] not in repository_ids
        for field in ("workItems", "activity")
        for item in snapshot[field]
    ):
        raise ValueError("dashboard item references a non-canonical repository")
    if snapshot.get("stats", {}).get("publicRepositories", len(repository_ids)) != len(repository_ids):
        raise ValueError("dashboard stats repository count diverged from canonical repositories")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repositories", required=True)
    parser.add_argument("--work-items", required=True)
    parser.add_argument("--workflow-runs", required=True)
    parser.add_argument("--activity")
    parser.add_argument("--stats")
    parser.add_argument("--openclaw-runtime")
    parser.add_argument("--repository-operations")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        load_json(args.repositories),
        load_json(args.work_items),
        load_json(args.workflow_runs),
        activity_items=load_json(args.activity) if args.activity else None,
        stats=load_json(args.stats) if args.stats else None,
        openclaw_runtime=load_json(args.openclaw_runtime) if args.openclaw_runtime else None,
        repository_operations=(
            load_json(args.repository_operations) if args.repository_operations else None
        ),
    )
    schema = load_json(args.schema)
    validate_snapshot(snapshot, schema)
    atomic_write_json(args.output, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
