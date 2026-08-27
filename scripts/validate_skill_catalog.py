from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

CATALOG_SCHEMA = "kafka.agent-resources.skill-collections.v1"
MANIFEST_SCHEMA = "kafka.agent-resources.api-manifest.v1"
HEX40 = frozenset("0123456789abcdef")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_git_tree_sha(root: Path, path_text: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", f"HEAD:{path_text}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    tree_sha = result.stdout.strip()
    if len(tree_sha) == 40 and all(char in HEX40 for char in tree_sha):
        return tree_sha
    return None


def validate_catalog(
    catalog: dict[str, Any],
    root: Path,
    *,
    tree_sha_resolver: Callable[[Path, str], str | None] = resolve_git_tree_sha,
) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema") != CATALOG_SCHEMA:
        errors.append("catalog schema is not supported")
    collections = catalog.get("collections")
    if not isinstance(collections, list) or not collections:
        return errors + ["collections must be a non-empty list"]
    if catalog.get("count") != len(collections):
        errors.append("count does not match collections length")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(collections):
        prefix = f"collections[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        path_text = item.get("path")
        tree_sha = item.get("tree_sha")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif item_id in seen_ids:
            errors.append(f"duplicate id: {item_id}")
        else:
            seen_ids.add(item_id)
        if not isinstance(path_text, str) or not path_text.startswith("skills/"):
            errors.append(f"{prefix}.path must be under skills/")
        elif path_text in seen_paths:
            errors.append(f"duplicate path: {path_text}")
        else:
            seen_paths.add(path_text)
            if not (root / path_text).is_dir():
                errors.append(f"missing directory: {path_text}")
            else:
                actual_tree_sha = tree_sha_resolver(root, path_text)
                if actual_tree_sha is not None and tree_sha != actual_tree_sha:
                    errors.append(
                        f"{prefix}.tree_sha does not match current Git tree "
                        f"for {path_text}"
                    )
        if (
            not isinstance(tree_sha, str)
            or len(tree_sha) != 40
            or any(char not in HEX40 for char in tree_sha)
        ):
            errors.append(f"{prefix}.tree_sha must be a lowercase 40-char Git SHA")
        if item.get("kind") not in {"skill", "collection"}:
            errors.append(f"{prefix}.kind must be skill or collection")
        source_url = item.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith(
            "https://github.com/KAFKA2306/agent-resources/tree/"
        ):
            errors.append(f"{prefix}.source_url is not a canonical repository URL")

    skills_dir = root / "skills"
    actual_paths = {
        f"skills/{child.name}"
        for child in skills_dir.iterdir()
        if child.is_dir() and not child.name.startswith(".")
    }
    for path in sorted(actual_paths - seen_paths):
        errors.append(f"catalog missing skill directory: {path}")
    return errors


def validate_manifest(
    manifest: dict[str, Any], catalog_path: Path, catalog: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest schema is not supported")
    resources = manifest.get("resources")
    if not isinstance(resources, list) or len(resources) != 1:
        return errors + ["manifest must contain exactly one resource"]
    resource = resources[0]
    if not isinstance(resource, dict):
        return errors + ["manifest resource must be an object"]
    if resource.get("path") != "api/v1/skill-collections.json":
        errors.append("manifest resource path is incorrect")
    if resource.get("record_count") != catalog.get("count"):
        errors.append("manifest record_count does not match catalog")
    if resource.get("sha256") != sha256_file(catalog_path):
        errors.append("manifest SHA-256 does not match catalog bytes")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--catalog", type=Path, default=Path("api/v1/skill-collections.json")
    )
    parser.add_argument("--manifest", type=Path, default=Path("api/v1/manifest.json"))
    args = parser.parse_args()

    catalog_path = args.root / args.catalog
    manifest_path = args.root / args.manifest
    catalog = load_json(catalog_path)
    manifest = load_json(manifest_path)
    errors = validate_catalog(catalog, args.root)
    errors.extend(validate_manifest(manifest, catalog_path, catalog))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"validated {catalog['count']} skill collections")
    print(f"catalog_sha256={sha256_file(catalog_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
