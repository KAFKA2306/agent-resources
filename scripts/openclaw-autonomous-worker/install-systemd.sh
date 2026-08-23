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
FREETOKEN_VERSION="${FREETOKEN_VERSION:-0.1.2}"
FREETOKEN_HOME="${FREETOKEN_HOME:-$HOME/.local/share/freetoken-ornith}"
FREETOKEN_BIN="${FREETOKEN_BIN:-$FREETOKEN_HOME/venv/bin/ft}"
FREETOKEN_MODEL="${FREETOKEN_MODEL:-ornith-ai/Ornith-1.5-35B-A3B-NVFP4}"
FREETOKEN_SERVED_MODEL="${FREETOKEN_SERVED_MODEL:-ornith-1.5-35b-a3b-nvfp4}"
FREETOKEN_HOST="${FREETOKEN_HOST:-127.0.0.1}"
FREETOKEN_PORT="${FREETOKEN_PORT:-1919}"
FREETOKEN_BASE_URL="http://${FREETOKEN_HOST}:${FREETOKEN_PORT}"
FREETOKEN_RUNNER="${FREETOKEN_RUNNER:-$ROOT/scripts/openclaw-autonomous-worker/run-freetoken.sh}"
FREETOKEN_VERIFY="${FREETOKEN_VERIFY:-$ROOT/scripts/openclaw-autonomous-worker/verify-freetoken.sh}"
OPENCLAW_GATEWAY_RUNNER="${OPENCLAW_GATEWAY_RUNNER:-$ROOT/scripts/openclaw-autonomous-worker/run-openclaw-gateway.sh}"
FREETOKEN_START_TIMEOUT_SECONDS="${FREETOKEN_START_TIMEOUT_SECONDS:-1800}"

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
require uv
require nvidia-smi
require nvcc

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

FREETOKEN_VERSION="$FREETOKEN_VERSION" \
FREETOKEN_HOME="$FREETOKEN_HOME" \
FREETOKEN_MODEL="$FREETOKEN_MODEL" \
  bash "$ROOT/scripts/openclaw-autonomous-worker/prepare-freetoken.sh"

if [[ ! -x "$FREETOKEN_BIN" ]]; then
  echo "FreeToken CLI was not installed at $FREETOKEN_BIN" >&2
  exit 1
fi

cat >"$ENV_FILE" <<EOF
AGENT_RESOURCES_ROOT=$ROOT
WORKER_CONFIG=$CONFIG_FILE
OPENCLAW_BIN=$OPENCLAW_BIN
FREETOKEN_BIN=$FREETOKEN_BIN
FREETOKEN_RUNNER=$FREETOKEN_RUNNER
FREETOKEN_MODEL=$FREETOKEN_MODEL
FREETOKEN_SERVED_MODEL=$FREETOKEN_SERVED_MODEL
FREETOKEN_HOST=$FREETOKEN_HOST
FREETOKEN_PORT=$FREETOKEN_PORT
FREETOKEN_MAX_SEQ_LEN=${FREETOKEN_MAX_SEQ_LEN:-8192}
FREETOKEN_NUM_TOKENS=${FREETOKEN_NUM_TOKENS:-8192}
FREETOKEN_MAX_PREFILL_LENGTH=${FREETOKEN_MAX_PREFILL_LENGTH:-2048}
FREETOKEN_MAX_OUTPUT_TOKENS=${FREETOKEN_MAX_OUTPUT_TOKENS:-4096}
FREETOKEN_MAX_RUNNING_REQUESTS=${FREETOKEN_MAX_RUNNING_REQUESTS:-1}
FREETOKEN_MEMORY_RATIO=${FREETOKEN_MEMORY_RATIO:-0.88}
FREETOKEN_MOE_BACKEND=${FREETOKEN_MOE_BACKEND:-auto}
OPENCLAW_GATEWAY_RUNNER=$OPENCLAW_GATEWAY_RUNNER
EOF
chmod 600 "$ENV_FILE"

for runner in "$FREETOKEN_RUNNER" "$FREETOKEN_VERIFY" "$OPENCLAW_GATEWAY_RUNNER"; do
  if [[ ! -f "$runner" ]]; then
    echo "runner is missing: $runner" >&2
    exit 1
  fi
done

install -m 0644 "$ROOT/scripts/openclaw-autonomous-worker/systemd/freetoken.service" "$UNIT_DIR/freetoken.service"
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

python3 -m py_compile "$ROOT/scripts/openclaw-autonomous-worker/supervisor.py"
bash -n "$FREETOKEN_RUNNER" "$FREETOKEN_VERIFY" "$OPENCLAW_GATEWAY_RUNNER"
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

# Remove the service owned by the previous llama.cpp runtime contract.
systemctl --user disable --now llama-server.service >/dev/null 2>&1 || true
rm -f "$UNIT_DIR/llama-server.service"

systemctl --user daemon-reload
systemctl --user enable freetoken.service openclaw-gateway.service openclaw-autonomous-worker.service

# Start inference first. Initial model download can be large, so readiness has its own timeout.
systemctl --user restart freetoken.service
systemctl --user is-enabled freetoken.service
systemctl --user is-active freetoken.service

deadline=$((SECONDS + FREETOKEN_START_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if curl -fsS "$FREETOKEN_BASE_URL/health" >/dev/null 2>&1 && \
     curl -fsS "$FREETOKEN_BASE_URL/v1/models" >/dev/null 2>&1; then
    break
  fi
  if ! systemctl --user is-active freetoken.service >/dev/null 2>&1; then
    systemctl --user status freetoken.service --no-pager >&2 || true
    exit 1
  fi
  sleep 2
done
curl -fsS "$FREETOKEN_BASE_URL/health" >/dev/null
curl -fsS "$FREETOKEN_BASE_URL/v1/models" >/dev/null

# Let FreeToken own the local OpenClaw provider configuration.
"$FREETOKEN_BIN" launch openclaw --server "$FREETOKEN_BASE_URL" --config --yes

systemctl --user restart openclaw-gateway.service
systemctl --user is-enabled openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
"$OPENCLAW_BIN" gateway health

# A real completion and runtime/cache snapshots are required before the supervisor starts.
FREETOKEN_BASE_URL="$FREETOKEN_BASE_URL" \
FREETOKEN_SERVED_MODEL="$FREETOKEN_SERVED_MODEL" \
  bash "$FREETOKEN_VERIFY"

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
