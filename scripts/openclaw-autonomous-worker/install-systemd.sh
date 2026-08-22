#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/openclaw-autonomous-worker"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/openclaw-autonomous-worker"
ENV_FILE="$CONFIG_DIR/env"
CONFIG_FILE="$CONFIG_DIR/config.json"

mkdir -p "$CONFIG_DIR" "$UNIT_DIR" "$STATE_DIR"

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

if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo "systemd user manager is unavailable. Enable systemd in WSL before installing." >&2
  exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  cp "$ROOT/scripts/openclaw-autonomous-worker/config.example.json" "$CONFIG_FILE"
fi

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

python3 -m py_compile "$ROOT/scripts/openclaw-autonomous-worker/supervisor.py"
python3 "$ROOT/scripts/openclaw-autonomous-worker/supervisor.py" --config "$CONFIG_FILE" --once || {
  echo "supervisor preflight/one-shot failed; services were not enabled" >&2
  exit 1
}

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
systemctl --user enable --now llama-server.service openclaw-gateway.service openclaw-autonomous-worker.service

for unit in llama-server.service openclaw-gateway.service openclaw-autonomous-worker.service; do
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

if [[ -x /root/.openclaw/bin/openclaw ]]; then
  /root/.openclaw/bin/openclaw gateway health
elif command -v openclaw >/dev/null 2>&1; then
  openclaw gateway health
else
  echo "OpenClaw CLI not found for health read-back" >&2
  exit 1
fi

python3 - <<'PY' "$STATE_DIR/state.json"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit("state.json was not created")
data = json.loads(path.read_text())
if data.get("version") != 1 or "tasks" not in data:
    raise SystemExit("invalid supervisor state")
print(json.dumps({"ready": True, "state": str(path), "task_count": len(data["tasks"])}, sort_keys=True))
PY
