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


def project_fields() -> list[dict[str, Any]]:
    return gh("project", "field-list", PROJECT, "--owner", OWNER, "--limit", "100", "--format", "json")["fields"]


def ensure_status_options() -> None:
    fields = project_fields()
    status = next((field for field in fields if field["name"] == "Status"), None)
    if status is None or "options" not in status:
        raise RuntimeError("Project #3 に単一選択の Status フィールドがありません。")

    options = [
        {key: value for key, value in option.items() if key in {"id", "name", "color", "description"}}
        for option in status["options"]
    ]
    existing_names = {option["name"] for option in options}
    missing = [name for name in STATUS_COLORS if name not in existing_names]
    if missing:
        # Carry existing IDs forward so values on existing items remain intact.
        options.extend(
            {"name": name, "color": STATUS_COLORS[name], "description": ""}
            for name in missing
        )
        gh(
            "api", "graphql", "--input", "-",
            data={
                "query": "mutation($input: UpdateProjectV2FieldInput!) { updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2SingleSelectField { id name } } } }",
                "variables": {"input": {"fieldId": status["id"], "singleSelectOptions": options}},
            },
        )
        print("Status選択肢を追加:", ", ".join(missing))

    updated = next(field for field in project_fields() if field["name"] == "Status")
    available = {option["name"] for option in updated.get("options", [])}
    if not set(STATUS_COLORS).issubset(available):
        raise RuntimeError(f"Status選択肢の確認に失敗: {sorted(available)}")


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
        info = gh("project", "view", PROJECT, "--owner", OWNER, "--format", "json")
        if str(info.get("number", PROJECT)) != PROJECT:
            raise RuntimeError("意図しないProjectへ接続されたため停止しました。")
        print(f"対象Project: {OWNER}/projects/{PROJECT} ({info.get('title', '')})")
        ensure_status_options()
        before = project_items()
        for repo, number, status in WORK:
            url = issue_url(repo, number)
            if url not in before:
                gh("project", "item-add", PROJECT, "--owner", OWNER, "--url", url, "--format", "json")
                print("追加:", url)
            gh("project", "item-edit", PROJECT, "--owner", OWNER, "--url", url,
               "--field", "Status", "--value", status, "--format", "json")
            print(f"  Status={status}: {url}")

        after = project_items()
        missing = [issue_url(repo, number) for repo, number, _ in WORK if issue_url(repo, number) not in after]
        wrong_status = [
            (issue_url(repo, number), status, after[issue_url(repo, number)].get("status"))
            for repo, number, status in WORK
            if issue_url(repo, number) in after and after[issue_url(repo, number)].get("status") != status
        ]
        if missing or wrong_status:
            raise RuntimeError(f"登録後の照合が不一致: missing={missing}; status_mismatch={wrong_status}")
        print(f"完了: {len(WORK)}件をProject #3へ登録しStatusを検証しました。")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("GitHub CLIのProject権限は gh auth refresh -s project で追加できます。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
