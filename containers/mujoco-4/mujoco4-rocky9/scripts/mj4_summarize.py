#!/usr/bin/env python3
"""Summarize the metrics.json files that mj4-sweep writes, one row per sweep point.

Usage: mj4-summarize [--csv PATH] DIR_OR_FILE...

The sweep type comes from each file's "sweep" field. A directory holding both
types prints one table for each.
"""

import argparse
import csv
import json
import pathlib
import sys

COLUMNS = {
    "torsion": (
        ("label", "label"),
        ("yield", "params.yield_strain"),
        ("peak_deg", "results.peak_twist_deg"),
        ("final_deg", "results.final_twist_deg"),
        ("elastic_final_deg", "results.elastic_final_twist_deg"),
        ("plastic_l1", "results.final_plastic_strain_l1"),
        ("frames", "frames"),
        ("gpu", "render.gpu"),
        ("s_per_frame", "render.seconds_per_frame"),
        ("wall_s", "wall_seconds"),
    ),
    "cradle": (
        ("label", "label"),
        ("angle", "params.release_angle_deg"),
        ("dt_ms", "params.timestep_ms"),
        ("speculative", "params.speculative"),
        ("travel_mm", "results.travel_per_step_mm"),
        ("plate_mm", "results.plate_thickness_mm"),
        ("gap_mm", "results.gap_mm"),
        ("tunneled", "results.tunneled"),
        ("first_tunnel_s", "results.first_tunnel_s"),
        ("frames", "frames"),
        ("gpu", "render.gpu"),
        ("s_per_frame", "render.seconds_per_frame"),
        ("wall_s", "wall_seconds"),
    ),
}


def lookup(metrics, dotted):
    """The value at a dotted path, or None when it is missing, as in files from an older mj4-sweep."""
    value = metrics
    for key in dotted.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def load(paths):
    """Read every metrics.json given, or found under a given directory. Skip unreadable files."""
    files = [f for p in paths for f in (sorted(p.glob("**/metrics.json")) if p.is_dir() else [p])]
    rows = {sweep: [] for sweep in COLUMNS}
    for path in files:
        try:
            metrics = json.loads(path.read_text())
            columns = COLUMNS[metrics["sweep"]]
            row = [lookup(metrics, dotted) for _, dotted in columns]
            # The parameter columns are the sort key, so they must be present.
            if any(v is None for v in row[1:4]):
                raise ValueError("missing a sweep parameter")
            rows[metrics["sweep"]].append(row)
        except (OSError, ValueError, KeyError, TypeError) as err:
            print(f"skipping {path}: {err!r}", file=sys.stderr)
    return {sweep: sorted(r, key=lambda row: row[1:4]) for sweep, r in rows.items() if r}


def print_table(sweep, rows):
    header = [name for name, _ in COLUMNS[sweep]]
    cells = [header] + [["-" if v is None else str(v) for v in row] for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(header))]
    for row in cells:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))


def print_cradle_verdict(rows):
    """Count the runs that tunnelled with speculative contacts off and on."""
    index = {name: i for i, (name, _) in enumerate(COLUMNS["cradle"])}
    for flag in ("disable", "enable"):
        group = [r for r in rows if r[index["speculative"]] == flag]
        if not group:
            continue
        tunneled = sum(1 for r in group if r[index["tunneled"]])
        print(f"speculative {flag}: {tunneled} of {len(group)} runs tunnelled")


def main():
    parser = argparse.ArgumentParser(description="Summarize mj4-sweep metrics.json files.")
    parser.add_argument("--csv", type=pathlib.Path,
                        help="Also write the rows to this CSV file. With both sweeps present, "
                             "each gets its own file with the sweep name before the suffix.")
    parser.add_argument("paths", nargs="+", type=pathlib.Path, help="metrics.json files or directories to search.")
    args = parser.parse_args()

    tables = load(args.paths)
    if not tables:
        print("no readable metrics.json found", file=sys.stderr)
        return 1

    for sweep, rows in tables.items():
        print(f"== {sweep}: {len(rows)} points")
        print_table(sweep, rows)
        if sweep == "cradle":
            print_cradle_verdict(rows)
        if args.csv:
            out = args.csv if len(tables) == 1 else args.csv.with_name(f"{args.csv.stem}-{sweep}{args.csv.suffix}")
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(name for name, _ in COLUMNS[sweep])
                writer.writerows(rows)
            print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
