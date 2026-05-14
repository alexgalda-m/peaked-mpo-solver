#!/usr/bin/env python3
"""Kremer-style total_elems plot for a p9solve run, with extras.

Reproduces the two-panel figure from Kremer & Dupuis'
`peaked-circuit-unswapping.ipynb` and adds:

  - a bond-dimension panel with the compression cap shown as a dashed line
  - black `x` markers at rows that hit the max-bond cap
  - faint vertical lines at each unswap-cycle boundary
  - a header line with run tag, cycle, work %, peaks, termination reason

Usage:
    uv run python diagnostics/plot_run.py runs/<tag>
    uv run python diagnostics/plot_run.py runs/<tag> --out plot.png
    uv run python diagnostics/plot_run.py runs/<tag> --watch 3
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TOTAL_GATES = 1885


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_rows(stats_csv: Path):
    rows = []
    last_work = 0.0
    cap = None
    with stats_csv.open() as f:
        for r in csv.DictReader(f):
            work = _f(r.get("u_consumed_total"))
            if work is not None:
                last_work = work
            te = _f(r.get("total_elems"))
            mb = _f(r.get("max_bond"))
            t = _f(r.get("time"))
            limit = _f(r.get("compression_max_bond_limit"))
            if limit is not None:
                cap = limit
            rows.append({
                "time": t,
                "work": last_work,
                "total_elems": te,
                "max_bond": mb,
                "stage": r.get("stage", ""),
                "hit": r.get("hit_max_bond", "").lower() == "true",
            })
    return rows, cap


def split(rows, key, stage=None):
    out_x, out_y = [], []
    for r in rows:
        if r[key] is None or r["time"] is None:
            continue
        if stage is not None and r["stage"] != stage:
            continue
        out_x.append(r)
        out_y.append(r[key])
    return out_x, out_y


def render(stats_csv: Path, summary_json: Path | None, out: Path):
    rows, cap = load_rows(stats_csv)
    plottable = [r for r in rows if r["time"] is not None and r["total_elems"] is not None]
    if not plottable:
        return 0, False

    by_time = sorted(plottable, key=lambda r: r["time"])
    by_work = sorted(plottable, key=lambda r: r["work"])

    abs_rows = [r for r in plottable if r["stage"] == "absorbing"]
    un_rows = [r for r in plottable if r["stage"] == "unswapping"]
    cycle_rows = [r for r in rows if r["stage"] == "unswap_cycle_summary"]
    hit_rows = [r for r in plottable if r["hit"] and r["max_bond"] is not None]

    bond_rows = [r for r in plottable if r["max_bond"] is not None]
    by_work_bond = sorted(bond_rows, key=lambda r: r["work"])

    peak_te = max((r["total_elems"] for r in plottable), default=0.0)
    peak_te_row = next(r for r in plottable if r["total_elems"] == peak_te)
    peak_mb = max((r["max_bond"] for r in bond_rows), default=0.0)
    peak_mb_row = next((r for r in bond_rows if r["max_bond"] == peak_mb), None)
    last_work = max((r["work"] for r in plottable), default=0.0)
    last_time = max((r["time"] for r in plottable), default=0.0)
    cycle = len(cycle_rows)
    terminated = any(r["stage"] == "termination" for r in rows)

    termination_reason = ""
    cutoff = None
    unswap_threshold = None
    parallel_rewire = None
    run_status = None
    if summary_json and summary_json.exists():
        try:
            s = json.loads(summary_json.read_text())
            termination_reason = s.get("termination_reason", "") or ""
            run_status = s.get("run_status")
            params = s.get("parameters", {})
            cutoff = params.get("cutoff")
            unswap_threshold = params.get("unswap_threshold")
            parallel_rewire = params.get("parallel_rewire")
        except Exception:
            pass

    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=False)
    trigger_label = (
        f"unswap trigger = {int(unswap_threshold):,}"
        if unswap_threshold is not None else None
    )

    # --- Panel 1: total_elems vs work ---
    ax = axes[0]
    ax.plot([r["work"] for r in by_work], [r["total_elems"] for r in by_work],
            "-", color="lightgray", linewidth=2.0)
    ax.plot([r["work"] for r in un_rows], [r["total_elems"] for r in un_rows],
            ".r", markersize=2, label="Unswapping")
    ax.plot([r["work"] for r in abs_rows], [r["total_elems"] for r in abs_rows],
            ".b", markersize=2, label="Absorption")
    for r in cycle_rows:
        ax.axvline(r["work"], color="gray", alpha=0.15, linewidth=0.8)
    if unswap_threshold is not None:
        ax.axhline(unswap_threshold, color="k", linestyle="--",
                   linewidth=0.8, label=trigger_label)
    ax.plot([peak_te_row["work"]], [peak_te], "k*", markersize=10,
            label=f"peak total_elems = {int(peak_te):,}")
    ax.set_yscale("log")
    ax.set_xlabel("Total 2q Unitaries Consumed")
    ax.set_ylabel("Total tensor elements")
    ax.legend(loc="lower left", fontsize=8)

    # --- Panel 2: max_bond vs work ---
    ax = axes[1]
    ax.plot([r["work"] for r in by_work_bond], [r["max_bond"] for r in by_work_bond],
            "-", color="lightgray", linewidth=2.0)
    ax.plot([r["work"] for r in un_rows if r["max_bond"] is not None],
            [r["max_bond"] for r in un_rows if r["max_bond"] is not None],
            ".r", markersize=2, label="Unswapping")
    ax.plot([r["work"] for r in abs_rows if r["max_bond"] is not None],
            [r["max_bond"] for r in abs_rows if r["max_bond"] is not None],
            ".b", markersize=2, label="Absorption")
    for r in cycle_rows:
        ax.axvline(r["work"], color="gray", alpha=0.15, linewidth=0.8)
    if cap is not None:
        ax.axhline(cap, color="k", linestyle="--", linewidth=0.8,
                   label=f"max_bond cap = {int(cap)}")
    if hit_rows:
        ax.plot([r["work"] for r in hit_rows], [r["max_bond"] for r in hit_rows],
                "kx", markersize=7, markeredgewidth=1.4, label="cap hit")
    if peak_mb_row is not None:
        ax.plot([peak_mb_row["work"]], [peak_mb], "k*", markersize=10,
                label=f"peak max_bond = {int(peak_mb)}")
    ax.set_yscale("log")
    ax.set_xlabel("Total 2q Unitaries Consumed")
    ax.set_ylabel("MPO max bond")
    ax.legend(loc="lower left", fontsize=8)

    # --- Panel 3: total_elems vs time ---
    ax = axes[2]
    ax.plot([r["time"] for r in by_time], [r["total_elems"] for r in by_time],
            "-", color="lightgray", linewidth=2.0)
    ax.plot([r["time"] for r in un_rows], [r["total_elems"] for r in un_rows],
            ".r", markersize=2, label="Unswapping")
    ax.plot([r["time"] for r in abs_rows], [r["total_elems"] for r in abs_rows],
            ".b", markersize=2, label="Absorption")
    for r in cycle_rows:
        if r["time"] is not None:
            ax.axvline(r["time"], color="gray", alpha=0.15, linewidth=0.8)
    if unswap_threshold is not None:
        ax.axhline(unswap_threshold, color="k", linestyle="--",
                   linewidth=0.8, label=trigger_label)
    ax.plot([peak_te_row["time"]], [peak_te], "k*", markersize=10,
            label=f"peak total_elems = {int(peak_te):,}")
    ax.set_yscale("log")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Total tensor elements")
    ax.legend(loc="lower left", fontsize=8)

    work_pct = 100.0 * last_work / TOTAL_GATES
    header_bits = [
        stats_csv.parent.name,
        f"cycle {cycle}",
        f"{last_time:.0f}s",
        f"work {int(last_work)}/{TOTAL_GATES} ({work_pct:.1f}%)",
    ]
    if cutoff is not None:
        header_bits.append(f"cutoff {cutoff:g}")
    if unswap_threshold is not None:
        header_bits.append(f"unswap_trig {int(unswap_threshold):,}")
    if parallel_rewire is not None:
        header_bits.append(f"parallel_rewire: {'on' if parallel_rewire else 'off'}")
    finished = run_status == "complete" or terminated or bool(termination_reason)
    if finished:
        if termination_reason and termination_reason != "completed":
            header_bits.append(f"finished ({termination_reason})")
        else:
            header_bits.append("finished")
    else:
        header_bits.append("running")
    fig.suptitle("  •  ".join(header_bits), fontsize=10)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return len(plottable), terminated


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("--out", default=None)
    p.add_argument("--watch", type=float, nargs="?", const=30.0, default=None,
                   metavar="SECONDS",
                   help="refresh interval in seconds; bare --watch means 30s")
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    stats_csv = run_dir / "stats.csv"
    summary_json = run_dir / "summary.json"
    out = Path(args.out) if args.out else run_dir / "plot.png"

    if args.watch is None:
        if not stats_csv.exists():
            raise SystemExit(f"no stats.csv at {stats_csv}")
        n, _ = render(stats_csv, summary_json, out)
        if n == 0:
            raise SystemExit(f"no plottable rows in {stats_csv}")
        print(f"wrote {out} ({n} rows)")
        return

    interval = max(0.5, args.watch)
    while not stats_csv.exists():
        time.sleep(interval)
    last_n = -1
    last_mtime = -1.0
    while True:
        mtime = stats_csv.stat().st_mtime
        if mtime != last_mtime:
            last_mtime = mtime
            n, terminated = render(stats_csv, summary_json, out)
            if n != last_n:
                print(f"wrote {out} ({n} rows)")
                last_n = n
            if terminated:
                return
        time.sleep(interval)


if __name__ == "__main__":
    main()
