#!/usr/bin/env bash
set -euo pipefail

QASM_PATH="${1:-circ/peaked_circuit_P9_Hqap_56x1917.qasm}"

uv run p9solve \
  --qasm "$QASM_PATH" \
  --outdir runs \
  --tag p9_no_parallel_rewire_s123 \
  --samples 1000 \
  --no-parallel-rewire
