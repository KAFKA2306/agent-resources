from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_release_provenance(*, revision: str, deployment_url: str, environment: str, run_id: str) -> dict[str, str]:
    values = {"revision": revision.strip(), "deploymentUrl": deployment_url.strip(), "environment": environment.strip(), "runId": run_id.strip()}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError("missing release provenance fields: " + ",".join(sorted(missing)))
    canonical = json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    values["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return values


def verify_release_provenance(payload: object, *, expected_revision: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError("release provenance must be an object")
    digest = payload.get("sha256")
    body = {key: payload.get(key) for key in ("revision", "deploymentUrl", "environment", "runId")}
    if body["revision"] != expected_revision:
        raise ValueError("release provenance revision mismatch")
    rebuilt = build_release_provenance(revision=str(body["revision"] or ""), deployment_url=str(body["deploymentUrl"] or ""), environment=str(body["environment"] or ""), run_id=str(body["runId"] or ""))
    if digest != rebuilt["sha256"]:
        raise ValueError("release provenance checksum mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--deployment-url", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_release_provenance(revision=args.revision, deployment_url=args.deployment_url, environment=args.environment, run_id=args.run_id)
    verify_release_provenance(payload, expected_revision=args.revision)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"release provenance: {payload['revision']} sha256={payload['sha256']}")


if __name__ == "__main__":
    main()
