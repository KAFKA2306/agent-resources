#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/openclaw-autonomous-worker"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENV_FILE="$CONFIG_DIR/env"
CONFIG_FILE="$CONFIG_DIR/config.json"

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

# Preflight must be non-mutating. Do not run the supervisor with --once here:
# --once intentionally processes one real Issue end-to-end.
python3 -m py_compile "$ROOT/scripts/openclaw-autonomous-worker/supervisor.py"
gh auth status
python3 - "$CONFIG_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
config = json.loads(config_path.read_text())
dispatch = config.get("dispatch_command")
if not isinstance(dispatch, list) or not dispatch:
    raise SystemExit("dispatch_command must be a non-empty list")
executable = Path(dispatch[0]).expanduser()
if "/" in dispatch[0] and not executable.is_file():
    raise SystemExit(f"dispatch executable not found: {executable}")
if "/" in dispatch[0] and not os.access(executable, os.X_OK):
    raise SystemExit(f"dispatch executable is not executable: {executable}")
roots = [Path(value).expanduser() for value in config.get("repository_roots", [])]
if not roots and not config.get("repositories"):
    raise SystemExit("no repository_roots or explicit repositories configured")
state_dir = Path(
    config.get("state_dir", "~/.local/state/openclaw-autonomous-worker")
).expanduser()
state_dir.mkdir(parents=True, exist_ok=True)
print(
    json.dumps(
        {
            "preflight": "pass",
            "config": str(config_path),
            "state_dir": str(state_dir),
        },
        sort_keys=True,
    )
)
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

STATE_FILE="$(python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
state_dir = Path(
    config.get("state_dir", "~/.local/state/openclaw-autonomous-worker")
).expanduser()
print(state_dir / "state.json")
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
if data.get("version") != 1 or "tasks" not in data:
    raise SystemExit("invalid supervisor state")
print(
    json.dumps(
        {"ready": True, "state": str(path), "task_count": len(data["tasks"])},
        sort_keys=True,
    )
)
PY
