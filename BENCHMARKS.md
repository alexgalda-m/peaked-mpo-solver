# Benchmarks

Full P9 sampled runs on Apple Silicon with `--cutoff 0.0006 --no-parallel-rewire
--samples 1000`, stock Apple Accelerate BLAS.

| Machine    | chip-id | compress (s) | sample (s) |  total (s) | peak count | #2 count | date       |
|------------|---------|-------------:|-----------:|-----------:|-----------:|---------:|------------|
| M5 Pro     | T6050   |        726.0 |        8.2 |  **734.2** |         92 |       10 | 2026-05-13 |
| M4         | T8132   |        737.4 |        9.8 |  **747.2** |         96 |        9 | 2026-05-13 |
| M2 Pro     | T6020   |        959.8 |       13.2 |  **973.0** |         46 |       28 | 2026-05-13 |
| M1 Max     | T6000   |       1326.3 |       13.2 | **1339.5** |         36 |        6 | 2026-05-13 |

All runs: `last_work_consumed: 1885`, `termination_reason: completed`,
`matches_expected_bitstring: true`.

## Comparison to the original GPU baseline

The original Kremer & Dupuis result on this exact circuit
([submission #106](https://github.com/quantum-advantage-tracker/quantum-advantage-tracker.github.io/issues/106),
verified) used the same MPO + unswapping method on a single datacenter GPU:

| Implementation         | Hardware                 | Runtime | Peak count |
|------------------------|--------------------------|--------:|-----------:|
| Kremer & Dupuis (#106) | 1× Nvidia A100 80 GB GPU |  4059 s | ~100/1000  |
| This work (M5 Pro)     | Apple M5 Pro laptop CPU  |   734 s |    92/1000 |

The headline change is the **compute class**: the same simulation that needed a
datacenter A100 80 GB GPU runs here on a consumer Apple Silicon laptop CPU with
no GPU, producing a comparable ~10% peak with `matches_expected_bitstring: true`.
Wall-clock favors the laptop too (~5.5× faster), but that gap is partly
configuration-dependent since the two runs use different compression cutoffs
(this work fixes `--cutoff 0.0006`; the #106 cutoff is not stated). The decisive,
hardware-level comparison is **a single datacenter Nvidia A100 80 GB GPU vs a
consumer laptop CPU with no GPU at all** — that shift in compute class is the
robust improvement.

## Reproduce

```bash
uv run p9solve \
  --qasm circ/peaked_circuit_P9_Hqap_56x1917.qasm \
  --outdir runs \
  --tag p9_<machine> \
  --samples 1000 \
  --cutoff 0.0006 \
  --no-parallel-rewire
```

If your run aborts with `termination_reason: no_progress_cycle_limit`, check the
`stall_mode` field in the termination row of `stats.json` (or the `run.log`
error line) before changing anything — the two stall modes need opposite fixes:

- **`stall_mode: entanglement_blowup`** — the MPO is pinned near `--max-bond`
  or `--unswap-threshold` and no block can be absorbed without overflowing.
  This is the cutoff-sensitive case: retry with a different `--cutoff` (try
  `0.001` first), or raise `--max-bond` / `--unswap-threshold`.
- **`stall_mode: swap_thrash`** — the MPO is *small* at the stall (low
  `max_bond`, `total_elems` well under the threshold) but the last cycles
  absorbed only routing SWAP layers before reaching the next 2q block, so zero
  work gates were consumed. **Changing `--cutoff` will not help.** Raise
  `--abort-after-no-progress-unswap-cycles` (e.g. `20`) or set it negative to
  disable the guard, and let the reroute push past the patch.

## A note on reproducibility across macOS / Accelerate versions

The greedy unswap + reroute trajectory is numerically sensitive: routing is
deterministic (Sabre, fixed `--seed`, pinned Qiskit), so the only moving part
across two Apple Silicon machines with identical `qiskit`/`quimb`/`numpy`/`scipy`
is the **Apple Accelerate LAPACK SVD**, which ships with the OS. Different macOS
versions can nudge the truncated bond structure just enough to send the greedy
path into a `swap_thrash` region on one machine and not another — even on the
same chip family. The rows above were produced on macOS 26.x; on an older macOS
the same hardware may need a higher `--abort-after-no-progress-unswap-cycles`
to complete. If a run stalls in `swap_thrash` mode, that is the first knob to
try, not the cutoff.
