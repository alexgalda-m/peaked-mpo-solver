#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-diagnostic_reports/$(hostname -s)_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUTDIR"

{
  echo "===== git ====="
  git rev-parse HEAD
  git status --short

  echo
  echo "===== macOS ====="
  sw_vers || true
  uname -a || true

  echo
  echo "===== hardware ====="
  system_profiler SPHardwareDataType || true
  sysctl machdep.cpu.brand_string hw.ncpu hw.activecpu hw.physicalcpu hw.logicalcpu hw.memsize \
    hw.perflevel0.physicalcpu hw.perflevel0.l2cachesize hw.perflevel0.l1icachesize hw.perflevel0.l1dcachesize \
    hw.perflevel1.physicalcpu hw.perflevel1.l2cachesize 2>/dev/null || true

  echo
  echo "===== uv / python ====="
  uv --version || true
  uv run python -VV
  uv run python - <<'PY'
import platform
import sys
print("executable:", sys.executable)
print("platform:", platform.platform())
print("machine:", platform.machine())
PY

  echo
  echo "===== package freeze ====="
  uv pip freeze | sort

  echo
  echo "===== lock and binary hashes ====="
  shasum -a 256 uv.lock pyproject.toml || true
  shasum -a 256 \
    .venv/lib/python3.10/site-packages/numpy/_core/_multiarray_umath*.so \
    .venv/lib/python3.10/site-packages/numpy/linalg/_umath_linalg*.so \
    .venv/lib/python3.10/site-packages/scipy/linalg/_flapack*.so \
    .venv/lib/python3.10/site-packages/scipy/linalg/cython_lapack*.so \
    2>/dev/null || true

  echo
  echo "===== numpy / scipy config ====="
  uv run python - <<'PY'
import numpy as np
import scipy
print("numpy", np.__version__)
np.__config__.show()
print("scipy", scipy.__version__)
scipy.show_config()
if hasattr(np, "show_runtime"):
    np.show_runtime()
PY

  echo
  echo "===== otool linkage ====="
  otool -L \
    .venv/lib/python3.10/site-packages/numpy/_core/_multiarray_umath*.so \
    .venv/lib/python3.10/site-packages/numpy/linalg/_umath_linalg*.so \
    .venv/lib/python3.10/site-packages/scipy/linalg/_flapack*.so \
    .venv/lib/python3.10/site-packages/scipy/linalg/cython_lapack*.so \
    2>/dev/null || true

  echo
  echo "===== thread environment ====="
  uv run python - <<'PY'
import os

keys = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
for key in keys:
    if key in os.environ:
        print(f"{key}={os.environ[key]}")
PY
} | tee "$OUTDIR/machine_state.txt"

uv run python diagnostics/svd_fingerprint.py --out "$OUTDIR/svd_default.json" > "$OUTDIR/svd_default.stdout"
VECLIB_MAXIMUM_THREADS=1 uv run python diagnostics/svd_fingerprint.py --out "$OUTDIR/svd_veclib1.json" > "$OUTDIR/svd_veclib1.stdout"

echo "Wrote $OUTDIR"
