import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit

from dashboard.collectors.github_api import atomic_write_json, fetch_paginated
from dashboard.collectors.public_links import (
    collect_repository_links,
    enrich_repository_public_links,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "repositories.json"
DEFAULT_PUBLIC_LINKS_CONFIG = (
    Path(__file__).resolve().parents[1] / "config" / "public-links.json"
)
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


def normalize_https_url(value):
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return candidate


def github_pages_url(owner, name):
    host = f"{owner.lower()}.github.io"
    if name.lower() == host:
        return f"https://{host}/"
    return f"https://{host}/{quote(name, safe='')}/"


def infer_public_links(raw, owner, name):
    links = []
    seen = set()

    def append_link(kind, url):
        identity = url.rstrip("/")
        if identity in seen:
            return
        seen.add(identity)
        links.append({"kind": kind, "url": url})

    homepage = normalize_https_url(raw.get("homepage"))
    if homepage:
        append_link("front", homepage)
    if raw.get("has_pages") is True:
        append_link("pages", github_pages_url(owner, name))
    return links


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
    required["publicLinks"] = infer_public_links(raw, owner, name)
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


def load_public_links_config(path=DEFAULT_PUBLIC_LINKS_CONFIG):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--public-links-config", default=str(DEFAULT_PUBLIC_LINKS_CONFIG))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    repositories = collect_repositories(config, token=os.getenv("GITHUB_TOKEN"))
    provider_links, provider_status = collect_repository_links(
        load_public_links_config(args.public_links_config),
        vercel_token=os.getenv("VERCEL_TOKEN"),
        cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID"),
        cloudflare_token=os.getenv("CLOUDFLARE_API_TOKEN"),
    )
    enrich_repository_public_links(repositories, provider_links)
    print(json.dumps({"publicLinkProviders": provider_status}, sort_keys=True))
    atomic_write_json(args.output, repositories)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
