"""Resume a saved recovery bundle by directly draining its routed residue.

This path is deliberately separate from the main unswap loop.  It is intended
for a nearly complete factor whose final routed gates are expensive enough to
stall the search machinery.  Every accepted layer produces another atomic
checkpoint, so recovery never restarts from identity.
"""
from __future__ import annotations

import argparse
import logging
import pickle
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit_quimb import quimb_circuit
from quimb.tensor import Circuit

from p9solver.cli import write_factor_bundle, write_recovery_checkpoint
from p9solver.mpo import apply_circuit
from p9solver.qiskit_utils import elem_counts


IGNORED = {"swap", "measure", "barrier", "delay"}


def work_count(layers):
    return sum(
        count
        for layer in layers
        for name, count in layer.count_ops().items()
        if name not in IGNORED
    )


def _backend(spec):
    if spec == "numpy":
        return None
    from p9solver import torch_hardening  # noqa: F401
    import torch
    dtype = torch.complex64 if spec == "torch-c64" else torch.complex128
    device = "cuda" if torch.cuda.is_available() else "cpu"

    def convert(x):
        return torch.as_tensor(x, dtype=dtype, device=device)

    return convert


def _q2c(layer, convert):
    layer = layer.decompose("unitary")
    return quimb_circuit(layer, Circuit, to_backend=convert)


def resume(checkpoint, outdir, max_bond, cutoff, backend="numpy"):
    with Path(checkpoint).open("rb") as handle:
        state = pickle.load(handle)
    if state.get("schema") != "p9solver.recovery-checkpoint.v1":
        raise ValueError("not a p9solver recovery checkpoint")
    if state.get("pending_outer_left") is not None or state.get("pending_outer_right") is not None:
        raise ValueError("cannot direct-drain before staged outer chunks activate")

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    convert = _backend(backend)
    mpo = state["mpo"]
    if convert is not None:
        mpo.apply_to_arrays(convert)
    left = list(state.get("layers_left") or [])
    right = list(state.get("layers_right") or [])
    consumed = int(state.get("u_consumed_total", 0))
    generation = int(state.get("metadata", {}).get("generation", 0))

    while work_count(left) or work_count(right):
        candidates = []
        if left:
            layer = left[0]
            candidate = apply_circuit(
                mpo, _q2c(layer.inverse(), convert), side="right",
                max_bond=max_bond, cutoff=cutoff,
            )
            candidates.append((elem_counts(candidate), "left", layer, candidate))
        if right:
            layer = right[0]
            candidate = apply_circuit(
                mpo, _q2c(layer, convert), side="left",
                max_bond=max_bond, cutoff=cutoff,
            )
            candidates.append((elem_counts(candidate), "right", layer, candidate))
        if not candidates:
            break
        _, side, layer, mpo = min(candidates, key=lambda item: item[0])
        if side == "left":
            left.pop(0)
        else:
            right.pop(0)
        consumed += sum(
            count for name, count in layer.count_ops().items() if name not in IGNORED
        )
        generation += 1
        write_recovery_checkpoint(
            outdir / "latest.pkl",
            {
                "mpo": mpo,
                "layers_left": left,
                "layers_right": right,
                "pending_outer_left": None,
                "pending_outer_right": None,
                "u_consumed_total": consumed,
                "remaining_work_gates": work_count(left) + work_count(right),
            },
            {"generation": generation, "recovered_from": str(checkpoint)},
        )
        logging.info(
            "accepted %s layer: work=%s remaining=%s bond=%s",
            side, consumed, work_count(left) + work_count(right), mpo.max_bond(),
        )

    write_factor_bundle(outdir / "mpo_dump.pkl", mpo, left, right)
    return mpo, left, right


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--max-bond", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument(
        "--backend", choices=("numpy", "torch-c64", "torch-c128"),
        default="numpy",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    resume(args.checkpoint, args.outdir, args.max_bond, args.cutoff, args.backend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
