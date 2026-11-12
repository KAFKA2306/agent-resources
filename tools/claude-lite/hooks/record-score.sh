#!/usr/bin/env bash
set -euo pipefail
if (( $# != 1 )) || [[ ! "$1" =~ ^[0-9]+$ ]]; then
  echo "Expected nonnegative integer score" >&2; exit 2
fi
STATE="$LITE_RUN_DIR/state"
mkdir -p "$STATE"
OLD=-1
if [[ -f "$STATE/best-score" ]]; then
  read -r OLD _ < "$STATE/best-score"
fi
if (( $1 > OLD )); then
  printf '%s %s\n' "$1" "$(date +%s)" > "$STATE/best-score.tmp"
  mv "$STATE/best-score.tmp" "$STATE/best-score"
  rm -f "$STATE/stalled-notified"
  echo "new best: $1"
else
  echo "unchanged best: $OLD"
fi
