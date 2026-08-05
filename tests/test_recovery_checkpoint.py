import pickle

import numpy as np
import quimb.tensor as qtn

from p9solver.cli import build_parser, write_recovery_checkpoint


def test_driver_and_checkpoint_cli_defaults():
    args = build_parser().parse_args(["--qasm", "toy.qasm"])
    assert args.svd_driver == "native"
    assert args.checkpoint_dir is None
    assert args.checkpoint_every_work_gates == 0
    assert args.track_fid10_until_work_gates is None

    bounded = build_parser().parse_args([
        "--qasm", "toy.qasm", "--track-fid10-until-work-gates", "160"
    ])
    assert bounded.track_fid10
    assert bounded.track_fid10_until_work_gates == 160


def test_recovery_checkpoint_is_atomic_and_cpu_backed(tmp_path):
    mpo = qtn.MPO_identity(3)
    out = tmp_path / "latest.pkl"
    write_recovery_checkpoint(
        out,
        {
            "mpo": mpo,
            "layers_left": [],
            "layers_right": [],
            "u_consumed_total": 7,
            "remaining_work_gates": 2,
        },
        {"tag": "unit"},
    )

    assert out.exists()
    assert not (tmp_path / "latest.pkl.tmp").exists()
    with out.open("rb") as handle:
        saved = pickle.load(handle)
    assert saved["schema"] == "p9solver.recovery-checkpoint.v1"
    assert saved["metadata"]["tag"] == "unit"
    assert saved["u_consumed_total"] == 7
    assert all(isinstance(t.data, np.ndarray) for t in saved["mpo"])
