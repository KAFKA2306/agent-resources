import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from dashboard.collectors.github_api import atomic_write_json
from dashboard.domain.lanes import add_lane


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_repository(repository):
    if repository.get("visibility") != "public":
        return None
    return {
        key: repository[key]
        for key in ("id", "owner", "name", "url", "group", "visibility", "updatedAt")
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


def build_activity(work_items):
    activity = []
    for item in work_items:
        activity.append(
            {
                "id": f"activity:{item['id']}",
                "repositoryId": item["repositoryId"],
                "kind": item["kind"],
                "occurredAt": item["updatedAt"],
                "url": item["url"],
                "summary": item["title"],
            }
        )
    return sorted(activity, key=lambda event: (event["occurredAt"], event["id"]), reverse=True)


def build_snapshot(repositories, work_items, workflow_runs, generated_at=None):
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

    activity = build_activity(canonical_items)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
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


def validate_snapshot(snapshot, schema):
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors[:5])
        raise ValueError(f"dashboard schema validation failed: {details}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repositories", required=True)
    parser.add_argument("--work-items", required=True)
    parser.add_argument("--workflow-runs", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        load_json(args.repositories),
        load_json(args.work_items),
        load_json(args.workflow_runs),
    )
    schema = load_json(args.schema)
    validate_snapshot(snapshot, schema)
    atomic_write_json(args.output, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
