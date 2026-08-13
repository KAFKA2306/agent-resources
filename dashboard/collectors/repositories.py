import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from dashboard.collectors.github_api import atomic_write_json, fetch_paginated

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "repositories.json"
ZONE_TOPIC_PREFIX = "agent-zone-"
UNCLASSIFIED_GROUP = "unclassified"
ALLOWED_CONFIG_KEYS = {"owner"}


def validate_config(config):
    if set(config) != ALLOWED_CONFIG_KEYS:
        raise ValueError("repository config must contain only owner")
    if not isinstance(config.get("owner"), str) or not config["owner"].strip():
        raise ValueError("owner must be a non-empty string")
    return config


def load_config(path=DEFAULT_CONFIG):
    with Path(path).open(encoding="utf-8") as handle:
        return validate_config(json.load(handle))


def normalize_group_fragment(value):
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "other"


def infer_group(raw):
    topics = raw.get("topics") or []
    if not isinstance(topics, list):
        raise ValueError("repository topics must be a list")
    zone_topics = sorted(
        topic[len(ZONE_TOPIC_PREFIX) :]
        for topic in topics
        if isinstance(topic, str)
        and topic.startswith(ZONE_TOPIC_PREFIX)
        and topic[len(ZONE_TOPIC_PREFIX) :]
    )
    if zone_topics:
        return normalize_group_fragment(zone_topics[0])
    return UNCLASSIFIED_GROUP


def normalize_repository(raw, config):
    owner = raw.get("owner", {}).get("login")
    name = raw.get("name")
    if owner != config["owner"]:
        return None
    if raw.get("visibility") != "public" or raw.get("private") is True:
        return None
    archived = raw.get("archived")
    if not isinstance(archived, bool):
        raise ValueError("repository archived flag is missing")
    if archived:
        return None

    required = {
        "id": raw.get("node_id"),
        "owner": owner,
        "name": name,
        "url": raw.get("html_url"),
        "visibility": raw.get("visibility"),
        "archived": archived,
        "updatedAt": raw.get("updated_at"),
    }
    for key in ("id", "owner", "name", "url", "visibility", "updatedAt"):
        if not required[key]:
            raise ValueError(f"repository payload is missing {key}: {name!r}")
    required["group"] = infer_group(raw)
    return required


def collect_repositories(config, token=None, fetcher=fetch_paginated):
    config = validate_config(config)
    owner = quote(config["owner"], safe="")
    url = f"https://api.github.com/users/{owner}/repos?per_page=100&type=owner&sort=updated"
    raw_repositories = fetcher(url, token=token)
    repositories = []
    for raw in raw_repositories:
        normalized = normalize_repository(raw, config)
        if normalized is not None:
            repositories.append(normalized)
    repositories.sort(key=lambda repo: (repo["owner"].lower(), repo["name"].lower()))
    return repositories


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    repositories = collect_repositories(config, token=os.getenv("GITHUB_TOKEN"))
    atomic_write_json(args.output, repositories)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
