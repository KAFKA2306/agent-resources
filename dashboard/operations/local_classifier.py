from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dashboard.collectors.github_api import atomic_write_json

SCHEMA_VERSION = 1
DEFAULT_PROFILE = "ornith-9b-q4"
DEFAULT_CONFIDENCE_THRESHOLD = 0.80


class LocalClassificationError(RuntimeError):
    pass


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def state_dir() -> Path:
    configured = os.environ.get("KAFKA_REPO_OPS_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    return (base / "kafka-repository-ops").resolve()


def default_hf_cache_hub_root() -> Path:
    configured = os.environ.get("HF_CACHE_HUB_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "src" / "hf-cache-hub").resolve()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _run_json(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LocalClassificationError(f"runtime command unavailable: {type(exc).__name__}") from exc
    text = result.stdout.strip()
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise LocalClassificationError("runtime command did not return JSON") from exc
    if result.returncode != 0 and payload.get("status") not in {"STOPPED", "CACHE_MISS"}:
        raise LocalClassificationError(
            f"runtime command failed: {payload.get('status') or result.returncode}"
        )
    return payload


def resolve_runtime(
    hf_root: Path,
    profile: str,
    *,
    ensure: bool,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    script = hf_root / "scripts" / "runtime_model.py"
    if not script.is_file():
        raise LocalClassificationError(f"hf-cache-hub runtime adapter missing: {script}")
    base = [python_executable, str(script)]
    status = _run_json([*base, "status", profile], cwd=hf_root)
    if status.get("status") in {"READY", "ALREADY_RUNNING"}:
        return status
    if not ensure:
        return status
    return _run_json([*base, "serve", profile, "--sync"], cwd=hf_root, timeout=1800)


def observed_domains(inventory: dict[str, Any]) -> list[str]:
    domains = {
        row.get("group")
        for row in inventory.get("repositories", [])
        if row.get("classificationSource") != "unclassified"
        and isinstance(row.get("group"), str)
        and row.get("group")
    }
    return sorted(domains)


def repository_fingerprint(
    row: dict[str, Any], domains: list[str], model_revision: str
) -> str:
    material = {
        "name": row.get("name", ""),
        "description": row.get("description", ""),
        "language": row.get("language", ""),
        "fork": bool(row.get("fork")),
        "topics": sorted(
            topic
            for topic in row.get("topics", [])
            if isinstance(topic, str) and not topic.startswith("agent-zone-")
        ),
        "updatedAt": row.get("updatedAt", ""),
        "domains": domains,
        "modelRevision": model_revision,
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _classification_prompt(row: dict[str, Any], domains: list[str]) -> str:
    metadata = {
        "name": row.get("name", ""),
        "description": row.get("description", "")[:1000],
        "language": row.get("language", ""),
        "fork": bool(row.get("fork")),
        "topics": [
            topic
            for topic in row.get("topics", [])
            if isinstance(topic, str) and not topic.startswith("agent-zone-")
        ][:30],
    }
    return (
        "Classify this GitHub repository into exactly one allowed domain. "
        "Use only the supplied metadata; do not infer private information. "
        "If evidence is weak, return a low confidence. Return ONE compact JSON object only, "
        "with keys domain, confidence, reason. confidence must be a number from 0 to 1. "
        f"Allowed domains: {json.dumps(domains, ensure_ascii=False)}\n"
        f"Repository metadata: {json.dumps(metadata, ensure_ascii=False, sort_keys=True)}"
    )


def call_openai_compatible(
    base_url: str,
    model: str,
    prompt: str,
    *,
    timeout: int = 120,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict repository classifier. Output valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 160,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LocalClassificationError(f"local model request failed: {type(exc).__name__}") from exc
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LocalClassificationError("local model response missing assistant content") from exc
    if not isinstance(content, str):
        raise LocalClassificationError("local model assistant content is not text")
    try:
        result = json.loads(content.strip())
    except json.JSONDecodeError as exc:
        raise LocalClassificationError("local model classification is not strict JSON") from exc
    return result


def validate_classification(result: dict[str, Any], domains: list[str]) -> tuple[str, float, str]:
    if not isinstance(result, dict) or set(result) != {"domain", "confidence", "reason"}:
        raise LocalClassificationError("classification schema mismatch")
    domain = result.get("domain")
    confidence = result.get("confidence")
    reason = result.get("reason")
    if domain not in domains:
        raise LocalClassificationError("classification domain is outside allowed domains")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise LocalClassificationError("classification confidence is not numeric")
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise LocalClassificationError("classification confidence is outside 0..1")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise LocalClassificationError("classification reason is invalid")
    return domain, confidence, reason.strip()


def classify_inventory(
    inventory: dict[str, Any],
    runtime: dict[str, Any],
    state: dict[str, Any],
    *,
    classifier: Callable[[str, str, str], dict[str, Any]],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if inventory.get("scope") != "public-nonarchived-owned-repositories":
        raise LocalClassificationError("classifier accepts only public repository inventory")
    if runtime.get("status") not in {"READY", "ALREADY_RUNNING"}:
        raise LocalClassificationError("local runtime is not ready")
    base_url = runtime.get("base_url")
    model = runtime.get("served_model_id")
    revision = runtime.get("revision")
    if not all(isinstance(value, str) and value for value in (base_url, model, revision)):
        raise LocalClassificationError("runtime identity is incomplete")
    domains = observed_domains(inventory)
    if len(domains) < 2:
        raise LocalClassificationError("at least two explicit domains are required before inference")

    old_entries = state.get("entries", {}) if isinstance(state, dict) else {}
    next_entries: dict[str, Any] = {}
    output = []
    inferred = reused = skipped = failed = 0
    for row in inventory.get("repositories", []):
        full_name = row.get("fullName")
        if not isinstance(full_name, str) or not full_name:
            continue
        if row.get("classificationSource") != "unclassified":
            skipped += 1
            continue
        fingerprint = repository_fingerprint(row, domains, revision)
        previous = old_entries.get(full_name)
        if isinstance(previous, dict) and previous.get("fingerprint") == fingerprint:
            next_entries[full_name] = previous
            output.append(previous)
            reused += 1
            continue
        try:
            raw = classifier(base_url, model, _classification_prompt(row, domains))
            domain, confidence, reason = validate_classification(raw, domains)
            entry = {
                "repository": full_name,
                "fingerprint": fingerprint,
                "suggestedGroup": domain,
                "confidence": confidence,
                "acceptedForView": confidence >= threshold,
                "reason": reason,
                "modelRevision": revision,
                "classifiedAt": iso_now(),
            }
            next_entries[full_name] = entry
            output.append(entry)
            inferred += 1
        except LocalClassificationError as exc:
            failed += 1
            output.append(
                {
                    "repository": full_name,
                    "fingerprint": fingerprint,
                    "status": "FAILED",
                    "error": str(exc),
                    "modelRevision": revision,
                }
            )

    output.sort(key=lambda entry: entry["repository"].casefold())
    snapshot = {
        "schemaVersion": SCHEMA_VERSION,
        "scope": inventory["scope"],
        "owner": inventory.get("owner"),
        "collectedAt": iso_now(),
        "model": {"servedModelId": model, "revision": revision, "baseUrl": base_url},
        "allowedDomains": domains,
        "confidenceThreshold": threshold,
        "classifications": output,
        "summary": {
            "inferredCount": inferred,
            "reusedCount": reused,
            "explicitSkippedCount": skipped,
            "failedCount": failed,
        },
    }
    next_state = {"schemaVersion": SCHEMA_VERSION, "updatedAt": iso_now(), "entries": next_entries}
    return snapshot, next_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--state")
    parser.add_argument("--hf-cache-hub-root", type=Path, default=default_hf_cache_hub_root())
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--ensure-runtime", action="store_true")
    parser.add_argument("--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    args = parser.parse_args(argv)

    try:
        if not 0 <= args.confidence_threshold <= 1:
            raise LocalClassificationError("confidence threshold must be within 0..1")
        inventory = load_json(Path(args.inventory))
        if not isinstance(inventory, dict):
            raise LocalClassificationError("inventory is not a JSON object")
        runtime = resolve_runtime(args.hf_cache_hub_root, args.profile, ensure=args.ensure_runtime)
        if runtime.get("status") not in {"READY", "ALREADY_RUNNING"}:
            snapshot = {
                "schemaVersion": SCHEMA_VERSION,
                "scope": inventory.get("scope"),
                "owner": inventory.get("owner"),
                "collectedAt": iso_now(),
                "status": "SKIPPED",
                "reason": f"local runtime not ready: {runtime.get('status', 'unknown')}",
                "classifications": [],
                "summary": {"inferredCount": 0, "reusedCount": 0, "explicitSkippedCount": 0, "failedCount": 0},
            }
            atomic_write_json(args.output, snapshot)
            print(json.dumps(snapshot["summary"], sort_keys=True))
            return 0
        state_path = Path(args.state).expanduser().resolve() if args.state else state_dir() / "classification-state.json"
        state = load_json(state_path, {"schemaVersion": SCHEMA_VERSION, "entries": {}})
        snapshot, next_state = classify_inventory(
            inventory,
            runtime,
            state,
            classifier=lambda base_url, model, prompt: call_openai_compatible(base_url, model, prompt),
            threshold=args.confidence_threshold,
        )
        atomic_write_json(args.output, snapshot)
        atomic_write_json(state_path, next_state)
        print(json.dumps(snapshot["summary"], sort_keys=True))
        return 0
    except (LocalClassificationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
