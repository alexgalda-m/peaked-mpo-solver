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
  see `STATUS_FOUR_MACHINE_CUTOFF_0006_PASS.md`)
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
  message recommending a different `--cutoff`. The rescue rerouting and
  forced-absorb fallbacks that earlier versions used to paper over this case
  have been removed — empirically they never produced a result that the next
  viable cutoff didn't produce faster and cleanly

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

Use this command for the public P9 benchmark. Run it from
`peakpilot_v4/public_p9_solver`. Do not run a parallel-rewire job at the same
time on the same machine.

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs \
  --tag p9_no_parallel_rewire_s123 \
  --samples 1000 \
  --cutoff 0.0006 \
  --no-parallel-rewire
```

Expected result:

- live cycle progress lines like
  `[Cycle 1] 8/1885 gates (0.4 %) after 14 sec`
- `summary.json`, `stats.json`, and `stats.csv` are checkpointed after every
  live cycle, so interrupted or fail-fast runs still leave structured state
- if compression hits a no-progress fixed point (`peak_max_bond` pinned at
  `--max-bond`), the run aborts cleanly after 2 zero-work cycles with
  `termination_reason: no_progress_cycle_limit`. The fix is to retry with a
  different `--cutoff` (see `STATUS_FOUR_MACHINE_CUTOFF_0006_PASS.md`)
- top sampled bitstring:
  `01101110111001100000100000001010011100101101010111110111`
- `matches_expected_bitstring: true` in
  `runs/p9_no_parallel_rewire_s123/summary.json`

For a live progress dashboard during the run, in a second terminal:

```bash
uv run python diagnostics/live_dashboard.py runs/p9_no_parallel_rewire_s123
```

The run writes:

- `summary.json`: parameters, timing, tensor peaks, sampled peak bitstring
- `stats.csv` and `stats.json`: compression timeline
- `samples.tsv`: raw and measurement-permuted samples
- `run.log`: detailed execution log

`summary.json` also records NumPy/SciPy BLAS/LAPACK configuration and
truncation diagnostics, including how often rows or absorb probes hit the
configured `--max-bond`.

For cross-machine timings on Apple Silicon (M1 Max, M2 Pro, M4 base,
M5 Pro) see `STATUS_FOUR_MACHINE_CUTOFF_0006_PASS.md`. If the run aborts
with `termination_reason: no_progress_cycle_limit` on your hardware,
either retry with a different `--cutoff` from the table in that file or
fall back to the OpenBLAS env described in `OPENBLAS_WORKAROUND.md`.

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
