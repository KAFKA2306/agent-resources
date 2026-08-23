#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_BIN="${OPENCLAW_BIN:-/root/.openclaw/bin/openclaw}"
if [[ ! -x "$OPENCLAW_BIN" ]]; then
  echo "OpenClaw CLI is missing or not executable: $OPENCLAW_BIN" >&2
  exit 1
fi

exec "$OPENCLAW_BIN" gateway run
