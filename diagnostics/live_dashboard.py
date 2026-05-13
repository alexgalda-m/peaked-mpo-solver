#!/usr/bin/env python3
"""Live progress dashboard for an in-flight p9solve run.

Tails a `run.log` (or a `runs/<tag>/` directory) and renders a single rich
panel that updates each cycle: work-gate progress bar, current cycle / MPO
stats, last rewire time, recent peak total_elems sparkline. Read-only — no
solver changes required.

Usage:
    uv run python diagnostics/live_dashboard.py runs/<tag>/run.log
    uv run python diagnostics/live_dashboard.py runs/<tag>             # auto-locates run.log
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

TOTAL_GATES = 1885  # P9 fixed

RE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
RE_STEP = re.compile(r"t_u: (\d+)/1885.*max_bond': (\d+).*total_elems': (\d+)")
RE_UNSWAP_START = re.compile(
    r"\[start unswap\].*max_bond': (\d+).*total_elems': (\d+)"
)
RE_REWIRE_END = re.compile(
    r"end rewire\]\(phase=post_unswap, cycle=(\d+), side=(left|right), "
    r"routed_layers=(\d+), elapsed_s=([\d.]+)"
)
RE_TERM = re.compile(
    r"(aborting after .* no-progress|matches_expected_bitstring|Traceback|^.*Error:|^FAILED|^Killed)"
)


def parse_ts(line: str):
    m = RE_TS.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")


class State:
    def __init__(self):
        self.t0 = None
        self.last_ts = None
        self.last_t_u = 0
        self.last_mb = 0
        self.last_te = 0
        self.peak_te = 0
        self.cycle = 0
        self.last_rewire_left_s = None
        self.last_rewire_right_s = None
        self.last_rewire_total_s = None
        self.te_history = []  # for sparkline (cycle peaks)
        self.no_progress_cycles = 0
        self.last_event = "starting"
        self.terminal = None

    def ingest(self, line: str):
        ts = parse_ts(line)
        if ts:
            self.last_ts = ts
            if self.t0 is None:
                self.t0 = ts

        m = RE_STEP.search(line)
        if m:
            self.last_t_u = int(m.group(1))
            self.last_mb = int(m.group(2))
            self.last_te = int(m.group(3))
            if self.last_te > self.peak_te:
                self.peak_te = self.last_te

        m = RE_UNSWAP_START.search(line)
        if m:
            self.cycle += 1
            self.last_event = f"cycle {self.cycle} unswap"

        m = RE_REWIRE_END.search(line)
        if m:
            cyc, side, _routed, elapsed = m.groups()
            elapsed = float(elapsed)
            if side == "left":
                self.last_rewire_left_s = elapsed
            else:
                self.last_rewire_right_s = elapsed
                total = (self.last_rewire_left_s or 0) + elapsed
                self.last_rewire_total_s = total
                self.te_history.append(self.last_te)
                self.te_history = self.te_history[-60:]
                self.last_event = f"cycle {cyc} done"

        if "no_progress" in line and "consumed zero" in line:
            # not a thing we expect with rescue removed, but track for safety
            pass

        m = RE_TERM.search(line)
        if m:
            tail = line.strip()[-160:]
            self.terminal = tail

    @property
    def elapsed_s(self):
        if not (self.t0 and self.last_ts):
            return 0
        return (self.last_ts - self.t0).total_seconds()


def sparkline(values):
    if not values:
        return ""
    glyphs = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    if mx == mn:
        return glyphs[3] * len(values)
    out = []
    for v in values:
        idx = int((v - mn) / (mx - mn) * (len(glyphs) - 1))
        out.append(glyphs[idx])
    return "".join(out)


def render(state: State, log_path: Path) -> Panel:
    pct = 100.0 * state.last_t_u / TOTAL_GATES if state.last_t_u else 0

    bar = Progress(
        TextColumn("[bold]work[/]"),
        BarColumn(bar_width=None, complete_style="green", finished_style="bright_green"),
        TextColumn("[bold]{task.completed}/{task.total}[/]"),
        TextColumn("({task.percentage:>5.1f}%)"),
        TimeElapsedColumn(),
        expand=True,
    )
    task = bar.add_task("work", total=TOTAL_GATES, completed=state.last_t_u)
    _ = task

    stats = Table.grid(padding=(0, 2))
    stats.add_column(style="bold cyan")
    stats.add_column(style="white")
    stats.add_column(style="bold cyan")
    stats.add_column(style="white")
    stats.add_row(
        "cycle", f"{state.cycle}",
        "elapsed", f"{state.elapsed_s:.0f} s",
    )
    stats.add_row(
        "t_u (work)", f"{state.last_t_u}/{TOTAL_GATES}  ({pct:.1f}%)",
        "current peak_te", f"{state.peak_te:,}",
    )
    stats.add_row(
        "current max_bond", f"{state.last_mb}",
        "current total_elems", f"{state.last_te:,}",
    )
    rewire_total = state.last_rewire_total_s
    rewire_str = f"{rewire_total:.2f}s" if rewire_total is not None else "—"
    stats.add_row(
        "last rewire (L+R)", rewire_str,
        "event", state.last_event,
    )

    spark = Text(sparkline(state.te_history), style="bright_blue")
    spark_panel = Table.grid()
    spark_panel.add_column(style="bold cyan")
    spark_panel.add_column()
    spark_panel.add_row("cycle-end total_elems  ", spark)

    body = Group(bar, stats, spark_panel)
    if state.terminal:
        body = Group(body, Text(state.terminal, style="bold red"))

    return Panel(
        body,
        title=f"p9solve live dashboard — {log_path.name}",
        border_style="green" if not state.terminal else "red",
    )


def resolve_log_path(p: Path) -> Path:
    if p.is_file():
        return p
    if p.is_dir():
        candidate = p / "run.log"
        if candidate.exists():
            return candidate
    raise SystemExit(f"could not find run.log under {p}")


def follow(path: Path):
    """Yield each newline-terminated line, blocking when EOF reached."""
    with path.open("r", errors="replace") as f:
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.25)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "path",
        type=Path,
        help="Path to run.log or to a runs/<tag>/ directory",
    )
    ap.add_argument(
        "--refresh-hz",
        type=float,
        default=4.0,
        help="Dashboard refresh rate",
    )
    args = ap.parse_args()

    log_path = resolve_log_path(args.path)
    state = State()
    console = Console()

    with Live(render(state, log_path), console=console, refresh_per_second=args.refresh_hz) as live:
        try:
            for line in follow(log_path):
                state.ingest(line)
                live.update(render(state, log_path))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
