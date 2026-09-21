from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ArtifactLineageDecision:
    status: str
    reason: str


def verify_artifact_lineage(
    *,
    expected_revision: str,
    artifacts: Iterable[Mapping[str, object]],
) -> ArtifactLineageDecision:
    """Verify artifact provenance against one exact source revision.

    Artifact evidence is fail-closed: every item must name a unique path, carry
    the exact source revision, and include a lowercase SHA-256 digest. Empty
    evidence is not considered verified.
    """
    revision = _required_string(expected_revision, "expected_revision")
    seen_paths: set[str] = set()
    count = 0

    for artifact in artifacts:
        count += 1
        path = _mapping_string(artifact, "path")
        if path in seen_paths:
            return ArtifactLineageDecision("UNVERIFIED", f"duplicate_path:{path}")
        seen_paths.add(path)

        observed_revision = _mapping_string(artifact, "revision")
        if observed_revision != revision:
            return ArtifactLineageDecision("UNVERIFIED", f"revision_mismatch:{path}")

        digest = _mapping_string(artifact, "sha256")
        if _SHA256_RE.fullmatch(digest) is None:
            return ArtifactLineageDecision("UNVERIFIED", f"invalid_sha256:{path}")

    if count == 0:
        return ArtifactLineageDecision("UNVERIFIED", "missing_artifacts")

    return ArtifactLineageDecision("PASS", "artifact_lineage_verified")


def _mapping_string(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a non-empty string")
    return _required_string(value, name)


def _required_string(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
