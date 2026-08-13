import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, request_json


def normalize_workflow_run(raw, repository):
    if repository.get("visibility") != "public":
        return None
    run_id = raw.get("id")
    run_number = raw.get("run_number")
    workflow_name = raw.get("name")
    status = raw.get("status")
    conclusion = raw.get("conclusion")
    url = raw.get("html_url")
    created_at = raw.get("created_at")
    updated_at = raw.get("updated_at")
    if not isinstance(run_id, int) or run_id < 1:
        raise ValueError("workflow run id is missing")
    if not isinstance(run_number, int) or run_number < 1:
        raise ValueError("workflow run number is missing")
    if not workflow_name or not status or not url or not created_at or not updated_at:
        raise ValueError("workflow run payload is incomplete")
    return {
        "id": f"{repository['id']}:workflow_run:{run_id}",
        "repositoryId": repository["id"],
        "runNumber": run_number,
        "workflowName": workflow_name,
        "status": status,
        "conclusion": conclusion,
        "url": url,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def collect_latest_workflow_runs(repositories, token=None, request_fn=request_json):
    runs = []
    for repository in repositories:
        if repository.get("visibility") != "public":
            continue
        owner = quote(repository["owner"], safe="")
        name = quote(repository["name"], safe="")
        url = f"https://api.github.com/repos/{owner}/{name}/actions/runs?per_page=1"
        payload, _headers = request_fn(url, token)
        raw_runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(raw_runs, list):
            raise GitHubApiError("unexpected workflow runs response shape")
        if not raw_runs:
            continue
        normalized = normalize_workflow_run(raw_runs[0], repository)
        if normalized is not None:
            runs.append(normalized)
    runs.sort(key=lambda run: run["repositoryId"])
    return runs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repositories", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    repositories = json.loads(Path(args.repositories).read_text(encoding="utf-8"))
    runs = collect_latest_workflow_runs(repositories, token=os.getenv("GITHUB_TOKEN"))
    atomic_write_json(args.output, runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
