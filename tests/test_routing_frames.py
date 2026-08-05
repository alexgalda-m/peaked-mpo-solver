"""Exact algebra checks for boundary frames versus routing traces."""

from itertools import permutations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from p9solver.routing_frames import strip_routing_swaps, trace_routed_circuit


def _permutation_operator(logical_to_site):
    """Dense operator that moves logical wire ``w`` to ``logical_to_site[w]``."""
    n = len(logical_to_site)
    matrix = np.zeros((2**n, 2**n), dtype=complex)
    for basis in range(2**n):
        moved = 0
        for wire, site in enumerate(logical_to_site):
            moved |= ((basis >> wire) & 1) << site
        matrix[moved, basis] = 1
    return matrix


def _all_permutations(n):
    return [_permutation_operator(perm) for perm in permutations(range(n))]


def test_swap_suffix_is_an_exact_single_output_frame():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.cz(0, 2)
    circuit.swap(0, 1)
    trace = trace_routed_circuit(circuit)
    stripped = strip_routing_swaps(circuit)

    assert trace.boundary_frame_safe
    expected = Operator(circuit).data
    content = Operator(stripped).data
    output_frame = _permutation_operator(trace.final_logical_to_site)
    assert np.allclose(expected, output_frame @ content, atol=1e-12)


def test_interleaved_swap_is_not_repairable_by_any_two_boundary_frames():
    """A counterexample to “skip SWAPs and store only the final frame”.

    The first H occurs before the routed SWAP and the CZ after it.  Moving the
    SWAP to either external boundary changes which wire the H acts on.  The
    exhaustive 3! x 3! boundary-frame search is intentionally small and makes
    the obstruction independent of a convention for input/output frames.
    """
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.swap(0, 1)
    circuit.cz(1, 2)
    trace = trace_routed_circuit(circuit)
    stripped = strip_routing_swaps(circuit)

    assert trace.swap_count == 1
    assert trace.work_after_first_swap == 1
    assert not trace.boundary_frame_safe

    expected = Operator(circuit).data
    content = Operator(stripped).data
    final_frame = _permutation_operator(trace.final_logical_to_site)
    assert not np.allclose(expected, final_frame @ content, atol=1e-12)
    assert not np.allclose(expected, content @ final_frame, atol=1e-12)

    # Stronger: no pair of arbitrary three-wire boundary permutations repairs
    # this content-only circuit.  A time-cut routing record is indispensable.
    assert not any(
        np.allclose(expected, left @ content @ right, atol=1e-12)
        for left in _all_permutations(3)
        for right in _all_permutations(3)
    )


def test_trace_carries_the_frame_at_every_work_cut():
    circuit = QuantumCircuit(4)
    circuit.x(0)
    circuit.swap(0, 1)
    circuit.cz(1, 2)
    circuit.swap(2, 3)
    circuit.h(3)
    trace = trace_routed_circuit(circuit)

    work = [event for event in trace.events if event.operation != "swap"]
    assert [event.wire_at_site_after for event in work] == [
        (0, 1, 2, 3),
        (1, 0, 2, 3),
        (1, 0, 3, 2),
    ]
    assert trace.summary() == {
        "num_qubits": 4,
        "swap_count": 2,
        "work_count": 3,
        "work_after_first_swap": 2,
        "boundary_frame_safe": False,
    }
