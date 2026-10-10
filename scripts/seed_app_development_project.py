#!/usr/bin/env python3
"""Idempotently seed GitHub Project #3 from existing application issues.

Requirements: GitHub CLI (gh) authenticated with the project scope.
No new issues, pull requests, or projects are created.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

OWNER = "KAFKA2306"
PROJECT = "3"
WORK = (
    ("image2outfit", 859, "Ready"),
    ("cast_event_cal", 329, "Ready"),
    ("unity-mcp", 89, "Ready"),
    ("vlog", 136, "Ready"),
    ("agent-resources", 530, "Blocked"),
    ("nlm", 44, "Blocked"),
    ("yt3", 218, "Ready"),
    ("game-library-dashboard", 3, "Backlog"),
    ("bodogenomikata2", 33, "Backlog"),
)
STATUS_COLORS = {
    "Backlog": "GRAY",
    "Ready": "BLUE",
    "In Progress": "YELLOW",
    "Blocked": "RED",
    "Done": "GREEN",
}


def gh(*args: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    command = ["gh", *args]
    try:
        process = subprocess.run(
            command,
            text=True,
            input=json.dumps(data) if data is not None else None,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI (gh) がありません: https://cli.github.com/") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"{' '.join(command)} failed: {details}") from exc
    return json.loads(process.stdout) if process.stdout.strip() else {}


def issue_url(repo: str, number: int) -> str:
    return f"https://github.com/{OWNER}/{repo}/issues/{number}"


def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    result = gh("api", "graphql", "--input", "-", data={"query": query, "variables": variables})
    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors: " + json.dumps(result["errors"], ensure_ascii=False))
    return result.get("data") or {}


def project_status() -> tuple[str, dict[str, Any]]:
    data = graphql(
        """query($owner: String!, $number: Int!) {
          user(login:$owner) { projectV2(number:$number) {
            id number title fields(first:100) { nodes {
              ... on ProjectV2SingleSelectField { id name options { id name color description } }
            } }
          } }
        }""",
        {"owner": OWNER, "number": int(PROJECT)},
    )
    project = (data.get("user") or {}).get("projectV2")
    if not project or str(project.get("number")) != PROJECT:
        raise RuntimeError("Project #3を読み取れません。認証とproject権限を確認してください。")
    status = next((x for x in project["fields"]["nodes"] if x and x.get("name") == "Status"), None)
    if not status or "options" not in status:
        raise RuntimeError("既存の単一選択Statusがありません。無断で別のFieldを作成しません。")
    return project["id"], status


def ensure_status_options(status: dict[str, Any]) -> dict[str, str]:
    original = status["options"]
    previous = {x["name"]: x["id"] for x in original}
    missing = [name for name in STATUS_COLORS if name not in previous]
    if not missing:
        return previous

    # updateProjectV2Field replaces all options. Preserve every ID, color and description.
    options = [
        {"id": x["id"], "name": x["name"], "description": x["description"], "color": x["color"]}
        for x in original
    ]
    options.extend(
        {"name": name, "description": "", "color": STATUS_COLORS[name]} for name in missing
    )
    graphql(
        """mutation($input: UpdateProjectV2FieldInput!) {
          updateProjectV2Field(input:$input) { projectV2Field {
            ... on ProjectV2SingleSelectField { id name }
          } }
        }""",
        {"input": {"fieldId": status["id"], "singleSelectOptions": options}},
    )
    _, updated = project_status()
    available = {x["name"]: x["id"] for x in updated["options"]}
    if not set(STATUS_COLORS).issubset(available):
        raise RuntimeError("不足していたStatusの追加を確認できません。")
    if any(available.get(name) != ident for name, ident in previous.items()):
        raise RuntimeError("既存のStatus option IDに変更を検出したため停止します。")
    print("Status選択肢追加:", ", ".join(missing))
    return available


def project_items() -> dict[str, dict[str, Any]]:
    result = gh("project", "item-list", PROJECT, "--owner", OWNER, "--limit", "1000", "--format", "json")
    items = result.get("items", [])
    by_url = {}
    for item in items:
        url = item.get("url") or (item.get("content") or {}).get("url")
        if url:
            by_url[url] = item
    return by_url


def main() -> int:
    try:
        project_id, status_field = project_status()
        print(f"対象: https://github.com/users/{OWNER}/projects/{PROJECT}")
        options = ensure_status_options(status_field)
        before = project_items()
        for repo, number, status in WORK:
            url = issue_url(repo, number)
            item = before.get(url)
            if item is None:
                item = gh("project", "item-add", PROJECT, "--owner", OWNER, "--url", url, "--format", "json")
                print("追加:", url)
            if not item.get("id"):
                raise RuntimeError(f"Project item IDを取得できません: {url}")
            if item.get("status") == status:
                print(f"維持: {status} {url}")
                continue
            gh("project", "item-edit", "--id", item["id"], "--project-id", project_id,
               "--field-id", status_field["id"], "--single-select-option-id", options[status], "--format", "json")
            print(f"更新: {status} {url}")

        after = project_items()
        problems = [
            (issue_url(repo, number), value, after.get(issue_url(repo, number), {}).get("status"))
            for repo, number, value in WORK
            if after.get(issue_url(repo, number), {}).get("status") != value
        ]
        if problems:
            raise RuntimeError(f"read-back不一致: {problems}")
        print(f"SUCCESS: {len(WORK)}件の登録とStatusをGitHub Projects #3で照合済み")
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("必要な環境: gh auth status / gh auth refresh -s project", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
