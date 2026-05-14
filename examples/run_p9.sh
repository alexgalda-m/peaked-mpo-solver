#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 '<machine label>' [qasm-path]" >&2
  echo "example: $0 'M2 Pro'" >&2
  exit 2
fi

MACHINE_LABEL="$1"
TAG="p9_${MACHINE_LABEL// /_}"
QASM_PATH="${2:-circ/peaked_circuit_P9_Hqap_56x1917.qasm}"

uv run p9solve \
  --qasm "$QASM_PATH" \
  --outdir runs \
  --tag "$TAG" \
  --samples 1000 \
  --cutoff 0.0006 \
  --no-parallel-rewire
