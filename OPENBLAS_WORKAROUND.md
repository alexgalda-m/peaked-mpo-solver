# Apple-Silicon OpenBLAS Workaround

The current public default (`--cutoff 0.0006`) completes the full P9
benchmark on every Apple Silicon SKU we have data for (M1 Max, M2 Pro, M4
base, M5 Pro) on stock Apple Accelerate. See
`STATUS_FOUR_MACHINE_CUTOFF_0006_PASS.md` for the per-machine timings.

This OpenBLAS recipe is a **diagnostic fallback** for two cases where
Accelerate hit a deadlock during development:

1. Older `--cutoff` values (notably `0.001` and `0.002`) reliably deadlock
   around `t_u≈192/1885` on M4 base and M5 Pro under Accelerate. The fix
   in production code is to use `--cutoff 0.0006`; this document is here
   in case a future SVD/Accelerate revision breaks that and you need a
   quick BLAS swap to confirm.
2. Cross-validating whether a regression is in the algorithm or in the
   numpy/scipy ↔ Accelerate path.

If you are running the standard `--cutoff 0.0006` and the run completes
cleanly, you do not need any of this.

## When to use this

Run the standard `uv sync --locked` env first.
Use this OpenBLAS env if and only if:

- The full or 300-gate run reaches `t_u=192/1885` (or near it, e.g. 174,
  204) and then either stalls indefinitely or aborts with
  `termination_reason: no_progress_cycle_limit`, **and**
- `numpy.show_config()` reports `Apple Accelerate` for BLAS / LAPACK.

If the standard env completes the benchmark, you don't need this. The
OpenBLAS env is ~1.5–2× slower wall-clock than Accelerate on Apple
Silicon because OpenBLAS is not vendor-tuned for Apple Silicon SoCs.

## Prerequisites

- Apple Silicon Mac, macOS 12 or later.
- `~50 MB` of free disk for the miniforge installer, plus ~600 MB for
  the conda env.
- A working `curl` (system default on macOS is fine).
- The repo cloned with the `circ/peaked_circuit_P9_Hqap_56x1917.qasm` file
  bundled. The OpenBLAS env installs `p9solver` in editable mode against
  the same source tree, so the standard uv env and the OpenBLAS env can
  coexist without conflict.

You do **not** need Homebrew, Xcode, or sudo. The install lives entirely
under `~/miniforge3`.

## Install (one-time, ~5 minutes)

### 1. Install miniforge silently

```bash
curl -fsSL -o /tmp/Miniforge3.sh \
  "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
bash /tmp/Miniforge3.sh -b -p ~/miniforge3
~/miniforge3/bin/conda --version
```

The `-b` flag means batch / non-interactive; nothing is written outside
`~/miniforge3`. You can wipe the whole install later with `rm -rf
~/miniforge3` if you want to undo.

### 2. Create the env with OpenBLAS-linked numpy + scipy from conda-forge

```bash
~/miniforge3/bin/conda create -n p9openblas -y -c conda-forge \
  "python=3.10" \
  "numpy=2.2.6" \
  "scipy=1.15.2" \
  "openblas" \
  "pip"
```

Notes:

- `python=3.10` matches `pyproject.toml` (`requires-python = ">=3.10,<3.11"`).
- `numpy=2.2.6` matches the lockfile exactly.
- `scipy=1.15.2` is **one patch level behind** the lockfile pin
  (`1.15.3`). At the time of writing, conda-forge does not ship an
  OpenBLAS-built `scipy 1.15.3` for `osx-arm64 py310`. The PyPI 1.15.3
  wheel is hard-linked against Accelerate (`scipy.show_config()` reports
  `"name": "Accelerate", "detection method": "extraframeworks"`), so
  using it defeats the workaround. The 1.15.2 / 1.15.3 patch delta has
  not produced different trajectories in any test so far.

### 3. Install the rest of the pinned stack with pip

`pip` inside this conda env will pick up the conda-installed numpy and
scipy as already-satisfied. The rest of the deps come from PyPI at the
lockfile pins:

```bash
~/miniforge3/envs/p9openblas/bin/pip install \
  "qiskit==1.4.5" "qiskit-quimb==0.0.10" "quimb==1.11.2" \
  "cotengra==0.7.5" "numba==0.65.0" "llvmlite==0.47.0" \
  "sympy==1.14.0" "autoray==0.8.10" "rustworkx==0.17.1" \
  "symengine==0.13.0" "psutil==7.2.2" "tqdm==4.67.3" \
  "cytoolz==1.1.0" "dill==0.4.1" "stevedore==5.7.0" \
  "typing-extensions==4.15.0"
```

If pip ever tries to upgrade `scipy` (e.g. as a transitive dep), reinstall
the conda-forge build to restore OpenBLAS linkage:

```bash
~/miniforge3/bin/conda install -n p9openblas -y --force-reinstall \
  -c conda-forge "scipy=1.15.2"
```

### 4. Install the local `p9solver` package in editable mode

This points the env at the live source tree, so `git pull` here also
updates the package code without reinstalling.

```bash
~/miniforge3/envs/p9openblas/bin/pip install -e <path-to-repo>/public_p9_solver
```

### 5. Verify OpenBLAS is actually being used

The conda-forge wheels are built against OpenBLAS, but it's worth
confirming both that the build-time linkage and the runtime linkage are
OpenBLAS, not Accelerate. Run:

```bash
~/miniforge3/envs/p9openblas/bin/python <<'PY'
import json, os, subprocess
import numpy as np, scipy.linalg as sla

# Build-time linkage
print("numpy version:", np.__version__)
print(json.dumps(
    np.show_config(mode='dicts').get('Build Dependencies', {}).get('blas'),
    indent=2,
))

import scipy
print("scipy version:", scipy.__version__)
print(json.dumps(
    scipy.show_config(mode='dicts').get('Build Dependencies', {}).get('blas'),
    indent=2,
))

# Runtime linkage: do a SVD so libs are loaded, then check what's mapped
sla.svd(np.random.rand(200, 200))
out = subprocess.check_output(
    ['vmmap', '-resident', str(os.getpid())],
    stderr=subprocess.DEVNULL,
).decode()
accel = sum(1 for l in out.splitlines() if 'Accelerate.framework' in l)
openb = sum(1 for l in out.splitlines() if any(k in l for k in (
    'libopenblas', 'libblas.', 'libcblas.', 'liblapack.',
)))
print()
print(f"Accelerate.framework lines: {accel}")
print(f"OpenBLAS/libblas/liblapack lines: {openb}")
PY
```

You want to see:

- numpy `Build Dependencies.blas`: `"name": "blas", ... "openblas configuration": ...` (any non-`Accelerate` value)
- scipy `Build Dependencies.blas`: same
- `Accelerate.framework lines: 0`
- `OpenBLAS/libblas/liblapack lines: > 0`

If either build-time linkage still reports `Accelerate`, you have a wheel
override leaking in — repeat step 2's `--force-reinstall` and rerun the
verification.

## Running the benchmark in the OpenBLAS env

Use the env's entry point directly (do **not** use `uv run`, which would
use the standard Accelerate-linked venv):

```bash
cd <path-to-repo>/public_p9_solver

# Smoke test (~25 s in OpenBLAS, vs ~9 s in Accelerate)
~/miniforge3/envs/p9openblas/bin/p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs --tag smoke_openblas \
  --max-unswap-cycles 1 --skip-sampling --no-parallel-rewire

# 300-gate guardrail (~10–15 min in OpenBLAS on M5 Pro)
~/miniforge3/envs/p9openblas/bin/p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs --tag m5_guardrail_300_openblas \
  --max-work-gates 300 --skip-sampling --no-parallel-rewire

# Full sampled benchmark (long — plan for 40–80 min on M5 Pro)
TAG="<machine>_openblas_cutoff_001_full_p9_s123_$(date +%Y%m%d_%H%M%S)"
~/miniforge3/envs/p9openblas/bin/p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs --tag "$TAG" \
  --samples 1000 --cutoff 0.001 --no-parallel-rewire \
  2>&1 | tee "runs/${TAG}.console.log"
```

## Tuning OpenBLAS threading (optional)

OpenBLAS picks a thread count from `OPENBLAS_NUM_THREADS` (falls back to
the machine core count). On a heavily oversubscribed laptop (M5 Pro has
18 cores) you may want to cap it to keep the system responsive:

```bash
OPENBLAS_NUM_THREADS=8 ~/miniforge3/envs/p9openblas/bin/p9solve ...
```

`numba`'s thread count is independent and set via `NUMBA_NUM_THREADS`.

## How to undo

The standard uv env is untouched — it lives at
`public_p9_solver/.venv/` and uses Apple Accelerate. To remove the
OpenBLAS env entirely:

```bash
~/miniforge3/bin/conda env remove -n p9openblas -y
# and optionally the whole miniforge install:
rm -rf ~/miniforge3
```

## Known reference results in this env

| Machine | Run | `last_work_consumed` | wall sec | `peak_max_bond` | `peak_total_elems` |
|---|---|---|---|---|---|
| M5 Pro (24 GB) | `m5_guardrail_300_openblas`, `--max-work-gates 300 --skip-sampling` | 301 | 668.6 | 510 | 1,100,704 |

Add full-sampled M5 Pro / M1 Max results here as they land.

## What this proves and what it does not

It proves that with the same code, same lockfile pins (modulo `scipy
1.15.2` vs `1.15.3`), and same seed, swapping `numpy`/`scipy` from Apple
Accelerate to OpenBLAS lets the algorithm cross the deadlock region on
M5 Pro. That isolates the cause to Accelerate's SVD / LAPACK numerics on
this SoC rather than to the algorithm itself.

It does **not** prove this is a permanent fix. Accelerate is still the
right BLAS for performance on Apple Silicon; the long-term fix likely
lives in the algorithm's absorb-acceptance tolerance or in a hardened
rescue path, not in shipping an OpenBLAS-only env. Treat this as a
diagnostic and reproducibility workaround.
