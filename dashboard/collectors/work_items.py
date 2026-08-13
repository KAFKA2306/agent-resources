import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

from dashboard.collectors.github_api import atomic_write_json, fetch_paginated


def normalize_work_item(raw, repository):
    if repository.get("visibility") != "public":
        return None
    if raw.get("state") != "open":
        return None
    kind = "pull_request" if "pull_request" in raw else "issue"
    number = raw.get("number")
    title = raw.get("title")
    url = raw.get("html_url")
    updated_at = raw.get("updated_at")
    if not isinstance(number, int) or number < 1 or not title or not url or not updated_at:
        raise ValueError("work item payload is incomplete")
    return {
        "id": f"{repository['id']}:{kind}:{number}",
        "kind": kind,
        "repositoryId": repository["id"],
        "number": number,
        "title": title,
        "url": url,
        "state": "open",
        "updatedAt": updated_at,
    }


def collect_work_items(repositories, token=None, fetcher=fetch_paginated):
    items_by_id = {}
    for repository in repositories:
        if repository.get("visibility") != "public":
            continue
        owner = quote(repository["owner"], safe="")
        name = quote(repository["name"], safe="")
        url = (
            f"https://api.github.com/repos/{owner}/{name}/issues"
            "?state=open&per_page=100&sort=updated&direction=desc"
        )
        for raw in fetcher(url, token=token):
            item = normalize_work_item(raw, repository)
            if item is None:
                continue
            current = items_by_id.get(item["id"])
            if current is None or item["updatedAt"] > current["updatedAt"]:
                items_by_id[item["id"]] = item
    return sorted(
        items_by_id.values(),
        key=lambda item: (item["repositoryId"], item["kind"], item["number"]),
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repositories", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    repositories = json.loads(Path(args.repositories).read_text(encoding="utf-8"))
    items = collect_work_items(repositories, token=os.getenv("GITHUB_TOKEN"))
    atomic_write_json(args.output, items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
