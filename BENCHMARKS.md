# Benchmarks

Full P9 sampled runs on Apple Silicon with `--cutoff 0.0006 --no-parallel-rewire
--samples 1000`, stock Apple Accelerate BLAS.

| Machine | chip-id | compress (s) | sample (s) | total (s) | peak count / 1000 | date |
|---|---|---:|---:|---:|---:|---|
| **M1 Max** | T6000 | 1303.7 | 13.4 | **1317.1** | 50 | 2026-05-13 |
| M2 Pro | T6020 | 938.6 | 12.7 | 951.3 | 50 | 2026-05-12 |
| M4 base | T8132 | 735.1 | 10.0 | 745.0 | 95 | 2026-05-12 |
| M5 Pro | T6050 | 675.8 | 7.9 | 683.7 | 101 | 2026-05-12 |

All runs: `last_work_consumed: 1885`, `termination_reason: completed`,
`matches_expected_bitstring: true`,
`predicted_bitstring: 01101110111001100000100000001010011100101101010111110111`.

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
