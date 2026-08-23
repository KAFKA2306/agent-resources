from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.validate_skill_catalog import validate_catalog, validate_manifest


def make_catalog(root: Path) -> dict:
    (root / "skills" / "example").mkdir(parents=True)
    return {
        "schema": "kafka.agent-resources.skill-collections.v1",
        "count": 1,
        "collections": [
            {
                "id": "example",
                "path": "skills/example",
                "tree_sha": "a" * 40,
                "kind": "skill",
                "title": "Example",
                "source_url": "https://github.com/KAFKA2306/agent-resources/tree/main/skills/example",
            }
        ],
    }


def test_valid_catalog_and_manifest(tmp_path: Path) -> None:
    catalog = make_catalog(tmp_path)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    manifest = {
        "schema": "kafka.agent-resources.api-manifest.v1",
        "resources": [
            {
                "path": "api/v1/skill-collections.json",
                "record_count": 1,
                "sha256": digest,
            }
        ],
    }
    assert validate_catalog(catalog, tmp_path) == []
    assert validate_manifest(manifest, catalog_path, catalog) == []


def test_duplicate_id_and_missing_directory_are_rejected(tmp_path: Path) -> None:
    catalog = make_catalog(tmp_path)
    duplicate = dict(catalog["collections"][0])
    duplicate["path"] = "skills/missing"
    catalog["collections"].append(duplicate)
    catalog["count"] = 2
    errors = validate_catalog(catalog, tmp_path)
    assert "duplicate id: example" in errors
    assert "missing directory: skills/missing" in errors


def test_unlisted_skill_directory_is_rejected(tmp_path: Path) -> None:
    catalog = make_catalog(tmp_path)
    (tmp_path / "skills" / "new-skill").mkdir()
    errors = validate_catalog(catalog, tmp_path)
    assert "catalog missing skill directory: skills/new-skill" in errors


def test_manifest_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    catalog = make_catalog(tmp_path)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    manifest = {
        "schema": "kafka.agent-resources.api-manifest.v1",
        "resources": [
            {
                "path": "api/v1/skill-collections.json",
                "record_count": 1,
                "sha256": "0" * 64,
            }
        ],
    }
    errors = validate_manifest(manifest, catalog_path, catalog)
    assert "manifest SHA-256 does not match catalog bytes" in errors
