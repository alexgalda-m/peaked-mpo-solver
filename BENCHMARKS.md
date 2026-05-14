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

If your run aborts with `termination_reason: no_progress_cycle_limit`, retry
with a different `--cutoff` (try `0.001` first).
