import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dashboard.collectors.github_api import GitHubApiError, atomic_write_json, request_json
from dashboard.collectors.repositories import collect_repositories, load_config

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX = BASE_DIR / "data" / "repository-index.json"
DEFAULT_OVERRIDES = BASE_DIR / "config" / "repository-recall-overrides.json"
UNKNOWN_PURPOSE = "未確認: source evidence は取得済みだが semantic review が必要"
UNKNOWN_MATCH = "未確認: semantic review 完了後に検索対象へ昇格"
_ASCII_TERM_RE = re.compile(r"[a-z0-9][a-z0-9+#._-]*")
_JAPANESE_TERM_RE = re.compile(r"[ぁ-んァ-ヶ一-龯ー]{3,}")


def utc_now_iso():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_json(path, default=None):
    source = Path(path)
    if not source.exists():
        return default
    with source.open(encoding="utf-8") as handle:
        return json.load(handle)


def canonical_hash(payload):
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def inventory_names(repositories):
    names = [repo["name"] for repo in repositories]
    if len(names) != len(set(names)):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise ValueError(f"duplicate repository names in inventory: {duplicates}")
    return sorted(names, key=str.casefold)


def _source(kind, url, status, fingerprint=None):
    payload = {"kind": kind, "url": url, "status": status}
    if fingerprint:
        payload["fingerprint"] = fingerprint
    return payload


def collect_source_fact(repo, token=None, request_fn=request_json):
    owner = repo["owner"]
    name = repo["name"]
    api_url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/"
        f"{quote(name, safe='')}"
    )
    repo_url = repo["url"]

    metadata, _ = request_fn(api_url, token)
    if (
        metadata.get("private") is True
        or metadata.get("visibility") != "public"
        or metadata.get("archived") is True
    ):
        raise ValueError(f"source boundary changed for {owner}/{name}")

    metadata_material = {
        "description": metadata.get("description"),
        "topics": sorted(metadata.get("topics") or []),
        "default_branch": metadata.get("default_branch"),
    }
    sources = [
        _source(
            "repository",
            repo_url,
            "ok",
            canonical_hash(metadata_material),
        )
    ]
    material = {"name": name, "repository": metadata_material}

    readme_api = f"{api_url}/readme"
    try:
        readme, _ = request_fn(readme_api, token)
        readme_sha = readme.get("sha")
        if not readme_sha:
            raise ValueError("README response missing sha")
        sources.append(
            _source(
                "readme",
                readme.get("html_url") or repo_url,
                "ok",
                readme_sha,
            )
        )
        material["readme"] = readme_sha
    except GitHubApiError as exc:
        if exc.status != 404:
            raise
        sources.append(_source("readme", repo_url, "absent"))
        material["readme"] = None

    return {
        "name": name,
        "url": repo_url,
        "sources": sources,
        "sourceFingerprint": canonical_hash(material),
        "description": metadata_material["description"],
        "topics": metadata_material["topics"],
    }


def collect_source_facts(repositories, token=None, request_fn=request_json):
    return {
        repo["name"]: collect_source_fact(
            repo,
            token=token,
            request_fn=request_fn,
        )
        for repo in repositories
    }


def _normalize_override(raw):
    if not isinstance(raw, dict):
        raise ValueError("repository recall override must be an object")
    purpose = raw.get("purpose")
    matches = raw.get("matches")
    not_for = raw.get("notFor", [])
    if not isinstance(purpose, str) or not purpose.strip():
        raise ValueError("override purpose must be non-empty")
    if (
        not isinstance(matches, list)
        or not matches
        or not all(isinstance(item, str) and item.strip() for item in matches)
    ):
        raise ValueError("override matches must contain non-empty strings")
    if not isinstance(not_for, list) or not all(
        isinstance(item, str) and item.strip() for item in not_for
    ):
        raise ValueError("override notFor must contain strings")
    return {
        "purpose": purpose.strip(),
        "matches": [item.strip() for item in matches],
        "notFor": [item.strip() for item in not_for],
    }


def _semantic_fields(entry):
    return {
        "purpose": entry["purpose"],
        "matches": entry["matches"],
        "notFor": entry.get("notFor", []),
    }


def _source_semantic(facts):
    description = facts.get("description")
    if not isinstance(description, str) or not description.strip():
        return None
    purpose = description.strip()
    topics = [
        topic.strip()
        for topic in facts.get("topics", [])
        if isinstance(topic, str) and topic.strip()
    ]
    matches = [purpose, *topics]
    return {
        "purpose": purpose,
        "matches": list(dict.fromkeys(matches)),
        "notFor": [],
    }


def _is_placeholder(entry):
    return (
        entry.get("purpose") == UNKNOWN_PURPOSE
        or entry.get("matches") == [UNKNOWN_MATCH]
    )


def merge_index(
    repositories,
    source_facts,
    existing=None,
    overrides=None,
    now=None,
):
    existing_entries = {
        entry["name"]: entry for entry in (existing or {}).get("repositories", [])
    }
    overrides = overrides or {}
    checked_now = now or utc_now_iso()
    result = []

    for repo in sorted(repositories, key=lambda item: item["name"].casefold()):
        name = repo["name"]
        facts = source_facts[name]
        old = existing_entries.get(name)
        override = overrides.get(name)
        normalized_override = _normalize_override(override) if override else None
        source_unchanged = (
            old is not None
            and old.get("sourceFingerprint") == facts["sourceFingerprint"]
        )
        override_unchanged = (
            normalized_override is not None
            and old is not None
            and _semantic_fields(old) == normalized_override
        )

        if source_unchanged and (
            normalized_override is None or override_unchanged
        ):
            source_semantic = _source_semantic(facts)
            should_backfill = (
                normalized_override is None
                and old.get("needsReview") is True
                and _is_placeholder(old)
                and source_semantic is not None
            )
            if not should_backfill:
                preserved = dict(old)
                preserved["url"] = repo["url"]
                preserved["sources"] = facts["sources"]
                result.append(preserved)
                continue

        if normalized_override is not None:
            semantic = normalized_override
            override_changed = (
                old is None or _semantic_fields(old) != normalized_override
            )
            if old is None or override_changed:
                needs_review = False
                checked_at = checked_now
            elif source_unchanged:
                needs_review = False
                checked_at = old.get("checkedAt")
            else:
                needs_review = True
                checked_at = old.get("checkedAt")
        elif old and not source_unchanged:
            semantic = _semantic_fields(old)
            needs_review = True
            checked_at = old.get("checkedAt")
        else:
            source_semantic = _source_semantic(facts)
            if source_semantic is not None:
                semantic = source_semantic
                needs_review = False
                checked_at = checked_now
            else:
                semantic = {
                    "purpose": UNKNOWN_PURPOSE,
                    "matches": [UNKNOWN_MATCH],
                    "notFor": [],
                }
                needs_review = True
                checked_at = None

        result.append(
            {
                "name": name,
                **semantic,
                "url": repo["url"],
                "sources": facts["sources"],
                "sourceFingerprint": facts["sourceFingerprint"],
                "checkedAt": checked_at,
                "needsReview": needs_review,
            }
        )

    document = {"repositories": result}
    validate_index(document)
    return document


def validate_index(document):
    if not isinstance(document, dict) or set(document) != {"repositories"}:
        raise ValueError("index must contain only repositories")
    entries = document["repositories"]
    if not isinstance(entries, list):
        raise ValueError("repositories must be a list")
    names = []
    allowed = {
        "name",
        "purpose",
        "matches",
        "notFor",
        "url",
        "sources",
        "sourceFingerprint",
        "checkedAt",
        "needsReview",
    }
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != allowed:
            raise ValueError("repository entry has unexpected fields")
        name = entry["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be non-empty")
        names.append(name)
        if not isinstance(entry["purpose"], str) or not entry["purpose"].strip():
            raise ValueError(f"purpose must be non-empty: {name}")
        if (
            not isinstance(entry["matches"], list)
            or not entry["matches"]
            or not all(
                isinstance(item, str) and item.strip() for item in entry["matches"]
            )
        ):
            raise ValueError(f"matches must be non-empty strings: {name}")
        if not isinstance(entry["notFor"], list) or not all(
            isinstance(item, str) and item.strip() for item in entry["notFor"]
        ):
            raise ValueError(f"notFor must contain strings: {name}")
        if not isinstance(entry["url"], str) or not entry["url"].startswith(
            "https://github.com/KAFKA2306/"
        ):
            raise ValueError(f"url must be a public KAFKA2306 GitHub URL: {name}")
        if not isinstance(entry["sourceFingerprint"], str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            entry["sourceFingerprint"],
        ):
            raise ValueError(f"sourceFingerprint must be sha256: {name}")
        if not isinstance(entry["sources"], list) or not entry["sources"]:
            raise ValueError(f"sources must be non-empty: {name}")
        for source in entry["sources"]:
            if (
                not isinstance(source, dict)
                or source.get("status") not in {"ok", "absent", "error"}
            ):
                raise ValueError(f"invalid source: {name}")
            if source.get("kind") not in {"repository", "readme"}:
                raise ValueError(f"invalid source kind: {name}")
            if not isinstance(source.get("url"), str) or not source["url"].startswith(
                "https://github.com/KAFKA2306/"
            ):
                raise ValueError(f"invalid source url: {name}")
            if source["status"] == "ok" and not source.get("fingerprint"):
                raise ValueError(f"ok source requires fingerprint: {name}")
        checked_at = entry["checkedAt"]
        if checked_at is not None and not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
            checked_at,
        ):
            raise ValueError(f"checkedAt must be UTC ISO 8601 or null: {name}")
        if not isinstance(entry["needsReview"], bool):
            raise ValueError(f"needsReview must be boolean: {name}")
        if not entry["needsReview"] and checked_at is None:
            raise ValueError(f"reviewed entry requires checkedAt: {name}")
        if not entry["needsReview"] and _is_placeholder(entry):
            raise ValueError(f"reviewed entry cannot use placeholder semantics: {name}")
    if len(names) != len(set(names)):
        raise ValueError("duplicate repository names in index")
    return document


def validate_coverage(repositories, document):
    validate_index(document)
    expected = set(inventory_names(repositories))
    actual = {entry["name"] for entry in document["repositories"]}
    missing = sorted(expected - actual, key=str.casefold)
    extra = sorted(actual - expected, key=str.casefold)
    if missing or extra:
        raise ValueError(
            f"repository recall coverage mismatch: missing={missing}, extra={extra}"
        )
    return True


def semantic_coverage(document):
    validate_index(document)
    repositories = document["repositories"]
    verified = sum(not entry["needsReview"] for entry in repositories)
    needs_review = len(repositories) - verified
    placeholders = sum(_is_placeholder(entry) for entry in repositories)
    return {
        "repositories": len(repositories),
        "verified": verified,
        "needsReview": needs_review,
        "placeholders": placeholders,
    }


def _normalize_text(value):
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _terms(query):
    normalized = _normalize_text(query)
    terms = _ASCII_TERM_RE.findall(normalized)
    terms.extend(_JAPANESE_TERM_RE.findall(normalized))
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def search_index(query, document, limit=5):
    validate_index(document)
    normalized_query = _normalize_text(query)
    terms = _terms(query)
    candidates = []
    for entry in document["repositories"]:
        positive = _normalize_text(" ".join([entry["purpose"], *entry["matches"]]))
        negative = _normalize_text(" ".join(entry["notFor"]))
        score = 0
        reasons = []
        exclusions = []
        if normalized_query and normalized_query in positive:
            score += 5
            reasons.append("full query matched purpose/matches")
        for term in terms:
            if term in positive:
                score += 2
                reasons.append(f"matched:{term}")
            if term in negative:
                score -= 4
                exclusions.append(f"notFor:{term}")
        if score > 0 or exclusions:
            candidates.append(
                {
                    "name": entry["name"],
                    "url": entry["url"],
                    "score": score,
                    "needsReview": entry["needsReview"],
                    "reasons": sorted(set(reasons)),
                    "exclusions": sorted(set(exclusions)),
                    "sources": entry["sources"],
                }
            )
    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["needsReview"],
            item["name"].casefold(),
        )
    )
    candidates = candidates[:limit]
    selectable = [
        item
        for item in candidates
        if not item["needsReview"] and item["score"] >= 4
    ]
    selected = None
    if selectable:
        first = selectable[0]
        second_score = selectable[1]["score"] if len(selectable) > 1 else 0
        if first["score"] - second_score >= 2:
            selected = first["name"]
    return {
        "query": query,
        "selected": selected,
        "ambiguous": selected is None,
        "candidates": candidates,
    }


def refresh_index(
    config_path,
    index_path=DEFAULT_INDEX,
    overrides_path=DEFAULT_OVERRIDES,
    token=None,
):
    config = load_config(config_path)
    repositories = collect_repositories(config, token=token)
    existing = load_json(index_path, {"repositories": []})
    overrides = load_json(overrides_path, {}) or {}
    facts = collect_source_facts(repositories, token=token)
    document = merge_index(
        repositories,
        facts,
        existing=existing,
        overrides=overrides,
    )
    validate_coverage(repositories, document)
    if existing != document:
        atomic_write_json(index_path, document)
        return True, document
    return False, document


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh")
    refresh.add_argument(
        "--config",
        default=str(BASE_DIR / "config" / "repositories.json"),
    )
    refresh.add_argument("--index", default=str(DEFAULT_INDEX))
    refresh.add_argument("--overrides", default=str(DEFAULT_OVERRIDES))

    validate = sub.add_parser("validate")
    validate.add_argument("--index", default=str(DEFAULT_INDEX))

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--index", default=str(DEFAULT_INDEX))

    args = parser.parse_args(argv)
    if args.command == "refresh":
        changed, document = refresh_index(
            args.config,
            args.index,
            args.overrides,
            token=os.getenv("GITHUB_TOKEN"),
        )
        print(
            json.dumps(
                {
                    "changed": changed,
                    **semantic_coverage(document),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "validate":
        document = validate_index(load_json(args.index))
        print(json.dumps(semantic_coverage(document), ensure_ascii=False))
        return 0
    result = search_index(args.query, load_json(args.index))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
