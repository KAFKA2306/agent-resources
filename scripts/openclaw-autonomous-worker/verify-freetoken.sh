#!/usr/bin/env bash
set -euo pipefail

FREETOKEN_BASE_URL="${FREETOKEN_BASE_URL:-http://127.0.0.1:1919}"
FREETOKEN_SERVED_MODEL="${FREETOKEN_SERVED_MODEL:-ornith-1.5-35b-a3b-nvfp4}"
STATE_DIR="${FREETOKEN_STATE_DIR:-$HOME/.local/state/openclaw-autonomous-worker}"
EVIDENCE_DIR="${FREETOKEN_EVIDENCE_DIR:-$STATE_DIR/freetoken-evidence}"
mkdir -p "$EVIDENCE_DIR"

curl -fsS "$FREETOKEN_BASE_URL/health" >"$EVIDENCE_DIR/health.json"
curl -fsS "$FREETOKEN_BASE_URL/v1/models" >"$EVIDENCE_DIR/models.json"

python3 - "$FREETOKEN_SERVED_MODEL" >"$EVIDENCE_DIR/smoke-request.json" <<'PY'
import json
import sys

print(json.dumps({
    "model": sys.argv[1],
    "messages": [{"role": "user", "content": "Return the single word OK."}],
    "max_tokens": 256,
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
}, ensure_ascii=False))
PY

curl -fsS "$FREETOKEN_BASE_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  --data-binary @"$EVIDENCE_DIR/smoke-request.json" \
  >"$EVIDENCE_DIR/smoke-response.json"

curl -fsS "$FREETOKEN_BASE_URL/v1/stats" >"$EVIDENCE_DIR/stats.json"
curl -fsS "$FREETOKEN_BASE_URL/v1/cache/status" >"$EVIDENCE_DIR/cache.json"

python3 - "$EVIDENCE_DIR" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
manifest = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "files": sorted(path.name for path in root.glob("*.json") if path.name != "manifest.json"),
}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"verified": True, "evidence_dir": str(root), **manifest}, sort_keys=True))
PY
