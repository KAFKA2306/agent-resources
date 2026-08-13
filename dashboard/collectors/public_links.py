import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

VERCEL_API = "https://api.vercel.com"
DEFAULT_TIMEOUT = 20


class PublicLinksError(RuntimeError):
    pass


def _iso_z(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def request_json(url, token, timeout=DEFAULT_TIMEOUT):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "KAFKA2306-agent-resources-dashboard",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PublicLinksError(
            f"request failed for {urlparse(url).path}: {type(exc).__name__}"
        ) from exc


def _https_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("public link must be an absolute https URL")
    return value.rstrip("/")


def normalize_profile(raw):
    required = ("id", "label", "url", "category")
    if any(not raw.get(key) for key in required):
        raise ValueError("public profile entry is incomplete")
    return {
        "id": str(raw["id"]),
        "label": str(raw["label"]),
        "url": _https_url(str(raw["url"])),
        "category": str(raw["category"]),
        "provider": str(raw.get("provider") or "profile"),
        "status": "configured",
    }


def choose_canonical_domain(domains):
    candidates = []
    for raw in domains:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").lower().rstrip(".")
        if not name or raw.get("redirect"):
            continue
        if raw.get("verified") is False:
            continue
        candidates.append(name)
    unique = sorted(
        set(candidates),
        key=lambda name: (
            name.endswith("-kafka2306s-projects.vercel.app"),
            "-git-" in name,
            len(name),
            name,
        ),
    )
    return unique[0] if unique else None


def _vercel_projects_url(team_id, limit):
    return f"{VERCEL_API}/v9/projects?{urlencode({'teamId': team_id, 'limit': limit})}"


def _vercel_deployments_url(team_id, project_id):
    return f"{VERCEL_API}/v6/deployments?{urlencode({'projectId': project_id, 'target': 'production', 'limit': 1, 'teamId': team_id})}"


def _vercel_domains_url(team_id, project_id):
    project = quote(project_id, safe="")
    query = urlencode(
        {
            "production": "true",
            "verified": "true",
            "redirects": "false",
            "limit": 100,
            "teamId": team_id,
        }
    )
    return f"{VERCEL_API}/v9/projects/{project}/domains?{query}"


def collect_vercel_links(config, token, request_fn=request_json):
    if not config:
        return [], {"status": "disabled", "discovered": 0, "ready": 0, "failed": 0}
    team_id = config.get("teamId")
    if not team_id:
        raise ValueError("vercel.teamId is required")
    if not token:
        return [], {"status": "unavailable", "discovered": 0, "ready": 0, "failed": 0}

    limit = int(config.get("maxProjects", 100))
    if limit < 1 or limit > 100:
        raise ValueError("vercel.maxProjects must be between 1 and 100")

    try:
        payload = request_fn(_vercel_projects_url(team_id, limit), token)
    except PublicLinksError:
        return [], {"status": "error", "discovered": 0, "ready": 0, "failed": 1}

    projects = payload.get("projects") if isinstance(payload, dict) else None
    if not isinstance(projects, list):
        return [], {"status": "error", "discovered": 0, "ready": 0, "failed": 1}

    links = []
    failed = 0
    ready = 0
    for project in projects:
        if not isinstance(project, dict):
            failed += 1
            continue
        project_id = project.get("id")
        name = project.get("name")
        if not project_id or not name:
            failed += 1
            continue
        try:
            deployment_payload = request_fn(
                _vercel_deployments_url(team_id, project_id), token
            )
            deployments = (
                deployment_payload.get("deployments")
                if isinstance(deployment_payload, dict)
                else None
            )
            if not isinstance(deployments, list):
                raise PublicLinksError("unexpected deployment payload")
            if not deployments:
                continue
            deployment = deployments[0]
            state = deployment.get("state") or deployment.get("readyState")
            if state != "READY":
                continue

            domain_payload = request_fn(_vercel_domains_url(team_id, project_id), token)
            domains = domain_payload.get("domains") if isinstance(domain_payload, dict) else None
            if not isinstance(domains, list):
                raise PublicLinksError("unexpected domains payload")
            domain = choose_canonical_domain(domains)
            if domain:
                url = f"https://{domain}"
            else:
                deployment_url = str(deployment.get("url") or "").strip()
                if not deployment_url:
                    raise PublicLinksError("READY deployment has no public URL")
                url = _https_url(f"https://{deployment_url}")
            links.append(
                {
                    "id": f"vercel:{project_id}",
                    "label": str(name),
                    "url": url,
                    "category": "app",
                    "provider": "vercel",
                    "status": "ready",
                }
            )
            ready += 1
        except (PublicLinksError, ValueError):
            failed += 1
            continue

    status = "ok" if failed == 0 else ("partial" if links else "error")
    return links, {
        "status": status,
        "discovered": len(projects),
        "ready": ready,
        "failed": failed,
    }


def collect_public_links(config, token=None, now=None, request_fn=request_json):
    profiles = config.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("profiles must be a list")

    links = [normalize_profile(raw) for raw in profiles]
    vercel_links, vercel_status = collect_vercel_links(
        config.get("vercel"), token=token, request_fn=request_fn
    )
    links.extend(vercel_links)

    deduped = {}
    ids = set()
    for link in links:
        if link["id"] in ids:
            raise ValueError(f"duplicate public link id: {link['id']}")
        ids.add(link["id"])
        deduped.setdefault(link["url"], link)

    ordered = sorted(
        deduped.values(),
        key=lambda link: (
            link["category"],
            link["provider"],
            link["label"].lower(),
            link["url"],
        ),
    )
    timestamp = _iso_z(now or datetime.now(timezone.utc))
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": timestamp,
        "sourceStatus": {
            "profiles": {"status": "ok", "configured": len(profiles)},
            "vercel": vercel_status,
        },
        "links": ordered,
    }


def atomic_write_json(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(destination)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="dashboard/config/public-links.json")
    parser.add_argument("--output", default="docs/dashboard/public-links.json")
    args = parser.parse_args(argv)

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    payload = collect_public_links(config, token=os.getenv("VERCEL_TOKEN"))
    atomic_write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
