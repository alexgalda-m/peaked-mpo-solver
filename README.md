# P9 Laptop Solver

CPU-oriented MPO + unswapping solver for the 56-qubit P9 peaked-circuit
benchmark (`peaked_circuit_P9_Hqap_56x1917`). Builds on the midpoint-MPO +
greedy-unswap strategy of Kremer & Dupuis
([d-kremer/peaked-circuit-simulation](https://github.com/d-kremer/peaked-circuit-simulation),
arXiv:2604.21908), and extends it with cached SWAP-layer MPO construction,
full parity-swap probe reuse, and route-aware unswap candidate selection.
Runs the full sampled benchmark in 12–22 min on stock Apple Silicon laptops
— versus ~68 min on a single
Nvidia A100 80 GB GPU in the original submission
([#106](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/106))
— see [`BENCHMARKS.md`](BENCHMARKS.md).

## Install

```bash
unset UV_INDEX UV_INDEX_URL PIP_INDEX_URL
uv sync --locked --extra diagnostics
```

The `diagnostics` extra adds matplotlib for the auto-generated `plot.png`
and `samples.png`. Drop it if you don't want PNGs.

## Run the benchmark

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs --tag p9 \
  --samples 1000 --cutoff 0.0006 --no-parallel-rewire
```

The run writes `runs/p9/` with `summary.json`, `stats.csv`, `samples.tsv`,
`plot.png`, `samples.png`, and `run.log`. Success is
`matches_expected_bitstring: true` in `summary.json`.

## Experimental staged center-out routing

`--staged-transpilation` initially routes only P9's two center-adjacent
chunks: `[471:942)` from the left (inverted) and `[942:1413)` from the right.
The raw outer chunks `[0:471)` and `[1413:1885)` do not participate in this
first routing pass. Once both inner fronts drain, the solver derives the
current logical-to-site maps from their routed measurement tails, routes each
outer chunk against those maps, and continues normal MPO compression.

`stats.csv` records this auditable handoff as one `staged_outer_activated`
row; for P9 it must have `u_consumed_total=942`. The handoff preserves the
source circuit's 56-bit classical frame, so rewiring cannot create an
ambiguous second measurement register.

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs --tag p9_staged --samples 1000 \
  --cutoff 0.0006 --no-parallel-rewire --staged-transpilation
```

This is a routing experiment, not a universal acceleration. It can win when
full-circuit initial routing inserts many edge-induced SWAPs or the center has
a low-entanglement cancellation window. It can lose when the deferred reroutes
or their boundary MPO compression cost more than those saved SWAPs. Compare
only completed, bitstring-verified runs and their full timelines.

The handoff design, audit conditions, and live validation checkpoint are in
[`STAGED_TRANSPILATION.md`](STAGED_TRANSPILATION.md).

The QASM has 1917 `rzz` + 3890 `u` gates; Qiskit's `Collect2qBlocks` +
`ConsolidateBlocks` fuse these losslessly into 1885 generic 2q-unitary
blocks, which is what progress lines (`[Cycle 1] 8/1885 gates …`) count.

If compression aborts with `termination_reason: no_progress_cycle_limit`,
check the `stall_mode` in the termination row of `stats.json`: an
`entanglement_blowup` stall is cutoff-sensitive (retry with a different
`--cutoff` — see `BENCHMARKS.md`), while a `swap_thrash` stall is not — raise
`--abort-after-no-progress-unswap-cycles` (e.g. `20`) or disable it with a
negative value. See `BENCHMARKS.md` for both cases and a note on
macOS/Accelerate reproducibility.

## Diagnostics

`plot.png` (Kremer-style compression timeline with bond cap and unswap
trigger marked) is refreshed every 30 s during the run; `samples.png`
(top-bitstring bar chart with the predicted peak highlighted) is written
after sampling completes. Standalone re-renders:

```bash
uv run python diagnostics/plot_run.py runs/p9 [--watch]
uv run python diagnostics/plot_samples.py runs/p9
```

A live Rich TUI dashboard is also available in a second terminal:

```bash
uv run python diagnostics/live_dashboard.py runs/p9
```

## Contributing a benchmark row

Wrapper script that tags the run by machine label (`runs/p9_<label>/`):

```bash
examples/run_p9.sh "M2 Pro"
```

Force-add the resulting `summary.json`, `stats.csv`, `samples.tsv`,
`plot.png`, `samples.png` (the `runs/` directory is gitignored), add a
row to `BENCHMARKS.md`, and open a PR.

## Citation

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

The CPU-oriented changes in this repo are implementation changes around
the same algorithm — not a claim that the underlying method is unrelated.
