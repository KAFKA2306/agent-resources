from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dashboard.collectors.github_api import API_VERSION, atomic_write_json, fetch_paginated, request_json
from dashboard.collectors.repositories import ZONE_TOPIC_PREFIX, normalize_group_fragment

SCHEMA_VERSION = 1
DEFAULT_OWNER = "KAFKA2306"
DEFAULT_MIN_AGE_DAYS = 30
DEFAULT_CONFIRM_HOURS = 24
DEFAULT_MAX_DELETES = 10
PROTECTED_BRANCH_NAMES = {"main", "master", "develop", "development", "production", "gh-pages"}
PROTECTED_BRANCH_PREFIXES = ("release/", "production/", "hotfix/")


class RepositoryMaintenanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BranchObservation:
    repository: str
    branch: str
    tip_sha: str
    status: str
    reason: str
    commit_date: str | None = None
    first_seen: str | None = None
    confirmed_at: str | None = None


def resolve_github_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    gh = shutil.which("gh")
    if gh is None:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip() if result.returncode == 0 else ""
    return token or None


class GitHubClient:
    def __init__(self, token: str | None):
        self.token = token

    def get(self, url: str) -> Any:
        return request_json(url, token=self.token)[0]

    def list(self, url: str) -> list[dict[str, Any]]:
        return fetch_paginated(url, token=self.token)

    def delete_ref(self, owner: str, repo: str, branch: str) -> None:
        if not self.token:
            raise RepositoryMaintenanceError("authenticated GitHub token is required for branch deletion")
        encoded_branch = quote(branch, safe="")
        url = (
            f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
            f"/git/refs/heads/{encoded_branch}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "KAFKA2306-agent-resources-maintenance",
            "Authorization": f"Bearer {self.token}",
        }
        request = Request(url, headers=headers, method="DELETE")
        try:
            with urlopen(request, timeout=30) as response:
                if response.status not in {204, 200}:
                    raise RepositoryMaintenanceError(
                        f"unexpected GitHub delete status {response.status}: {owner}/{repo}:{branch}"
                    )
        except HTTPError as exc:
            raise RepositoryMaintenanceError(
                f"GitHub branch delete failed with HTTP {exc.code}: {owner}/{repo}:{branch}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RepositoryMaintenanceError(
                f"GitHub branch delete transport failure: {owner}/{repo}:{branch}: {type(exc).__name__}"
            ) from exc


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _classification(raw: dict[str, Any]) -> tuple[str, str]:
    topics = raw.get("topics") or []
    zone_topics = sorted(
        topic[len(ZONE_TOPIC_PREFIX) :]
        for topic in topics
        if isinstance(topic, str)
        and topic.startswith(ZONE_TOPIC_PREFIX)
        and topic[len(ZONE_TOPIC_PREFIX) :]
    )
    if zone_topics:
        return normalize_group_fragment(zone_topics[0]), "agent-zone-topic"
    return "unclassified", "unclassified"


def collect_operations_inventory(
    owner: str,
    *,
    token: str | None = None,
    fetcher: Callable[..., list[dict[str, Any]]] = fetch_paginated,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    owner_q = quote(owner, safe="")
    url = f"https://api.github.com/users/{owner_q}/repos?per_page=100&type=owner&sort=updated"
    rows = []
    for raw in fetcher(url, token=token):
        if raw.get("owner", {}).get("login") != owner:
            continue
        if raw.get("private") is True or raw.get("visibility") != "public" or raw.get("archived") is True:
            continue
        name = raw.get("name")
        node_id = raw.get("node_id")
        default_branch = raw.get("default_branch")
        html_url = raw.get("html_url")
        updated_at = raw.get("updated_at")
        if not all(
            isinstance(value, str) and value
            for value in (name, node_id, default_branch, html_url, updated_at)
        ):
            raise RepositoryMaintenanceError(f"repository payload incomplete: {name!r}")
        group, source = _classification(raw)
        description = raw.get("description")
        language = raw.get("language")
        rows.append(
            {
                "id": node_id,
                "name": name,
                "fullName": f"{owner}/{name}",
                "url": html_url,
                "defaultBranch": default_branch,
                "group": group,
                "classificationSource": source,
                "description": description if isinstance(description, str) else "",
                "language": language if isinstance(language, str) else "",
                "fork": raw.get("fork") is True,
                "topics": sorted(
                    topic for topic in (raw.get("topics") or []) if isinstance(topic, str)
                ),
                "updatedAt": updated_at,
            }
        )
    rows.sort(key=lambda repo: repo["name"].casefold())
    now = collected_at or utc_now()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "scope": "public-nonarchived-owned-repositories",
        "owner": owner,
        "collectedAt": iso_utc(now),
        "repositories": rows,
        "summary": {
            "repositoryCount": len(rows),
            "classifiedCount": sum(
                row["classificationSource"] != "unclassified" for row in rows
            ),
            "unclassifiedCount": sum(
                row["classificationSource"] == "unclassified" for row in rows
            ),
        },
    }


def _protected_name(branch: str) -> bool:
    lowered = branch.casefold()
    return lowered in PROTECTED_BRANCH_NAMES or any(
        lowered.startswith(prefix) for prefix in PROTECTED_BRANCH_PREFIXES
    )


def _commit_date(commit_payload: dict[str, Any]) -> str | None:
    commit = commit_payload.get("commit") or {}
    for identity in ("committer", "author"):
        date = (commit.get(identity) or {}).get("date")
        if isinstance(date, str) and date:
            return date
    return None


def _candidate_key(full_name: str, branch: str) -> str:
    return f"{full_name}:{branch}"


def load_candidate_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "candidates": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryMaintenanceError(f"invalid branch candidate state: {path}") from exc
    if payload.get("schemaVersion") != SCHEMA_VERSION or not isinstance(
        payload.get("candidates"), dict
    ):
        raise RepositoryMaintenanceError("branch candidate state schema mismatch")
    return payload


def _active_pull_requests(client: GitHubClient, owner: str, repo: str, branch: str) -> bool:
    head = quote(f"{owner}:{branch}", safe="")
    url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls"
        f"?state=open&head={head}&per_page=1"
    )
    payload = client.get(url)
    if not isinstance(payload, list):
        raise RepositoryMaintenanceError("unexpected pull request response shape")
    return bool(payload)


def _is_merged_into_default(
    client: GitHubClient, owner: str, repo: str, default_branch: str, branch: str
) -> bool:
    base = quote(default_branch, safe="")
    head = quote(branch, safe="")
    url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/compare/"
        f"{base}...{head}"
    )
    payload = client.get(url)
    ahead_by = payload.get("ahead_by") if isinstance(payload, dict) else None
    if not isinstance(ahead_by, int):
        raise RepositoryMaintenanceError("unexpected compare response shape")
    return ahead_by == 0


def _branch_detail(client: GitHubClient, owner: str, repo: str, branch: str) -> dict[str, Any]:
    encoded_branch = quote(branch, safe="")
    url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
        f"/branches/{encoded_branch}"
    )
    payload = client.get(url)
    if not isinstance(payload, dict):
        raise RepositoryMaintenanceError("unexpected branch detail response shape")
    return payload


def _delete_after_readback(
    client: GitHubClient,
    owner: str,
    repo: str,
    default_branch: str,
    branch: str,
    expected_tip: str,
) -> tuple[bool, str]:
    current = _branch_detail(client, owner, repo, branch)
    current_tip = (current.get("commit") or {}).get("sha")
    if current_tip != expected_tip:
        return False, "branch_tip_changed_since_scan"
    if current.get("protected") is True or _protected_name(branch):
        return False, "branch_became_protected"
    if _active_pull_requests(client, owner, repo, branch):
        return False, "active_pull_request_on_readback"
    if not _is_merged_into_default(client, owner, repo, default_branch, branch):
        return False, "not_merged_on_readback"
    client.delete_ref(owner, repo, branch)
    return True, "confirmed_stale_merged_branch"


def scan_branch_hygiene(
    inventory: dict[str, Any],
    state: dict[str, Any],
    client: GitHubClient,
    *,
    now: datetime | None = None,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    confirm_hours: int = DEFAULT_CONFIRM_HOURS,
    apply: bool = False,
    max_deletes: int = DEFAULT_MAX_DELETES,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if inventory.get("scope") != "public-nonarchived-owned-repositories":
        raise RepositoryMaintenanceError(
            "branch hygiene accepts only the sanitized public inventory scope"
        )
    owner = inventory.get("owner")
    if not isinstance(owner, str) or not owner:
        raise RepositoryMaintenanceError("inventory owner missing")
    if apply and not client.token:
        raise RepositoryMaintenanceError(
            "branch --apply requires GITHUB_TOKEN/GH_TOKEN or an authenticated gh CLI"
        )
    now = now or utc_now()
    age_cutoff = now - timedelta(days=min_age_days)
    confirm_delta = timedelta(hours=confirm_hours)
    previous = state.get("candidates", {})
    next_candidates: dict[str, Any] = {}
    observations: list[dict[str, Any]] = []
    deletes = 0

    for repo_row in inventory.get("repositories", []):
        repo = repo_row.get("name")
        default_branch = repo_row.get("defaultBranch")
        full_name = repo_row.get("fullName")
        if not all(
            isinstance(value, str) and value for value in (repo, default_branch, full_name)
        ):
            continue
        branches_url = (
            f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
            "/branches?per_page=100"
        )
        for branch_row in client.list(branches_url):
            branch = branch_row.get("name")
            tip_sha = (branch_row.get("commit") or {}).get("sha")
            if not isinstance(branch, str) or not isinstance(tip_sha, str):
                continue
            if branch == default_branch:
                continue
            if branch_row.get("protected") is True or _protected_name(branch):
                continue

            key = _candidate_key(full_name, branch)
            if _active_pull_requests(client, owner, repo, branch):
                observations.append(
                    BranchObservation(
                        full_name, branch, tip_sha, "blocked", "active_pull_request"
                    ).__dict__
                )
                continue
            if not _is_merged_into_default(client, owner, repo, default_branch, branch):
                observations.append(
                    BranchObservation(
                        full_name, branch, tip_sha, "blocked", "not_merged_into_default"
                    ).__dict__
                )
                continue

            commit_url = (
                f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
                f"/commits/{tip_sha}"
            )
            commit_payload = client.get(commit_url)
            commit_date = _commit_date(commit_payload if isinstance(commit_payload, dict) else {})
            if commit_date is None:
                observations.append(
                    BranchObservation(
                        full_name, branch, tip_sha, "blocked", "commit_date_missing"
                    ).__dict__
                )
                continue
            if parse_utc(commit_date) > age_cutoff:
                continue

            prior = previous.get(key)
            same_tip = isinstance(prior, dict) and prior.get("tipSha") == tip_sha
            first_seen = prior.get("firstSeen") if same_tip else iso_utc(now)
            consecutive = int(prior.get("consecutiveScans", 0)) + 1 if same_tip else 1
            confirmed = (
                same_tip
                and consecutive >= 2
                and now - parse_utc(first_seen) >= confirm_delta
            )
            status = "confirmed" if confirmed else "candidate"
            confirmed_at = iso_utc(now) if confirmed else None

            entry = {
                "repository": full_name,
                "branch": branch,
                "tipSha": tip_sha,
                "firstSeen": first_seen,
                "lastSeen": iso_utc(now),
                "consecutiveScans": consecutive,
                "commitDate": commit_date,
            }
            next_candidates[key] = entry

            if confirmed and apply:
                if deletes >= max_deletes:
                    status = "blocked"
                    reason = "delete_budget_exhausted"
                else:
                    try:
                        deleted, reason = _delete_after_readback(
                            client,
                            owner,
                            repo,
                            default_branch,
                            branch,
                            tip_sha,
                        )
                    except RepositoryMaintenanceError as exc:
                        deleted = False
                        reason = f"delete_failed:{str(exc).split(':', 1)[0]}"
                    if deleted:
                        deletes += 1
                        status = "deleted"
                        next_candidates.pop(key, None)
                    else:
                        status = "blocked"
            else:
                reason = "stable_stale_merged_branch" if confirmed else "awaiting_second_scan"

            observations.append(
                BranchObservation(
                    full_name,
                    branch,
                    tip_sha,
                    status,
                    reason,
                    commit_date=commit_date,
                    first_seen=first_seen,
                    confirmed_at=confirmed_at,
                ).__dict__
            )

    observations.sort(
        key=lambda row: (row["repository"].casefold(), row["branch"].casefold())
    )
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "scope": inventory["scope"],
        "owner": owner,
        "collectedAt": iso_utc(now),
        "apply": apply,
        "policy": {
            "minAgeDays": min_age_days,
            "confirmHours": confirm_hours,
            "maxDeletesPerRun": max_deletes,
            "requiresMergedIntoDefault": True,
            "requiresNoOpenPullRequest": True,
            "requiresUnprotectedBranch": True,
            "requiresSameTipOnDeleteReadback": True,
        },
        "branches": observations,
        "summary": {
            "candidateCount": sum(row["status"] == "candidate" for row in observations),
            "confirmedCount": sum(row["status"] == "confirmed" for row in observations),
            "deletedCount": sum(row["status"] == "deleted" for row in observations),
            "blockedCount": sum(row["status"] == "blocked" for row in observations),
        },
    }
    next_state = {
        "schemaVersion": SCHEMA_VERSION,
        "updatedAt": iso_utc(now),
        "candidates": next_candidates,
    }
    return report, next_state


def default_state_dir() -> Path:
    configured = os.environ.get("KAFKA_REPO_OPS_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    return (base / "kafka-repository-ops").resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--owner", default=DEFAULT_OWNER)
    inventory_parser.add_argument("--output", required=True)

    branches_parser = subparsers.add_parser("branches")
    branches_parser.add_argument("--inventory", required=True)
    branches_parser.add_argument("--output", required=True)
    branches_parser.add_argument("--state")
    branches_parser.add_argument("--apply", action="store_true")
    branches_parser.add_argument("--min-age-days", type=int, default=DEFAULT_MIN_AGE_DAYS)
    branches_parser.add_argument("--confirm-hours", type=int, default=DEFAULT_CONFIRM_HOURS)
    branches_parser.add_argument("--max-deletes", type=int, default=DEFAULT_MAX_DELETES)

    args = parser.parse_args(argv)
    token = resolve_github_token()
    try:
        if args.command == "inventory":
            inventory = collect_operations_inventory(args.owner, token=token)
            atomic_write_json(args.output, inventory)
            print(json.dumps(inventory["summary"], sort_keys=True))
            return 0

        inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
        state_file = (
            Path(args.state).expanduser().resolve()
            if args.state
            else default_state_dir() / "branch-candidates.json"
        )
        state = load_candidate_state(state_file)
        report, next_state = scan_branch_hygiene(
            inventory,
            state,
            GitHubClient(token),
            min_age_days=args.min_age_days,
            confirm_hours=args.confirm_hours,
            apply=args.apply,
            max_deletes=args.max_deletes,
        )
        atomic_write_json(args.output, report)
        atomic_write_json(state_file, next_state)
        print(json.dumps(report["summary"], sort_keys=True))
        return 0
    except (RepositoryMaintenanceError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
