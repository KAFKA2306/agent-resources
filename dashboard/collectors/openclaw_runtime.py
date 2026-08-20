import argparse
import json
import subprocess
from datetime import datetime, timezone

from dashboard.collectors.github_api import atomic_write_json

DEFAULT_AGENT_IDS = ("finance", "vr-3d", "games", "research-data", "agent-web")
AUTOMATION_STATUSES = {"disabled", "running", "ok", "error", "skipped", "idle"}


def _run_json(command, runner=subprocess.run):
    result = runner(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "OpenClaw command failed").strip()
        raise RuntimeError(f"{' '.join(command[:2])} failed: {detail[:500]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(command[:2])} did not return JSON") from exc


def _rows(payload, keys):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def build_runtime_snapshot(sessions_payload, automations_payload, agent_ids=None, collected_at=None):
    allowed_agents = set(agent_ids or DEFAULT_AGENT_IDS)
    agents = {agent_id: {"id": agent_id, "sessionCount": 0, "models": set()} for agent_id in allowed_agents}

    for session in _rows(sessions_payload, ("sessions", "items")):
        if not isinstance(session, dict):
            continue
        agent_id = session.get("agentId")
        if agent_id not in allowed_agents:
            continue
        agents[agent_id]["sessionCount"] += 1
        model = session.get("model")
        if isinstance(model, str) and model:
            agents[agent_id]["models"].add(model)

    automations = []
    for job in _rows(automations_payload, ("jobs", "automations", "items")):
        if not isinstance(job, dict):
            continue
        agent_id = job.get("agentId")
        if agent_id not in allowed_agents:
            continue
        job_id = job.get("id")
        name = job.get("name")
        if not isinstance(job_id, str) or not job_id or not isinstance(name, str) or not name:
            continue
        status = job.get("status")
        automations.append(
            {
                "id": job_id,
                "agentId": agent_id,
                "name": name,
                "status": status if status in AUTOMATION_STATUSES else "unknown",
            }
        )

    canonical_agents = []
    for agent_id in sorted(agents):
        row = agents[agent_id]
        canonical_agents.append(
            {
                "id": agent_id,
                "sessionCount": row["sessionCount"],
                "models": sorted(row["models"]),
            }
        )

    automations.sort(key=lambda row: (row["agentId"], row["name"], row["id"]))
    timestamp = collected_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "scope": "domain-agents",
        "collectedAt": timestamp,
        "agents": canonical_agents,
        "automations": automations,
    }


def collect_openclaw_runtime(openclaw="openclaw", agent_ids=None, runner=subprocess.run, collected_at=None):
    sessions = _run_json(
        [openclaw, "sessions", "--all-agents", "--limit", "100", "--json"],
        runner=runner,
    )
    automations = _run_json(
        [openclaw, "automations", "list", "--all", "--json"],
        runner=runner,
    )
    return build_runtime_snapshot(
        sessions,
        automations,
        agent_ids=agent_ids,
        collected_at=collected_at,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect a sanitized OpenClaw domain-agent runtime snapshot")
    parser.add_argument("--openclaw", default="openclaw", help="OpenClaw executable")
    parser.add_argument("--agent-id", action="append", dest="agent_ids")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    payload = collect_openclaw_runtime(openclaw=args.openclaw, agent_ids=args.agent_ids)
    atomic_write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
