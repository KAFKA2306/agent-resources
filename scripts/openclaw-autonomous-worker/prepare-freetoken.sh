#!/usr/bin/env bash
set -euo pipefail

FREETOKEN_VERSION="${FREETOKEN_VERSION:-0.1.2}"
FREETOKEN_HOME="${FREETOKEN_HOME:-$HOME/.local/share/freetoken-ornith}"
FREETOKEN_VENV="${FREETOKEN_VENV:-$FREETOKEN_HOME/venv}"
FREETOKEN_MODEL="${FREETOKEN_MODEL:-ornith-ai/Ornith-1.5-35B-A3B-NVFP4}"
STATE_DIR="${FREETOKEN_STATE_DIR:-$HOME/.local/state/openclaw-autonomous-worker}"
MIN_RAM_GIB="${FREETOKEN_MIN_RAM_GIB:-28}"
MIN_DISK_GIB="${FREETOKEN_MIN_DISK_GIB:-35}"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require uv
require nvidia-smi
require nvcc
require python3
require awk
require df
require free

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "FreeToken profile requires Linux x86_64 (WSL2 Linux is supported)." >&2
  exit 1
fi

GPU_LINE="$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits | head -n 1)"
GPU_NAME="$(printf '%s' "$GPU_LINE" | cut -d, -f1 | xargs)"
GPU_MEMORY_MIB="$(printf '%s' "$GPU_LINE" | cut -d, -f2 | xargs | cut -d. -f1)"
DRIVER_VERSION="$(printf '%s' "$GPU_LINE" | cut -d, -f3 | xargs)"
DRIVER_MAJOR="${DRIVER_VERSION%%.*}"

if [[ ! "$DRIVER_MAJOR" =~ ^[0-9]+$ ]] || (( DRIVER_MAJOR < 580 )); then
  echo "NVIDIA driver r580+ is required; detected $DRIVER_VERSION." >&2
  exit 1
fi

CUDA_RELEASE="$(nvcc --version | sed -n 's/.*release \([0-9][0-9]*\)\..*/\1/p' | tail -n 1)"
if [[ "$CUDA_RELEASE" != "13" ]]; then
  echo "CUDA 13 toolkit with nvcc is required; detected CUDA major ${CUDA_RELEASE:-unknown}." >&2
  exit 1
fi

RAM_GIB="$(free -b | awk '/^Mem:/ {printf "%d", $2 / 1024 / 1024 / 1024}')"
if (( RAM_GIB < MIN_RAM_GIB )); then
  echo "At least ${MIN_RAM_GIB} GiB visible system RAM is required for this profile; detected ${RAM_GIB} GiB." >&2
  echo "If this is WSL2, increase the WSL memory limit before continuing." >&2
  exit 1
fi

mkdir -p "$FREETOKEN_HOME" "$STATE_DIR"
DISK_GIB="$(df -Pk "$FREETOKEN_HOME" | awk 'NR==2 {printf "%d", $4 / 1024 / 1024}')"
if (( DISK_GIB < MIN_DISK_GIB )); then
  echo "At least ${MIN_DISK_GIB} GiB free disk is required for the engine, model and caches; detected ${DISK_GIB} GiB." >&2
  exit 1
fi

if [[ ! -x "$FREETOKEN_VENV/bin/python" ]]; then
  uv venv --python 3.12 "$FREETOKEN_VENV"
fi

uv pip install --python "$FREETOKEN_VENV/bin/python" "freetoken[accel]==${FREETOKEN_VERSION}"
FREETOKEN_BIN="$FREETOKEN_VENV/bin/ft"
FT_VERSION_OUTPUT="$($FREETOKEN_BIN --version)"

if [[ "${FREETOKEN_SKIP_BENCH:-0}" != "1" ]]; then
  "$FREETOKEN_BIN" bench bw --dtype nvfp4
fi

python3 - "$STATE_DIR/freetoken-preflight.json" "$GPU_NAME" "$GPU_MEMORY_MIB" "$DRIVER_VERSION" "$CUDA_RELEASE" "$RAM_GIB" "$DISK_GIB" "$FT_VERSION_OUTPUT" "$FREETOKEN_MODEL" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    path,
    gpu_name,
    gpu_memory_mib,
    driver_version,
    cuda_major,
    ram_gib,
    disk_free_gib,
    freetoken_version,
    model,
) = sys.argv[1:]
record = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "gpu": gpu_name,
    "gpu_memory_mib": int(gpu_memory_mib),
    "driver_version": driver_version,
    "cuda_toolkit_major": int(cuda_major),
    "system_ram_gib": int(ram_gib),
    "disk_free_gib": int(disk_free_gib),
    "freetoken_version": freetoken_version,
    "model": model,
    "bench_profile": str(Path.home() / ".cache/freetoken/benchbw.json"),
}
Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False, sort_keys=True))
PY
