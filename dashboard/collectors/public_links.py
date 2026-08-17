import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

VERCEL_API = "https://api.vercel.com"
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT = 20


class PublicLinksError(RuntimeError):
    pass


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


def choose_canonical_domain(domains):
    candidates = []
    for raw in domains:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").lower().rstrip(".")
        if not name or raw.get("redirect") or raw.get("verified") is False:
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


def normalize_configured_link(raw):
    required = ("owner", "name", "url", "provider")
    if any(not raw.get(key) for key in required):
        raise ValueError("repository public link entry is incomplete")
    return {
        "kind": "front",
        "url": _https_url(str(raw["url"])),
        "provider": str(raw["provider"]),
        "repository": {"owner": str(raw["owner"]), "name": str(raw["name"])},
    }


def _repository_from_vercel_deployment(deployment):
    meta = deployment.get("meta")
    if not isinstance(meta, dict):
        return None
    owner = meta.get("githubCommitOrg") or meta.get("githubOrg")
    name = meta.get("githubCommitRepo") or meta.get("githubRepo")
    if not owner or not name:
        return None
    return {"owner": str(owner), "name": str(name)}


def collect_vercel_repository_links(config, token, request_fn=request_json):
    if not config or not token:
        return [], {"status": "unavailable", "discovered": 0, "mapped": 0, "failed": 0}
    team_id = config.get("teamId")
    if not team_id:
        raise ValueError("vercel.teamId is required")
    limit = int(config.get("maxProjects", 100))
    if limit < 1 or limit > 100:
        raise ValueError("vercel.maxProjects must be between 1 and 100")

    projects_url = f"{VERCEL_API}/v9/projects?{urlencode({'teamId': team_id, 'limit': limit})}"
    try:
        payload = request_fn(projects_url, token)
    except PublicLinksError:
        return [], {"status": "error", "discovered": 0, "mapped": 0, "failed": 1}
    projects = payload.get("projects") if isinstance(payload, dict) else None
    if not isinstance(projects, list):
        return [], {"status": "error", "discovered": 0, "mapped": 0, "failed": 1}

    links = []
    failed = 0
    for project in projects:
        if not isinstance(project, dict) or not project.get("id"):
            failed += 1
            continue
        project_id = str(project["id"])
        deployments_url = f"{VERCEL_API}/v6/deployments?{urlencode({'projectId': project_id, 'target': 'production', 'limit': 20, 'teamId': team_id})}"
        domains_url = f"{VERCEL_API}/v9/projects/{quote(project_id, safe='')}/domains?{urlencode({'production': 'true', 'verified': 'true', 'redirects': 'false', 'limit': 100, 'teamId': team_id})}"
        try:
            deployment_payload = request_fn(deployments_url, token)
            deployments = deployment_payload.get("deployments")
            if not isinstance(deployments, list):
                raise PublicLinksError("unexpected deployment payload")
            deployment = next(
                (
                    item
                    for item in deployments
                    if isinstance(item, dict)
                    and (item.get("state") or item.get("readyState")) == "READY"
                    and _repository_from_vercel_deployment(item)
                ),
                None,
            )
            if deployment is None:
                continue
            domain_payload = request_fn(domains_url, token)
            domains = domain_payload.get("domains")
            if not isinstance(domains, list):
                raise PublicLinksError("unexpected domains payload")
            domain = choose_canonical_domain(domains)
            if not domain:
                continue
            links.append(
                {
                    "kind": "front",
                    "url": f"https://{domain}",
                    "provider": "vercel",
                    "repository": _repository_from_vercel_deployment(deployment),
                }
            )
        except (PublicLinksError, ValueError):
            failed += 1

    return links, {
        "status": "ok" if failed == 0 else ("partial" if links else "error"),
        "discovered": len(projects),
        "mapped": len(links),
        "failed": failed,
    }


def collect_cloudflare_repository_links(account_id, token, request_fn=request_json):
    if not account_id or not token:
        return [], {"status": "unavailable", "discovered": 0, "mapped": 0, "failed": 0}
    url = f"{CLOUDFLARE_API}/accounts/{quote(account_id, safe='')}/pages/projects?per_page=100"
    try:
        payload = request_fn(url, token)
    except PublicLinksError:
        return [], {"status": "error", "discovered": 0, "mapped": 0, "failed": 1}
    projects = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(projects, list):
        return [], {"status": "error", "discovered": 0, "mapped": 0, "failed": 1}

    links = []
    failed = 0
    for project in projects:
        if not isinstance(project, dict):
            failed += 1
            continue
        source = project.get("source")
        source_config = source.get("config") if isinstance(source, dict) else None
        if not isinstance(source, dict) or source.get("type") != "github":
            continue
        owner = source_config.get("owner") if isinstance(source_config, dict) else None
        name = source_config.get("repo_name") if isinstance(source_config, dict) else None
        subdomain = str(project.get("subdomain") or "").strip()
        if not owner or not name or not subdomain:
            continue
        try:
            public_url = _https_url(f"https://{subdomain}")
        except ValueError:
            failed += 1
            continue
        links.append(
            {
                "kind": "front",
                "url": public_url,
                "provider": "cloudflare",
                "repository": {"owner": str(owner), "name": str(name)},
            }
        )

    return links, {
        "status": "ok" if failed == 0 else ("partial" if links else "error"),
        "discovered": len(projects),
        "mapped": len(links),
        "failed": failed,
    }


def collect_repository_links(
    config,
    vercel_token=None,
    cloudflare_account_id=None,
    cloudflare_token=None,
    request_fn=request_json,
):
    configured = config.get("repositoryLinks") or []
    if not isinstance(configured, list):
        raise ValueError("repositoryLinks must be a list")
    configured_links = [normalize_configured_link(raw) for raw in configured]
    vercel_links, vercel_status = collect_vercel_repository_links(
        config.get("vercel"), vercel_token, request_fn=request_fn
    )
    cloudflare_links, cloudflare_status = collect_cloudflare_repository_links(
        cloudflare_account_id, cloudflare_token, request_fn=request_fn
    )

    merged = {}
    for link in [*configured_links, *vercel_links, *cloudflare_links]:
        repository = link["repository"]
        key = (
            repository["owner"].lower(),
            repository["name"].lower(),
            link["provider"],
        )
        merged[key] = link
    return list(merged.values()), {
        "configured": len(configured_links),
        "vercel": vercel_status,
        "cloudflare": cloudflare_status,
    }


def enrich_repository_public_links(repositories, links):
    by_repository = {
        (repo["owner"].lower(), repo["name"].lower()): repo for repo in repositories
    }
    for link in links:
        repository = link["repository"]
        target = by_repository.get(
            (repository["owner"].lower(), repository["name"].lower())
        )
        if target is None:
            continue
        public_links = target.setdefault("publicLinks", [])
        identity = link["url"].rstrip("/")
        if any(item.get("url", "").rstrip("/") == identity for item in public_links):
            continue
        public_links.append({"kind": "front", "url": link["url"]})
    return repositories
