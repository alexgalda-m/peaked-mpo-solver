"""Micro-benchmark: does absorbing a pure-SWAP layer inflate the MPO bond
spuriously (imperfect recompression) or genuinely (SWAP at the cut raises the
operator bond)?

Builds an MPO with realistic bond from a random brickwork circuit, then applies
one parity layer of adjacent SWAPs three ways and compares max_bond / elems:
  (a) current path     : apply_circuit with block-SWAP MPO multiply + compress
  (b) exact swap+split : MPO.gate_lower_ per pair, contract='swap+split'
  (c) reference        : same SWAP applied then its inverse (should return to base)
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from p9solver.mpo import mpo_from_circuit, apply_circuit

SWAP = np.array([[1, 0, 0, 0],
                 [0, 0, 1, 0],
                 [0, 1, 0, 0],
                 [0, 0, 0, 1]], dtype=complex)


def random_mpo(n, depth, seed=0, cutoff=1e-9, max_bond=256):
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(n)
    for d in range(depth):
        for q in range(n):
            qc.u(*rng.uniform(0, 2 * np.pi, 3), q)
        for q in range(d % 2, n - 1, 2):
            qc.cz(q, q + 1)
    circ = quimb_circuit(qc, Circuit, to_backend=None)
    return mpo_from_circuit(circ)


def swap_layer_circuit(n, parity):
    qc = QuantumCircuit(n)
    pairs = [(i, i + 1) for i in range(parity, n - 1, 2)]
    for a, b in pairs:
        qc.swap(a, b)
    return qc, pairs


def info(mpo):
    return mpo.max_bond(), int(sum(int(np.prod(t.shape)) for t in mpo))


def main():
    n, depth, parity = 24, 8, 0
    cutoff, max_bond = 6e-4, 512
    base = random_mpo(n, depth)
    print(f"base MPO ({n}q, depth {depth}): max_bond={info(base)[0]} elems={info(base)[1]}")

    # (a) current path: apply SWAP layer as a block-SWAP MPO multiply + compress
    qc_swaps, pairs = swap_layer_circuit(n, parity)
    circ = quimb_circuit(qc_swaps, Circuit, to_backend=None)
    a = apply_circuit(base, circ, side="right", max_bond=max_bond, cutoff=cutoff)
    print(f"(a) apply_circuit block-SWAP multiply : max_bond={info(a)[0]} elems={info(a)[1]}")

    # (b) exact swap+split per adjacent pair on the lower (ket) legs
    b = base.copy()
    for q0, q1 in pairs:
        b.gate_lower_(SWAP, (q0, q1), contract="split", cutoff=cutoff, max_bond=max_bond)
    print(f"(b) exact gate_lower swap+split       : max_bond={info(b)[0]} elems={info(b)[1]}")

    # (c) SWAP then inverse SWAP via exact path -> should match base
    c = b.copy()
    for q0, q1 in pairs:
        c.gate_lower_(SWAP, (q0, q1), contract="split", cutoff=cutoff, max_bond=max_bond)
    print(f"(c) exact SWAP then SWAP^-1 (->base?)  : max_bond={info(c)[0]} elems={info(c)[1]}")


if __name__ == "__main__":
    main()
