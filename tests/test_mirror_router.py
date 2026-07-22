from __future__ import annotations

import json

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from p9solver.mirror_router import (
    _greedy_route_to_targets,
    _work_gate_sites,
    load_pair_targets,
    mirror_route_right,
)
from p9solver.qiskit_utils import iter_layers, merge_layers


def _random_stream(nq, n2q, seed, oneq_every=2):
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(nq)
    for k in range(n2q):
        a, b = map(int, rng.choice(nq, size=2, replace=False))
        if k % oneq_every == 0:
            qc.rz(float(rng.uniform(0, 3)), int(rng.integers(nq)))
        qc.cz(a, b)
    return qc


def _strip_measure(qc):
    out = QuantumCircuit(qc.num_qubits)
    for inst in qc.data:
        if inst.operation.name in ("measure", "barrier"):
            continue
        out.append(inst.operation, [qc.find_bit(q).index for q in inst.qubits])
    return out


def _perm_unitary(pos, nq):
    """Permutation matrix for logical wire w residing on line site pos[w]."""
    qc = QuantumCircuit(nq)
    cur = list(range(nq))  # identity placement
    # realize pos via transpositions
    site_of = dict(enumerate(cur))
    want = {w: pos[w] for w in range(nq)}
    perm = [None] * nq
    for w, s in want.items():
        perm[s] = w
    m = np.zeros((2**nq, 2**nq))
    for basis in range(2**nq):
        bits = [(basis >> i) & 1 for i in range(nq)]
        nb = [0] * nq
        for w in range(nq):
            nb[pos[w]] = bits[w]
        m[sum(v << i for i, v in enumerate(nb)), basis] = 1
    return m


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_routed_stream_is_unitarily_exact(seed):
    nq, n2q = 5, 12
    qc = _random_stream(nq, n2q, seed)
    routed_layers, pos = _greedy_route_to_targets(list(iter_layers(qc)), {}, nq)
    routed = _strip_measure(merge_layers(routed_layers))
    u_orig = Operator(qc).data
    u_routed = Operator(routed).data
    p = _perm_unitary(pos, nq)
    # routed = P(pos) . original  (wires moved to their final sites)
    assert np.allclose(p @ u_orig, u_routed, atol=1e-10)


@pytest.mark.parametrize("seed", [4, 5])
def test_all_2q_gates_adjacent_after_routing(seed):
    nq, n2q = 6, 15
    qc = _random_stream(nq, n2q, seed)
    routed_layers, _ = _greedy_route_to_targets(list(iter_layers(qc)), {}, nq)
    routed = merge_layers(routed_layers)
    for inst in routed.data:
        if inst.operation.name in ("measure", "barrier", "swap"):
            continue
        qs = [routed.find_bit(q).index for q in inst.qubits]
        if len(qs) == 2:
            assert abs(qs[0] - qs[1]) == 1


def test_targeted_gates_land_on_target_sites():
    nq = 6
    qc = QuantumCircuit(nq)
    qc.cz(0, 5)
    qc.cz(1, 4)
    qc.cz(2, 3)
    targets = {0: (2, 3), 1: (0, 1), 2: (4, 5)}
    routed_layers, _ = _greedy_route_to_targets(list(iter_layers(qc)), targets, nq)
    sites = _work_gate_sites(routed_layers)
    assert sites == [(2, 3), (0, 1), (4, 5)]


def test_per_wire_gate_order_preserved():
    nq, n2q, seed = 5, 10, 7
    qc = _random_stream(nq, n2q, seed)
    routed_layers, pos = _greedy_route_to_targets(list(iter_layers(qc)), {}, nq)
    routed = _strip_measure(merge_layers(routed_layers))
    # map routed sites back to wires while replaying swaps
    wire_at = list(range(nq))
    seq_orig = {w: [] for w in range(nq)}
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        for q in qs:
            seq_orig[q].append((inst.operation.name, len(qs)))
    seq_routed = {w: [] for w in range(nq)}
    for inst in routed.data:
        qs = [routed.find_bit(q).index for q in inst.qubits]
        if inst.operation.name == "swap":
            a, b = qs
            wire_at[a], wire_at[b] = wire_at[b], wire_at[a]
            continue
        for s in qs:
            seq_routed[wire_at[s]].append((inst.operation.name, len(qs)))
    assert seq_routed == seq_orig


def test_load_pair_targets_rank_conversion(tmp_path):
    sidecar = tmp_path / "sigma_pairs.json"
    sidecar.write_text(json.dumps({"pairs": [[1, 2], [5, 1]]}))
    assert load_pair_targets(sidecar) == {1: 0, 0: 4}


def _synthetic_mirror(nq, depth, seed):
    """U then sigma-conjugated U^dagger (swept): the module toy."""
    rng = np.random.default_rng(seed)
    u = QuantumCircuit(nq)
    for _ in range(depth):
        a, b = map(int, rng.choice(nq, size=2, replace=False))
        u.rz(float(rng.uniform(0, 3)), a)
        u.cz(a, b)
    sigma = list(reversed(range(nq)))  # involution
    udg = QuantumCircuit(nq)
    for inst in reversed(u.data):
        qs = [sigma[u.find_bit(q).index] for q in inst.qubits]
        udg.append(inst.operation.inverse(), [udg.qubits[j] for j in qs])
    full = QuantumCircuit(nq)
    # sigma stays VIRTUAL (as in real S2: explicit_swaps=0); the mirror is
    # U then the sigma-conjugated inverse.
    full.compose(u, inplace=True)
    full.compose(udg, inplace=True)
    # pair map in 2q stream ranks: U has depth CZs (ranks 0..depth-1 in the
    # left/inverted stream = innermost first -> left rank r pairs with right
    # rank r). P_sigma swaps are 2q too; they sit between and are unpaired.
    return full, u, udg


def test_mirror_route_right_end_to_end_small():
    nq, depth, seed = 6, 8, 11
    full, u, udg = _synthetic_mirror(nq, depth, seed)
    n_sw = 0
    cut = len(u.data)  # instruction index of the split (end of U)
    left = QuantumCircuit(nq)
    for inst in list(full.data)[:cut]:
        left.append(inst.operation, [full.find_bit(q).index for q in inst.qubits])
    right = QuantumCircuit(nq)
    for inst in list(full.data)[cut:]:
        right.append(inst.operation, [full.find_bit(q).index for q in inst.qubits])
    left_stream = left.inverse()  # innermost-first, as the pipeline does
    routed_left, pos_left = _greedy_route_to_targets(
        list(iter_layers(left_stream)), {}, nq
    )
    # left stream rank r (innermost-first) = U's CZ rank depth-1-r
    # right stream: n_sw swaps (unpaired) then udg CZ rank k pairs with U CZ
    # rank depth-1-k -> left stream rank k
    pair_map = {n_sw + k: k for k in range(depth)}
    routed_right, pos_right = mirror_route_right(
        routed_left, list(iter_layers(right)), pair_map, nq
    )
    # 1. paired gates match their partner's sites
    ls = _work_gate_sites(routed_left)
    rs = _work_gate_sites(routed_right)
    matched = sum(1 for rrank, lrank in pair_map.items() if rs[rrank] == ls[lrank])
    assert matched == depth, f"only {matched}/{depth} pairs site-matched"
    # 2. unitary exactness of each routed stream
    u_right = Operator(_strip_measure(merge_layers(routed_right))).data
    p_right = _perm_unitary(pos_right, nq)
    assert np.allclose(p_right @ Operator(right).data, u_right, atol=1e-10)
    u_leftr = Operator(_strip_measure(merge_layers(routed_left))).data
    p_left = _perm_unitary(pos_left, nq)
    assert np.allclose(p_left @ Operator(left_stream).data, u_leftr, atol=1e-10)
