#!/usr/bin/env bash
set -euo pipefail
# Usage: bash run.sh <repo-url-or-path> <conditions-file> [end-at-RFC3339]
if (( $# < 2 || $# > 3 )); then
  echo "Usage: $0 <repo> <CONDITIONS.md> [2026-11-13T04:00:00+09:00]" >&2; exit 2
fi
for tool in git claude date mktemp realpath; do
  command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 2; }
done
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
SOURCE="$1"
CONDITIONS="$(realpath "$2")"
test -f "$CONDITIONS" || { echo "Missing CONDITIONS.md" >&2; exit 2; }
ROOT="$HOME/.agent-eval"
mkdir -p "$ROOT/runs" "$ROOT/claude-config"
END_EPOCH=""
if (( $# == 3 )); then
  END_EPOCH="$(date -d "$3" +%s)" || exit 2
  if (( END_EPOCH <= $(date +%s) )); then
    echo "Deadline must be in future" >&2; exit 2
  fi
fi
RUN_DIR="$(mktemp -d "$ROOT/runs/lite-XXXXXXXX")"
git clone --quiet --no-local "$SOURCE" "$RUN_DIR/source"
mkdir -p "$RUN_DIR/.claude" "$RUN_DIR/hooks" "$RUN_DIR/state"
cp "$CONDITIONS" "$RUN_DIR/CONDITIONS.md"
cp "$SCRIPT_DIR/settings.json" "$RUN_DIR/.claude/settings.json"
cp "$SCRIPT_DIR/system-prompt-lite.md" "$RUN_DIR/prompt-lite.md"
cp "$SCRIPT_DIR/Makefile.guard" "$RUN_DIR/Makefile.guard"
cp "$SCRIPT_DIR/hooks/"*.sh "$RUN_DIR/hooks/"
printf '{"mcpServers":{}}\n' > "$RUN_DIR/empty-mcp.json"
echo "Run directory: $RUN_DIR"
echo "Initial login: CLAUDE_CONFIG_DIR=$ROOT/claude-config claude auth login"
cd "$RUN_DIR"
# Only explicit environment values cross into the agent process.
exec env -i HOME="$HOME" PATH="$PATH" USER="$(id -un)" LANG=C.UTF-8 TERM=xterm-256color \
  CLAUDE_CONFIG_DIR="$ROOT/claude-config" CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
  LITE_RUN_DIR="$RUN_DIR" LITE_END_EPOCH="$END_EPOCH" \
  claude --strict-mcp-config --mcp-config "$RUN_DIR/empty-mcp.json" \
  --setting-sources project,local --permission-mode dontAsk \
  --append-system-prompt-file "$RUN_DIR/prompt-lite.md" \
  "Read CONDITIONS.md first. Edit only source/. Use Makefile.guard for benchmarks or deploys, commit known-good code, verify results and preserve rollback."
