"""Exact bookkeeping for routed SWAP frames.

This module deliberately separates two ideas that were previously both called
"virtual routing":

* a *boundary frame*, which is one permutation on an external set of legs;
* a *routing trace*, which records permutations at the time cuts of a routed
  circuit.

An end frame is exact when a block of routed SWAPs is wholly at the boundary.
It is not in general a replacement for SWAPs interleaved with work gates.
The latter require the complete trace (or, equivalently, a non-local gate after
the swaps have been elided).  Keeping this distinction explicit prevents a
low-chain-bond vperm factor from being mistaken for a strict MPO.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiskit import QuantumCircuit


_IGNORED = {"barrier", "delay", "measure"}


def _qargs(circuit: QuantumCircuit, instruction) -> tuple[int, ...]:
    return tuple(circuit.find_bit(qubit).index for qubit in instruction.qubits)


@dataclass(frozen=True)
class RoutingEvent:
    """One routed operation and the logical wire held at every line site.

    ``wire_at_site_after`` has the direct hardware meaning: after this event,
    the state originally on logical wire ``wire`` resides at the site where
    ``wire_at_site_after[site] == wire``.  It is intentionally recorded for
    every work event, not merely at factor boundaries.
    """

    operation: str
    qubits: tuple[int, ...]
    wire_at_site_after: tuple[int, ...]


@dataclass(frozen=True)
class RoutingFrameTrace:
    """An exact, inspectable trace of line-routing SWAPs.

    The trace makes no claim that its final frame alone represents the routed
    circuit.  ``boundary_frame_safe`` is a conservative sufficient condition:
    it is true precisely when all routed SWAPs occur after all retained work
    gates in chronological circuit order.  Such a suffix is a genuine output
    frame.  Any mixed work/SWAP region must use the trace or physical swaps.
    """

    num_qubits: int
    events: tuple[RoutingEvent, ...]
    final_wire_at_site: tuple[int, ...]
    swap_count: int
    work_count: int
    work_after_first_swap: int

    @property
    def boundary_frame_safe(self) -> bool:
        return self.work_after_first_swap == 0

    @property
    def final_logical_to_site(self) -> tuple[int, ...]:
        """Return ``site[logical_wire]`` for a final output-frame reader."""
        out = [None] * self.num_qubits
        for site, wire in enumerate(self.final_wire_at_site):
            out[wire] = site
        return tuple(out)

    def summary(self) -> dict[str, int | bool]:
        return {
            "num_qubits": self.num_qubits,
            "swap_count": self.swap_count,
            "work_count": self.work_count,
            "work_after_first_swap": self.work_after_first_swap,
            "boundary_frame_safe": self.boundary_frame_safe,
        }


def trace_routed_circuit(circuit: QuantumCircuit) -> RoutingFrameTrace:
    """Record the exact permutation history of an already-routed circuit.

    ``swap`` is treated as routing scaffolding here.  A caller with a semantic
    (non-router) SWAP must retain it as work before using this helper.
    """
    wire_at_site = list(range(circuit.num_qubits))
    events = []
    swap_count = work_count = work_after_first_swap = 0
    seen_swap = False

    for instruction in circuit.data:
        name = instruction.operation.name
        qubits = _qargs(circuit, instruction)
        if name in _IGNORED:
            continue
        if name == "swap":
            if len(qubits) != 2:
                raise ValueError(f"malformed SWAP qargs: {qubits}")
            left, right = qubits
            wire_at_site[left], wire_at_site[right] = (
                wire_at_site[right],
                wire_at_site[left],
            )
            swap_count += 1
            seen_swap = True
        else:
            work_count += 1
            if seen_swap:
                work_after_first_swap += 1
        events.append(
            RoutingEvent(name, qubits, tuple(wire_at_site))
        )

    return RoutingFrameTrace(
        num_qubits=circuit.num_qubits,
        events=tuple(events),
        final_wire_at_site=tuple(wire_at_site),
        swap_count=swap_count,
        work_count=work_count,
        work_after_first_swap=work_after_first_swap,
    )


def strip_routing_swaps(circuit: QuantumCircuit) -> QuantumCircuit:
    """Return only retained content gates, in their original physical slots.

    This is a diagnostic helper, not a general circuit transformation.  Its
    result plus the trace's final frame is exact only when
    ``boundary_frame_safe`` holds.
    """
    out = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
    for instruction in circuit.data:
        if instruction.operation.name in _IGNORED | {"swap"}:
            continue
        out.append(
            instruction.operation,
            qargs=_qargs(circuit, instruction),
            cargs=[circuit.find_bit(bit).index for bit in instruction.clbits],
        )
    return out
