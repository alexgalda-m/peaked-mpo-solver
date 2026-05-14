# Method Notes

This solver uses midpoint MPO cancellation with greedy unswapping.

At a high level:

1. Load the P9 OpenQASM circuit.
2. Consolidate the original two-qubit content into Qiskit `unitary` blocks.
3. Split the circuit at the midpoint.
4. Route both halves to linear connectivity with Sabre.
5. Absorb routed layers into a central MPO from the left or right, choosing the
   side that gives the smaller tensor footprint.
6. When the MPO grows past the tensor-element budget, run greedy unswapping:
   test even/odd adjacent SWAP layers, keep the swaps that reduce local bond
   dimensions, then reroute the remaining circuit around the new permutations.
7. Materialize the final MPS, sample, and report the most frequent bitstring.

The laptop configuration differs from the original high-throughput GPU-oriented
setup in three practical ways:

- It uses lower Sabre effort for repeated post-unswap rerouting while keeping
  the initial route strong enough for P9.
- It caches reusable full-parity SWAP MPOs, avoiding repeated Qiskit-to-quimb
  construction of the same probe layers.
- It reuses a full parity-swap probe when the greedy unswap selector keeps
  every swap in that probed layer, avoiding an immediate second application of
  the same SWAP layer.
- It avoids repeated deep copies when rebuilding remaining routed layer stacks
  after unswapping.

SWAP handling matters. On small exact tests, raw SWAP and CX-decomposed SWAP
agree. On the actual P9 first-unswap state, raw-SWAP probes change unswap
decisions because the MPO's logical physical legs are no longer guaranteed to
align with tensor sites. The production path therefore decomposes unswap-probe
SWAP layers to CX gates. A full-run probe that also decomposed routed SWAPs to
CX was not competitive on this machine, so routed SWAPs stay in the previously
verified representation for the final laptop submission.

## Experimental: Unswap/Reroute Merge

The CLI includes an experimental `bond_route_proxy` unswap selector. It still
starts from the verified bond-improving unswap candidates, but discounts a
candidate if it increases a cheap span-based estimate of the next routed
left/right frontier. This is a low-cost proxy for merging two decisions that
are separate in the baseline loop: reducing the MPO now and making the next
post-unswap reroute easier.

This is implemented and reproducible, but it is not the production default. On
P9 four-cycle compression probes with sampling disabled, using the proxy only
for the first unswap cycle was marginally faster than the verified baseline
(`46.51s` vs `46.99s`) and reduced peak tensor elements (`693472` vs `696160`).
Using it for three or all cycles was slower, so the default remains the simpler
bond selector.
