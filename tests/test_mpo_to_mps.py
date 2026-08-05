"""Regression tests for state extraction from saved factor bundles."""

from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from p9solver.mpo import mpo_from_circuit
from p9solver.pipeline import mpo_to_mps


def _measure_frame(order):
    """Measure the given qubit at classical bit 0, then the rest in order."""
    n = len(order)
    circuit = QuantumCircuit(n, n)
    for classical, qubit in enumerate(order):
        circuit.measure(qubit, classical)
    return circuit


def test_mpo_to_mps_keeps_measurements_as_a_readout_frame():
    n = 3
    source = QuantumCircuit(n)
    source.h(0)
    mpo = mpo_from_circuit(quimb_circuit(source, Circuit))

    # A completed factor may leave only measurement layers on both sides.  The
    # left one must not be inverted; both are boundary metadata, not unitary
    # residual work.
    left = _measure_frame([0, 1, 2])
    right = _measure_frame([2, 1, 0])
    state, frame = mpo_to_mps(mpo, [left], [right], max_bond=16, cutoff=0.0)

    assert state.L == n
    assert frame == [2, 1, 0]
