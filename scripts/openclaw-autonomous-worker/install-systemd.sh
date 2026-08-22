#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/openclaw-autonomous-worker"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENV_FILE="$CONFIG_DIR/env"
CONFIG_FILE="$CONFIG_DIR/config.json"
OPENCLAW_BIN="${OPENCLAW_BIN:-/root/.openclaw/bin/openclaw}"
WORKER_AGENT="${OPENCLAW_WORKER_AGENT:-coding-worker}"
WORKER_HARNESS="${OPENCLAW_WORKER_HARNESS:-opencode}"
WORKER_WORKSPACE="${OPENCLAW_WORKER_WORKSPACE:-/home/kafka/projects}"

mkdir -p "$CONFIG_DIR" "$UNIT_DIR"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require systemctl
require python3
require git
require gh
require curl

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "OpenClaw CLI is missing or not executable: $OPENCLAW_BIN" >&2
  exit 1
fi

if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo "systemd user manager is unavailable. Enable systemd in WSL before installing." >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$ROOT/scripts/openclaw-autonomous-worker/config.example.json" "$CONFIG_FILE"
fi

python3 - "$CONFIG_FILE" "$OPENCLAW_BIN" "$WORKER_AGENT" "$WORKER_HARNESS" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
data["openclaw_bin"] = sys.argv[2]
data["openclaw_agent"] = sys.argv[3]
data["openclaw_harness"] = sys.argv[4]
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY

cat >"$ENV_FILE" <<EOF
AGENT_RESOURCES_ROOT=$ROOT
WORKER_CONFIG=$CONFIG_FILE
LLAMA_RUNNER=${LLAMA_RUNNER:-/home/kafka/projects/run-ornith-llama-server.sh}
OPENCLAW_GATEWAY_RUNNER=${OPENCLAW_GATEWAY_RUNNER:-/home/kafka/projects/run-openclaw-local.sh}
EOF
chmod 600 "$ENV_FILE"

source "$ENV_FILE"
for runner in "$LLAMA_RUNNER" "$OPENCLAW_GATEWAY_RUNNER"; do
  if [[ ! -x "$runner" ]]; then
    echo "runner is missing or not executable: $runner" >&2
    exit 1
  fi
done

install -m 0644 "$ROOT/scripts/openclaw-autonomous-worker/systemd/llama-server.service" "$UNIT_DIR/llama-server.service"
install -m 0644 "$ROOT/scripts/openclaw-autonomous-worker/systemd/openclaw-gateway.service" "$UNIT_DIR/openclaw-gateway.service"
install -m 0644 "$ROOT/scripts/openclaw-autonomous-worker/systemd/openclaw-autonomous-worker.service" "$UNIT_DIR/openclaw-autonomous-worker.service"

# Configure exactly one direct ACP worker. This removes the old parent-model router.
"$OPENCLAW_BIN" config set acp.enabled true --strict-json
"$OPENCLAW_BIN" config set acp.backend '"acpx"' --strict-json

ALLOWED="$($OPENCLAW_BIN config get acp.allowedAgents --json 2>/dev/null || printf '[]')"
MERGED_ALLOWED="$(python3 - "$ALLOWED" "$WORKER_HARNESS" <<'PY'
import json
import sys
values = json.loads(sys.argv[1]) if sys.argv[1].strip() else []
if not isinstance(values, list):
    values = []
if sys.argv[2] not in values:
    values.append(sys.argv[2])
print(json.dumps(values, separators=(",", ":")))
PY
)"
"$OPENCLAW_BIN" config set acp.allowedAgents "$MERGED_ALLOWED" --strict-json
"$OPENCLAW_BIN" config set plugins.entries.acpx.enabled true --strict-json

AGENT_INDEX="$($OPENCLAW_BIN config get agents.list --json | python3 -c '
import json,sys
agents=json.load(sys.stdin)
target=sys.argv[1]
matches=[i for i,a in enumerate(agents) if a.get("id")==target]
print(matches[0] if len(matches)==1 else "")
' "$WORKER_AGENT")"
if [[ -z "$AGENT_INDEX" ]]; then
  "$OPENCLAW_BIN" agents add "$WORKER_AGENT" --workspace "$WORKER_WORKSPACE" --non-interactive --json >/dev/null
  AGENT_INDEX="$($OPENCLAW_BIN config get agents.list --json | python3 -c '
import json,sys
agents=json.load(sys.stdin)
target=sys.argv[1]
matches=[i for i,a in enumerate(agents) if a.get("id")==target]
print(matches[0] if len(matches)==1 else "")
' "$WORKER_AGENT")"
fi
if [[ -z "$AGENT_INDEX" ]]; then
  echo "failed to create or resolve OpenClaw worker agent: $WORKER_AGENT" >&2
  exit 1
fi

# Remove embedded-agent/router-only state from this worker.
for field in model tools subagents contextTokens contextInjection bootstrapMaxChars bootstrapTotalMaxChars experimental; do
  "$OPENCLAW_BIN" config unset "agents.list[$AGENT_INDEX].$field" >/dev/null 2>&1 || true
done
RUNTIME="$(python3 - "$WORKER_HARNESS" <<'PY'
import json,sys
print(json.dumps({"type":"acp","acp":{"agent":sys.argv[1],"mode":"oneshot"}}, separators=(",", ":")))
PY
)"
"$OPENCLAW_BIN" config set "agents.list[$AGENT_INDEX].runtime" "$RUNTIME" --strict-json
"$OPENCLAW_BIN" config validate

# Preflight is non-mutating with respect to repositories and GitHub work items.
python3 -m py_compile "$ROOT/scripts/openclaw-autonomous-worker/supervisor.py"
gh auth status
python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
config = json.loads(config_path.read_text())
required = ["openclaw_bin", "openclaw_agent", "openclaw_harness"]
missing = [key for key in required if not config.get(key)]
if missing:
    raise SystemExit(f"missing worker config keys: {missing}")
roots = [Path(value).expanduser() for value in config.get("repository_roots", [])]
if not roots and not config.get("repositories"):
    raise SystemExit("no repository_roots or explicit repositories configured")
state_dir = Path(config.get("state_dir", "~/.local/state/openclaw-autonomous-worker")).expanduser()
state_dir.mkdir(parents=True, exist_ok=True)
print(json.dumps({"preflight": "pass", "config": str(config_path), "state_dir": str(state_dir)}, sort_keys=True))
PY

if command -v loginctl >/dev/null 2>&1; then
  if ! loginctl show-user "$USER" -p Linger --value 2>/dev/null | grep -qx yes; then
    if command -v sudo >/dev/null 2>&1; then
      sudo loginctl enable-linger "$USER"
    else
      echo "linger is disabled and sudo is unavailable; reboot persistence is not established" >&2
      exit 1
    fi
  fi
fi

systemctl --user daemon-reload
systemctl --user enable llama-server.service openclaw-gateway.service openclaw-autonomous-worker.service
systemctl --user restart llama-server.service openclaw-gateway.service

for unit in llama-server.service openclaw-gateway.service; do
  systemctl --user is-enabled "$unit"
  systemctl --user is-active "$unit"
done

deadline=$((SECONDS + 120))
while (( SECONDS < deadline )); do
  if curl -fsS -H 'Authorization: Bearer llama.cpp-local' http://127.0.0.1:8080/v1/models >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS -H 'Authorization: Bearer llama.cpp-local' http://127.0.0.1:8080/v1/models >/dev/null
"$OPENCLAW_BIN" gateway health

# Start the autonomous supervisor only after the local model and Gateway are healthy.
systemctl --user restart openclaw-autonomous-worker.service
systemctl --user is-enabled openclaw-autonomous-worker.service
systemctl --user is-active openclaw-autonomous-worker.service

STATE_FILE="$(python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path
config = json.loads(Path(sys.argv[1]).read_text())
print(Path(config.get("state_dir", "~/.local/state/openclaw-autonomous-worker")).expanduser() / "state.json")
PY
)"

deadline=$((SECONDS + 30))
while [[ ! -f "$STATE_FILE" ]] && (( SECONDS < deadline )); do
  sleep 1
done
python3 - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit("state.json was not created by the running supervisor")
data = json.loads(path.read_text())
if data.get("version") != 2 or "tasks" not in data:
    raise SystemExit("invalid supervisor state")
print(json.dumps({"ready": True, "state": str(path), "task_count": len(data["tasks"])}, sort_keys=True))
PY
