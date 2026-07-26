# Staged center-out transpilation

This note records the design and validation criteria for the experimental
`--staged-transpilation` mode.

## Procedure

For P9's 1,885 consolidated work blocks, the midpoint is 942. The first
routing pass handles only `[471:942)` (left, inverted for midpoint MPO
absorption) and `[942:1413)` (right). The outer intervals `[0:471)` and
`[1413:1885)` remain raw: they are intentionally absent from the initial
linear-transpilation problem.

When both inner routed streams drain, their measurement tails encode the
logical-to-site maps at the boundary. The implementation routes each raw outer
chunk with that map, strips its newly routed measurement tail, and resumes the
ordinary two-front MPO/unswap loop. It preserves the original 56 classical
bits through every rewire and uses `measure_all(add_bits=False)`, avoiding a
second measurement register.

## Audit conditions

An accepted run must establish all of the following:

1. There is exactly one `staged_outer_activated` row in `stats.csv`.
2. That row has `u_consumed_total=942` for P9—neither outer chunk was routed
   early.
3. Its `left_layers` and `right_layers` are nonzero, showing both raw chunks
   were routed at the boundary.
4. The completed summary reports all 1,885 work blocks and
   `matches_expected_bitstring: true`.

## Live validation checkpoint (2026-07-25)

The first durable staged run crossed the boundary at 4,124.08 seconds with:

| field | value |
|---|---:|
| `u_consumed_total` | 942 |
| deferred left routed layers | 839 |
| deferred right routed layers | 919 |

The run remained live after activation and had absorbed 1,035/1,885 work
blocks at the checkpoint. This proves the staged handoff itself; it is not a
claim of end-to-end correctness until the required final sampling check passes.

## When it can help

Staging is useful when the middle interval offers a low-entanglement
cancellation window and initial all-circuit routing would insert many SWAPs
because of distant edge structure. It is not free: two boundary reroutes and
the resulting MPO state can cost more than the early routing savings. Compare
completed, bitstring-verified runs using both their swap timelines and their
MPO wall times; early initial-SWAP counts alone are not evidence of a speedup.
