# P9 Laptop Solver

This is a CPU-oriented implementation of the midpoint MPO cancellation and
greedy unswapping approach for the 56-qubit P9 peaked-circuit benchmark.

The method is inspired by David Kremer and Nicolas Dupuis' peaked-circuit
simulation work. This package keeps that algorithmic starting point visible and
focuses on the laptop execution path: faster local rerouting, cached SWAP-layer
MPO construction, and a narrower production CLI for reproducible CPU runs.

## What This Runs

Target circuit:

- `peaked_circuit_P9_Hqap_56x1917`
- 56 qubits
- bundled QASM path: `circ/peaked_circuit_P9_Hqap_56x1917.qasm`
- expected peak bitstring:
  `01101110111001100000100000001010011100101101010111110111`

Validated laptop defaults:

- midpoint cut: `0.5`
- max MPO bond: `512`
- compression cutoff: `0.0006` (verified on M1 Max, M2 Pro, M4 base, M5 Pro;
  see `BENCHMARKS.md`)
- unswap trigger: `500000` total tensor elements
- parallel rewire: off (`--no-parallel-rewire`)
- initial Sabre routing: `trials=90`, `heuristic=decay`
- post-unswap Sabre routing: `trials=50`, `heuristic=decay`
- unswap-probe SWAPs: decomposed to CX before MPO conversion
- full parity-swap probe reuse: enabled when the selected swaps are exactly
  the probed parity layer
- unswap pass order: `both`, `left`, `right`
- fail-fast stall guard: after 2 consecutive zero-work unswap cycles, the run
  stops with `termination_reason: no_progress_cycle_limit` and an error
  message recommending a different `--cutoff`

On the local M2 Pro test machine, this configuration produced the verified P9
peak in `887.31s` total (`874.98s` compression plus `12.33s`
materialization/sampling). The probe-reuse path reduced a 500-work-gate
equal-progress benchmark from `460.00s` to `435.62s` without changing the peak
MPO size or endpoint tensor size.

## Install

From this folder:

```bash
unset UV_INDEX UV_INDEX_URL PIP_INDEX_URL
uv sync --locked
```

or run directly with:

```bash
uv run p9solve --help
```

## Run The Benchmark

Use this command for the public P9 benchmark. Run it from the repo root. Do
not run a parallel-rewire job at the same time on the same machine.

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs \
  --tag p9 \
  --samples 1000 \
  --cutoff 0.0006 \
  --no-parallel-rewire
```

Expected result:

- live cycle progress lines like
  `[Cycle 1] 8/1885 gates (0.4 %) after 14 sec`
- `summary.json`, `stats.json`, and `stats.csv` are checkpointed after every
  live cycle, so interrupted or fail-fast runs still leave structured state
- with diagnostics installed, `plot.png` is refreshed during compression every
  30 seconds by default; use `--plot-interval-s` to change the cadence or
  `--no-plots` to disable PNG generation
- if compression hits a no-progress fixed point (`peak_max_bond` pinned at
  `--max-bond`), the run aborts cleanly after 2 zero-work cycles with
  `termination_reason: no_progress_cycle_limit`. The fix is to retry with a
  different `--cutoff` (see `BENCHMARKS.md`)
- top sampled bitstring:
  `01101110111001100000100000001010011100101101010111110111`
- `matches_expected_bitstring: true` in
  `runs/p9/summary.json`

The run writes:

- `summary.json`: parameters, timing, tensor peaks, sampled peak bitstring
- `stats.csv` and `stats.json`: compression timeline
- `samples.tsv`: raw and measurement-permuted samples
- `plot.png`: live compression timeline, refreshed during compression when
  diagnostics dependencies are installed
- `samples.png`: top sampled bitstrings after sampling completes when
  diagnostics dependencies are installed
- `run.log`: detailed execution log

`summary.json` also records NumPy/SciPy BLAS/LAPACK configuration and
truncation diagnostics, including how often rows or absorb probes hit the
configured `--max-bond`.

For cross-machine timings on Apple Silicon (M1 Max, M2 Pro, M4 base,
M5 Pro) see `BENCHMARKS.md`. If the run aborts with
`termination_reason: no_progress_cycle_limit` on your hardware, retry
with a different `--cutoff`.

## Diagnostics

Three visualization tools live under `diagnostics/`. The plot scripts pull
in `matplotlib`; install the extra once:

```bash
uv sync --extra diagnostics
```

**Live terminal dashboard** — Rich-based panel that tails `run.log` and
shows cycle, work-gate progress, current bond / total_elems, last rewire
time, and a sparkline of cycle-end totals. Run in a second terminal:

```bash
uv run python diagnostics/live_dashboard.py runs/p9
```

**Compression timeline plot** — `p9solve` writes `runs/<tag>/plot.png` by
default while compression runs, refreshed every 30 seconds. The plot is a
Kremer-style log-scale plot of total tensor elements and MPO bond dimension
over both work consumed and wall time, with the `--max-bond` cap and unswap
trigger drawn as dashed lines and cycle boundaries marked. The standalone
script still works on a finished run, or add `--watch` to refresh while a run
is in flight:

```bash
uv run python diagnostics/plot_run.py runs/p9            # one-shot
uv run python diagnostics/plot_run.py runs/p9 --watch    # live refresh
```

**Sampling chart** — `p9solve` writes `runs/<tag>/samples.png` by default
after sampling completes. It is a horizontal bar chart of the top sampled
bitstrings, with the predicted peak highlighted and an explicit "matches
expected" verdict. The standalone script remains available:

```bash
uv run python diagnostics/plot_samples.py runs/p9
```

For a short compression-only smoke test:

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --tag smoke \
  --max-unswap-cycles 1 \
  --skip-sampling \
  --no-parallel-rewire
```

Experimental route-aware unswapping and parallel rewire are available, but are
off by default. Do not use them for the submission benchmark unless you are
running a separate experiment.

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --tag route_proxy_probe \
  --max-unswap-cycles 4 \
  --skip-sampling \
  --unswap-select-mode bond_route_proxy \
  --unswap-route-proxy-weight 0.5 \
  --unswap-route-proxy-max-cycles 1
```

Local probes showed only a marginal four-cycle gain, so the verified production
path keeps `--unswap-select-mode bond`.

## Attribution

This project uses the same core tensor-network idea as:

```bibtex
@article{kremer2026peaked,
    title   = {Efficient Classical Simulation of Heuristic Peaked Quantum Circuits},
    author  = {Kremer, David and Dupuis, Nicolas},
    year    = {2026},
    eprint  = {2604.21908},
    archivePrefix = {arXiv},
    primaryClass  = {quant-ph},
    url     = {https://arxiv.org/abs/2604.21908}
}
```

The CPU-oriented changes here are implementation changes around the same
high-level strategy, not a claim that the underlying method is unrelated.
