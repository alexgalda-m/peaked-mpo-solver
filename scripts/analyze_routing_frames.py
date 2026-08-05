#!/usr/bin/env python3
"""Classify whether a SABRE-routed circuit admits a boundary-frame reading.

This tool is deliberately conservative.  It does not estimate MPO fidelity or
claim an optimal routing.  It answers the narrower exact question: are all
router SWAPs at the output boundary, so their effect can be represented by one
permutation frame without changing an interleaved content gate?  If not, a
low-bond vperm object needs its time-cut routing trace or non-local links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.converters import dag_to_circuit
from qiskit.transpiler import CouplingMap
from qiskit.transpiler.passes import SabreSwap

from p9solver.routing_frames import trace_routed_circuit


def _crossing_width(logical_to_site: tuple[int, ...]) -> int:
    n = len(logical_to_site)
    return max(
        sum(
            (wire < cut) != (logical_to_site[wire] < cut)
            for wire in range(n)
        )
        for cut in range(1, n)
    ) if n > 1 else 0


def _inversions(values: tuple[int, ...]) -> int:
    return sum(
        values[left] > values[right]
        for left in range(len(values))
        for right in range(left + 1, len(values))
    )


def _unitary_only(circuit: QuantumCircuit) -> QuantumCircuit:
    out = QuantumCircuit(circuit.num_qubits)
    for instruction in circuit.data:
        if instruction.operation.name in {"barrier", "delay", "measure"}:
            continue
        out.append(
            instruction.operation,
            [circuit.find_bit(qubit).index for qubit in instruction.qubits],
        )
    return out


def _interaction_graph(circuit: QuantumCircuit) -> dict[str, int | bool]:
    """Return a fixed-order obstruction for an all-adjacent content circuit.

    A single input/output boundary permutation only relabels vertices.  It
    cannot turn a two-qubit interaction graph with a degree greater than two
    into a subgraph of a line.  This is not an MPO-bond lower bound; it is the
    simpler, exact reason a router must change its layout *during* such a
    circuit.
    """
    pairs = set()
    degrees = [0] * circuit.num_qubits
    for instruction in circuit.data:
        if instruction.operation.name in {"barrier", "delay", "measure"}:
            continue
        qubits = [circuit.find_bit(qubit).index for qubit in instruction.qubits]
        if len(qubits) != 2:
            continue
        left, right = sorted(qubits)
        pairs.add((left, right))
    for left, right in pairs:
        degrees[left] += 1
        degrees[right] += 1
    max_degree = max(degrees, default=0)
    return {
        "unique_two_qubit_pairs": len(pairs),
        "interaction_max_degree": max_degree,
        "fixed_line_order_possible": max_degree <= 2,
        "fixed_line_order_obstruction": max_degree > 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qasm", type=Path)
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source = _unitary_only(QuantumCircuit.from_qasm_file(str(args.qasm)))
    routed_result = SabreSwap(
        coupling_map=CouplingMap.from_line(source.num_qubits),
        heuristic="decay",
        trials=args.trials,
        seed=args.seed,
    )(source)
    # Qiskit 1.x and 2.x both accept a circuit here, but the underlying pass
    # result changed type across releases.
    routed = (
        routed_result
        if isinstance(routed_result, QuantumCircuit)
        else dag_to_circuit(routed_result)
    )
    trace = trace_routed_circuit(routed)
    frame = trace.final_logical_to_site
    result = {
        "schema": "p9solver.routing-frame-analysis.v1",
        "qasm": str(args.qasm),
        "qasm_sha256": hashlib.sha256(args.qasm.read_bytes()).hexdigest(),
        "seed": args.seed,
        "trials": args.trials,
        "source_ops": dict(source.count_ops()),
        "source_interaction_graph": _interaction_graph(source),
        "routed_ops": dict(routed.count_ops()),
        "trace": trace.summary(),
        "final_logical_to_site": list(frame),
        "final_frame_inversions": _inversions(frame),
        "final_frame_crossing_width": _crossing_width(frame),
        "verdict": (
            "boundary-frame-safe"
            if trace.boundary_frame_safe
            else "interleaved-routing-trace-required"
        ),
        "verdict_detail": (
            "Every router SWAP follows retained work, so a single output frame "
            "can represent this routed block exactly."
            if trace.boundary_frame_safe
            else "At least one retained work gate follows a router SWAP. A final "
            "frame alone cannot replace the swap history; elision must retain "
            "time-cut wiring or non-local links."
        ),
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
