"""Compare two p9solve stats/summary artifacts and print divergence points."""

import argparse
import json
from pathlib import Path
from statistics import mean


COMPARE_KEYS = (
    "stage",
    "iteration",
    "side",
    "parity",
    "new_swaps",
    "total_swaps",
    "absorb_side",
    "it_left",
    "it_right",
    "u_consumed_total",
    "u_consumed",
    "swap_consumed",
    "max_bond",
    "total_elems",
    "total_shapes",
    "remaining_layers_before_rewire",
    "rewire_side",
    "rewire_phase",
)


def load_json(path):
    with Path(path).open() as handle:
        return json.load(handle)


def summarize(label, rows):
    cycle_rows = [row for row in rows if row.get("stage") == "cycle_progress"]
    rewire_rows = [
        row for row in rows
        if row.get("stage") == "rewiring" and row.get("rewire_phase") == "post_unswap"
    ]
    rescue_rows = [row for row in rewire_rows if row.get("no_progress_rescue_rewire")]
    normal_rows = [row for row in rewire_rows if not row.get("no_progress_rescue_rewire")]
    print(f"{label}:")
    print(f"  cycles: {len(cycle_rows)}")
    print(f"  final work: {cycle_rows[-1].get('gates_consumed') if cycle_rows else None}")
    print(f"  rescue cycles: {sorted(set(row.get('unswap_cycle') for row in rescue_rows))}")
    if normal_rows:
        print(f"  normal post-rewire mean: {mean(float(row.get('rewire_time_s', 0.0)) for row in normal_rows):.3f}s")
    if rescue_rows:
        print(f"  rescue post-rewire mean: {mean(float(row.get('rewire_time_s', 0.0)) for row in rescue_rows):.3f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("left_stats")
    parser.add_argument("right_stats")
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    args = parser.parse_args()

    left = load_json(args.left_stats)
    right = load_json(args.right_stats)
    summarize(args.left_label, left)
    summarize(args.right_label, right)

    for index, (left_row, right_row) in enumerate(zip(left, right)):
        diffs = [
            (key, left_row.get(key), right_row.get(key))
            for key in COMPARE_KEYS
            if left_row.get(key) != right_row.get(key)
        ]
        if diffs:
            print(f"\nfirst divergent stats row: {index}")
            for key, left_value, right_value in diffs[:20]:
                print(f"  {key}: {args.left_label}={left_value!r} {args.right_label}={right_value!r}")
            print(f"\n{args.left_label} row: {left_row}")
            print(f"\n{args.right_label} row: {right_row}")
            return
    print("\nNo divergence found in aligned rows.")


if __name__ == "__main__":
    main()
