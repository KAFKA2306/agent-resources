from collections import Counter
from urllib.parse import urlencode

from dashboard.collectors.github_api import GitHubApiError, fetch_paginated, request_json

API_ROOT = "https://api.github.com"


def _runner_family(labels):
    normalized = [label.lower() for label in labels if isinstance(label, str)]
    if "self-hosted" in normalized:
        return "self-hosted"
    if any(label.startswith("ubuntu") for label in normalized):
        return "linux"
    if any(label.startswith("windows") for label in normalized):
        return "windows"
    if any(label.startswith("macos") for label in normalized):
        return "macos"
    return "unknown"


def collect_workflow_job_usage(
    owner,
    repo,
    workflow_id,
    start,
    end,
    token,
    request_fn=request_json,
    paginate_fn=fetch_paginated,
):
    query = urlencode({"created": f"{start.isoformat()}..{end.isoformat()}", "per_page": 100})
    runs_url = f"{API_ROOT}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?{query}"
    runs = paginate_fn(runs_url, token=token, request_fn=request_fn, item_key="workflow_runs")

    run_ids = []
    for run in runs:
        run_id = run.get("id") if isinstance(run, dict) else None
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
            raise GitHubApiError("workflow run is missing a valid id")
        run_ids.append(run_id)

    family_counts = Counter()
    runner_names = Counter()
    label_counts = Counter()
    job_count = 0

    for run_id in run_ids:
        jobs_url = f"{API_ROOT}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=100"
        jobs = paginate_fn(jobs_url, token=token, request_fn=request_fn, item_key="jobs")
        for job in jobs:
            if not isinstance(job, dict):
                continue
            labels = job.get("labels")
            if not isinstance(labels, list):
                labels = []
            family_counts[_runner_family(labels)] += 1
            for label in labels:
                if isinstance(label, str) and label:
                    label_counts[label] += 1
            runner_name = job.get("runner_name")
            if isinstance(runner_name, str) and runner_name:
                runner_names[runner_name] += 1
            job_count += 1

    def breakdown(counter):
        return [
            {"name": name, "jobs": jobs}
            for name, jobs in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
        ]

    return {
        "run_count": len(run_ids),
        "job_count": job_count,
        "jobs_by_runner_family": breakdown(family_counts),
        "jobs_by_runner_name": breakdown(runner_names),
        "jobs_by_runner_label": breakdown(label_counts),
        "billing_minutes_estimated": None,
        "billing_minutes_source": "not_estimated_from_jobs",
    }
