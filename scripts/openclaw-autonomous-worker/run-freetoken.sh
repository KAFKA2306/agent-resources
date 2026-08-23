#!/usr/bin/env bash
set -euo pipefail

FREETOKEN_BIN="${FREETOKEN_BIN:-$HOME/.local/share/freetoken-ornith/venv/bin/ft}"
FREETOKEN_MODEL="${FREETOKEN_MODEL:-ornith-ai/Ornith-1.5-35B-A3B-NVFP4}"
FREETOKEN_SERVED_MODEL="${FREETOKEN_SERVED_MODEL:-ornith-1.5-35b-a3b-nvfp4}"
FREETOKEN_HOST="${FREETOKEN_HOST:-127.0.0.1}"
FREETOKEN_PORT="${FREETOKEN_PORT:-1919}"
FREETOKEN_MAX_SEQ_LEN="${FREETOKEN_MAX_SEQ_LEN:-8192}"
FREETOKEN_NUM_TOKENS="${FREETOKEN_NUM_TOKENS:-8192}"
FREETOKEN_MAX_PREFILL_LENGTH="${FREETOKEN_MAX_PREFILL_LENGTH:-2048}"
FREETOKEN_MAX_OUTPUT_TOKENS="${FREETOKEN_MAX_OUTPUT_TOKENS:-4096}"
FREETOKEN_MAX_RUNNING_REQUESTS="${FREETOKEN_MAX_RUNNING_REQUESTS:-1}"
FREETOKEN_MEMORY_RATIO="${FREETOKEN_MEMORY_RATIO:-0.88}"
FREETOKEN_MOE_BACKEND="${FREETOKEN_MOE_BACKEND:-auto}"

if [[ ! -x "$FREETOKEN_BIN" ]]; then
  echo "FreeToken CLI is missing or not executable: $FREETOKEN_BIN" >&2
  exit 1
fi

exec "$FREETOKEN_BIN" serve \
  --model "$FREETOKEN_MODEL" \
  --served-model-name "$FREETOKEN_SERVED_MODEL" \
  --host "$FREETOKEN_HOST" \
  --port "$FREETOKEN_PORT" \
  --max-running-requests "$FREETOKEN_MAX_RUNNING_REQUESTS" \
  --max-output-tokens "$FREETOKEN_MAX_OUTPUT_TOKENS" \
  --max-seq-len-override "$FREETOKEN_MAX_SEQ_LEN" \
  --max-prefill-length "$FREETOKEN_MAX_PREFILL_LENGTH" \
  --num-tokens "$FREETOKEN_NUM_TOKENS" \
  --memory-ratio "$FREETOKEN_MEMORY_RATIO" \
  --moe-backend "$FREETOKEN_MOE_BACKEND" \
  --sampling-defaults model \
  --tool-call-parser auto \
  --reasoning-parser auto \
  --enable-cache-report \
  --graph 1
