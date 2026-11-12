#!/usr/bin/env bash
set -euo pipefail
RUN="$LITE_RUN_DIR"
STATE="$RUN/state"
mkdir -p "$STATE"
case "$1" in
  compact) cat "$RUN/CONDITIONS.md"; exit 0 ;;
  progress) ;;
  *) exit 2 ;;
esac
NOW="$(date +%s)"
MESSAGE=""
if [[ -f "$STATE/best-score" ]]; then
  read -r BEST LAST_BEST < "$STATE/best-score"
  if [[ "$LAST_BEST" =~ ^[0-9]+$ ]] && (( NOW - LAST_BEST >= 1800 )) && [[ ! -e "$STATE/stalled-notified" ]]; then
    : > "$STATE/stalled-notified"
    MESSAGE="Best score unchanged for 30 minutes. Ask an independent audit subagent to review changes, bottlenecks and untried hypotheses; do not assume that a benchmark passed."
  fi
fi
if [[ -n "$LITE_END_EPOCH" ]] && [[ "$LITE_END_EPOCH" =~ ^[0-9]+$ ]] && (( NOW >= LITE_END_EPOCH - 2400 )) && [[ ! -e "$STATE/final-notified" ]]; then
  : > "$STATE/final-notified"
  MESSAGE="$MESSAGE Final 40 minutes: avoid large rewrites, ensure clean commits, check restart/persistence where relevant and run final verification."
fi
if [[ -n "$MESSAGE" ]]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$MESSAGE"
fi
