#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run.sh /absolute/path/to/repo /absolute/path/to/CONDITIONS.md 2026-11-14T18:00:00+09:00
[[ $# -eq 3 ]] || { echo 'usage: run.sh REPO CONDITIONS.md DEADLINE_ISO8601_WITH_OFFSET' >&2; exit 2; }
command -v claude >/dev/null || { echo 'Claude Code CLI is required' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'python3 is required' >&2; exit 2; }
command -v git >/dev/null || { echo 'git is required' >&2; exit 2; }

SOURCE_REPO="$(git -C "$1" rev-parse --show-toplevel)"
CONDITIONS="$(realpath "$2")"
[[ -f "$CONDITIONS" ]] || { echo 'CONDITIONS.md does not exist' >&2; exit 2; }
[[ -z "$(git -C "$SOURCE_REPO" status --porcelain)" ]] || {
  echo 'Source repository has uncommitted changes; commit or stash them first' >&2; exit 2;
}
DEADLINE_EPOCH="$(python3 - "$3" <<'PY'
from datetime import datetime
import sys
try:
    deadline = datetime.fromisoformat(sys.argv[1])
    if deadline.tzinfo is None or deadline.utcoffset() is None:
        raise ValueError('timezone offset required')
    print(int(deadline.timestamp()))
except ValueError as exc:
    raise SystemExit(f'invalid deadline: {exc}')
PY
)"
[[ "$DEADLINE_EPOCH" -gt "$(date +%s)" ]] || {
  echo 'Deadline must be in the future' >&2; exit 2;
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
RUN_BASE="${AGENT_LITE_BASE:-${HOME}/.agent-eval}"
mkdir -p "$RUN_BASE/runs" "$RUN_BASE/claude-config"
chmod 700 "$RUN_BASE" "$RUN_BASE/runs" "$RUN_BASE/claude-config"
RUN_ROOT="$(mktemp -d "$RUN_BASE/runs/run-XXXXXXXX")"
chmod 700 "$RUN_ROOT"
# Local clone keeps the source repo and its credentials/working tree untouched.
git clone --quiet --no-hardlinks -- "$SOURCE_REPO" "$RUN_ROOT/repo"
cp "$SCRIPT_DIR/settings.json" "$RUN_ROOT/settings.json"
cp "$SCRIPT_DIR/hooks.py" "$RUN_ROOT/hooks.py"
cp "$CONDITIONS" "$RUN_ROOT/CONDITIONS.md"
{
  cat "$SCRIPT_DIR/lite-prompt.md"
  printf '\n__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__\n\n'
  cat "$RUN_ROOT/CONDITIONS.md"
} > "$RUN_ROOT/run-prompt.md"
printf '{"mcpServers":{}}\n' > "$RUN_ROOT/mcp.json"

export AGENT_LITE_RUN_ROOT="$RUN_ROOT"
export AGENT_LITE_DEADLINE_EPOCH="$DEADLINE_EPOCH"
export CLAUDE_CONFIG_DIR="$RUN_BASE/claude-config"
# Login once under the dedicated config: CLAUDE_CONFIG_DIR=... claude auth login
printf 'Isolated run: %s\n' "$RUN_ROOT"
printf 'Source commit: %s\n' "$(git -C "$RUN_ROOT/repo" rev-parse HEAD)"
cd "$RUN_ROOT/repo"
# Empty setting-sources excludes user/project/local settings. Managed policy still applies.
# The repo's tracked CLAUDE.md remains project input; this is not OS-level isolation.
exec claude -p \
  --setting-sources '' \
  --settings "$RUN_ROOT/settings.json" \
  --strict-mcp-config --mcp-config "$RUN_ROOT/mcp.json" \
  --append-system-prompt-file "$RUN_ROOT/run-prompt.md" \
  --output-format stream-json --verbose \
  'Execute the task in the supplied run conditions. Work only in this clone. Record benchmark scores as AGENT_SCORE=<number> in the output of make bench. Keep a rollback commit before deploying. Continue until the task is complete, then report the final state.'