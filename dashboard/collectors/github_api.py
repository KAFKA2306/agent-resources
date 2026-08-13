import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_VERSION = "2026-03-10"


class GitHubApiError(RuntimeError):
    pass


def request_json(url, token=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "KAFKA2306-agent-resources-dashboard",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, dict(response.headers.items())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubApiError(f"GitHub API request failed: {url}") from exc


def next_link(headers):
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None
    for part in link.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        start = section.find("<")
        end = section.find(">", start + 1)
        if start >= 0 and end > start:
            return section[start + 1 : end]
    return None


def fetch_paginated(url, token=None, request_fn=request_json, item_key=None):
    items = []
    seen = set()
    current = url
    while current:
        if current in seen:
            raise GitHubApiError("pagination cycle detected")
        seen.add(current)
        payload, headers = request_fn(current, token)
        page_items = payload.get(item_key) if item_key else payload
        if not isinstance(page_items, list):
            raise GitHubApiError("unexpected GitHub API response shape")
        items.extend(page_items)
        current = next_link(headers)
    return items


def atomic_write_json(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
