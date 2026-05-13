#!/usr/bin/env python3
"""Top-bitstring sample chart for a p9solve run.

Renders the top-N most-sampled output bitstrings as a horizontal bar chart,
highlighting the predicted peak. The expected peak (if known) is marked.

Usage:
    uv run python diagnostics/plot_samples.py runs/<tag>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PEAK_COLOR = "#c0392b"
BAR_COLOR = "#5b86b5"


def render(run_dir, out=None, top_n=10):
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())

    top = summary.get("top_permuted_samples") or []
    if not top:
        raise SystemExit(f"no samples in {run_dir}/summary.json (was the run skip-sampling?)")
    top = top[:top_n]
    top.reverse()  # so the largest ends up at the top of the bar chart

    bitstrings = [bs for bs, _ in top]
    counts = [c for _, c in top]
    n_samples = summary.get("samples") or sum(counts)
    predicted = summary.get("predicted_bitstring", "")
    expected = summary.get("expected_bitstring")
    matches = summary.get("matches_expected_bitstring")
    peak_count = summary.get("sample_peak_count", max(counts))
    peak_fraction = summary.get("sample_peak_fraction", peak_count / max(n_samples, 1))
    n_unique = summary.get("sample_unique_permuted", len(set(bitstrings)))

    colors = [PEAK_COLOR if bs == predicted else BAR_COLOR for bs in bitstrings]

    fig, ax = plt.subplots(figsize=(11, max(4, 0.45 * len(top) + 1.4)))
    y = list(range(len(top)))
    bars = ax.barh(y, counts, color=colors, edgecolor="none")
    ax.set_yticks(y)
    ax.set_yticklabels(bitstrings, family="monospace", fontsize=7)
    ax.set_xlabel("Sample count")
    ax.set_xlim(0, max(counts) * 1.18)

    for bar, c in zip(bars, counts):
        ax.text(bar.get_width() + max(counts) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{c}", va="center", fontsize=9, color="#333")

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#eee", zorder=0)
    ax.set_axisbelow(True)

    if matches is True:
        verdict = "matches expected"
        verdict_color = "#1b7e3b"
    elif matches is False:
        verdict = "does NOT match expected"
        verdict_color = PEAK_COLOR
    else:
        verdict = "no expected bitstring set"
        verdict_color = "#666"

    title = (
        f"Top {len(top)} sampled bitstrings  •  "
        f"N = {n_samples:,}  •  unique = {n_unique:,}  •  "
        f"peak count {peak_count} ({100 * peak_fraction:.1f}%)"
    )
    fig.suptitle(title, fontsize=11)
    fig.text(0.5, 0.92, verdict, ha="center", fontsize=10, color=verdict_color)

    if predicted:
        fig.text(0.01, 0.015,
                 f"predicted peak:  {predicted}",
                 family="monospace", fontsize=8, color=PEAK_COLOR)
    if expected and expected != predicted:
        fig.text(0.01, 0.001,
                 f"expected peak:   {expected}",
                 family="monospace", fontsize=8, color="#666")

    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    out = Path(out) if out else run_dir / "samples.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("--out", default=None)
    p.add_argument("--top", type=int, default=10)
    args = p.parse_args()

    out = render(args.run_dir, args.out, args.top)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
