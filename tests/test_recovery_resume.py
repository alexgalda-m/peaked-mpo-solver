"""End-to-end small-system regression for checkpointed residue recovery."""

from __future__ import annotations

import pickle
import tempfile
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from p9solver.cli import write_recovery_checkpoint
from p9solver.mpo import apply_circuit, mpo_from_circuit
from p9solver.recovery import resume


def _dense(mpo, qubits):
    tensor = mpo ^ ...
    indices = (
        [mpo.upper_ind_id.format(site) for site in range(qubits)]
        + [mpo.lower_ind_id.format(site) for site in range(qubits)]
    )
    return np.asarray(tensor.transpose(*indices).data).reshape(2**qubits, 2**qubits)


def test_recovery_direct_drain_preserves_residual_operator():
    """A checkpointed left/right residue completes without identity restart."""
    qubits = 4
    base = mpo_from_circuit(quimb_circuit(QuantumCircuit(qubits), Circuit))
    left = QuantumCircuit(qubits)
    left.h(0)
    left.cz(0, 3)
    right1 = QuantumCircuit(qubits)
    right1.rx(0.31, 1)
    right1.cz(1, 2)
    right2 = QuantumCircuit(qubits)
    right2.ry(-0.22, 3)
    right2.cz(0, 2)
    state = {
        "mpo": base,
        "layers_left": [left],
        "layers_right": [right1, right2],
        "pending_outer_left": None,
        "pending_outer_right": None,
        "u_consumed_total": 0,
        "remaining_work_gates": 6,
    }

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint = root / "latest.pkl"
        outdir = root / "resumed"
        write_recovery_checkpoint(checkpoint, state, {"case": "small-resume"})
        resumed, remaining_left, remaining_right = resume(
            checkpoint, outdir, max_bond=64, cutoff=0.0
        )
        assert not remaining_left and not remaining_right

        q2c = lambda circuit: quimb_circuit(circuit.decompose("unitary"), Circuit)
        expected = base.copy()
        expected = apply_circuit(
            expected, q2c(left.inverse()), side="right", max_bond=64, cutoff=0.0
        )
        expected = apply_circuit(
            expected, q2c(right1), side="left", max_bond=64, cutoff=0.0
        )
        expected = apply_circuit(
            expected, q2c(right2), side="left", max_bond=64, cutoff=0.0
        )
        assert np.allclose(_dense(resumed, qubits), _dense(expected, qubits), atol=1e-12)

        saved = pickle.load(open(outdir / "latest.pkl", "rb"))
        assert saved["schema"] == "p9solver.recovery-checkpoint.v1"
        final_bundle = pickle.load(open(outdir / "mpo_dump.pkl", "rb"))
        assert not final_bundle["layers_left"] and not final_bundle["layers_right"]
