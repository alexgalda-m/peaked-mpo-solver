# speed/drain-livelock — regression evidence

Branch = `codex/s2-recovery-fastpath` (the box's pinned branch) + cherry-pick of
`76a7e05` from `drain-layer-budget`. This is the first build carrying BOTH
forced-drain fixes:

- `--forced-drain-max-threshold-multiple` (fizzle ceiling, from `21d1d45`)
- `--forced-drain-layer-budget` / `--forced-drain-escalate` (from `76a7e05`)

Neither upstream branch has both, which is why no binary the box has run could
clear both give-up modes. See `enigma-peaked2/docs/SPEEDLAB_BASELINE.md`.

## 1. Test suite

    uv run --with pytest python -m pytest tests/ -q
    12 passed

## 2. Defaults preserve prior behaviour (value-identical A/B)

Same circuit (`gapL.qasm`), same flags, unpatched `21d1d45` vs this branch,
neither passing any new flag:

    --max-bond 256 --cutoff 6e-4 --center-ratio 0.5 --seed 777 --max-its 20
    --force-absorb-tail-gates 0 --abort-after-no-progress-unswap-cycles 8
    --sabre-trials 20 --post-sabre-trials 10 --no-parallel-rewire --no-track-fid10

Result:

- **non-timing behavioural diffs: NONE** (including the full
  `truncation_diagnostics` block: rows_at_max_bond 17, absorbing 14,
  unswapping 3, probe hits 18, selected 14, over-threshold 8 — identical)
- parameter diffs are exactly `{outdir, forced_drain_layer_budget,
  forced_drain_escalate}` — i.e. only the two new flags recording their
  defaults (`8`, `False`), which reproduce the previously hardcoded values.

The cherry-pick is purely additive: `forced_drain_layer_budget` defaults to the
`8` that was hardcoded at the old `pipeline.py:2504`, and `forced_drain_escalate`
defaults off.

## 3. What the new flag actually fixes

On `m0_window_sigma0.qasm` (48q, center 0.4283, job-199 config) the default
budget of 8 livelocks: the forced drain walks 8 swap-only layers, never reaches
the work gate 3-7 layers out, gives up with `work_remaining=1`, unswap undoes
everything, and the next cycle is bit-identical. 14 give-ups, wedged at u82.

`--forced-drain-layer-budget 64` eliminates layer-limit give-ups entirely and
carries the traversal past the wedge point.

Keep `--forced-drain-max-threshold-multiple` at its 4.0 default: with the guard
disabled the drain progresses by absorbing 4.57M-element candidates (9x the
unswap threshold), which is the unbounded growth `71fc8ee` added it to stop.

## 4. `--forced-drain-max-growth` (relative memory guard)

Added after measuring that the drain's required absorb grows roughly
geometrically with traversal depth on d3 M0:

    2.05M (s2 u94) -> 2.56M (s1 u94) -> 2.66M (s2 u96) -> 4.57M (s2 u85) -> 8.75M (s2 u86)

The absolute guard compares a candidate against `multiple x unswap_threshold`,
a CONSTANT, so every fixed ceiling is eventually outgrown -- raising 4x to 16x
moved the wall from u96 to u86 rather than removing it. The relative rule

    selected_counts > growth * max(current_elems, unswap_threshold)

scales with the traversal and still rejects the pathology the guard exists for:
the 11M -> 114.7M blow-up in `71fc8ee` is a 10x jump, caught by any growth <= 10
at any absolute size.

Set (>0) it REPLACES the absolute rule; default 0 keeps the absolute rule.

### Regression after the guard refactor

Same default-flag A/B against pristine `21d1d45` (the control-flow around the
guard was restructured, so this was re-run):

- both runs `termination_reason=completed`, `final_max_bond=96`,
  `final_total_elems=112724`
- **non-timing behavioural diffs: NONE**, including the whole
  `truncation_diagnostics` block
- parameter diffs exactly `{outdir, forced_drain_layer_budget,
  forced_drain_escalate, forced_drain_max_growth}`

Suggested starting value: `--forced-drain-max-growth 4` (never absorb something
more than 4x the current object). Untested at 48q — the arms in
`SPEEDLAB_20260805.md` predate this flag.
