#!/usr/bin/env python3
"""Aggregate per-model lm-eval-harness JSON results into a leaderboard.

Reads all `results_*.json` files under <results-dir>/**/, extracts each
benchmark's best-available accuracy metric, and writes:
  - leaderboard.csv — one row per model, one column per benchmark
  - leaderboard.md — same data as a ranked Markdown table
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path


METRIC_PRIORITY = [
    "acc_norm,none",
    "acc,none",
    "exact_match,strict-match",
    "exact_match,flexible-extract",
]


def extract_metric(task_results: dict):
    for metric in METRIC_PRIORITY:
        if metric in task_results:
            return metric.split(",")[0], float(task_results[metric])
    for k, v in task_results.items():
        if isinstance(v, (int, float)) and not k.endswith("_stderr,none"):
            return k.split(",")[0], float(v)
    return None


def parse_results_file(path: Path):
    data = json.loads(path.read_text())
    model = data.get("model_name") or str(data.get("config", {}).get("model_args", "unknown"))
    m = re.search(r"model=([^,]+)", model)
    if m:
        model = m.group(1)
    scores = {}
    for bench, results in data.get("results", {}).items():
        extracted = extract_metric(results)
        if extracted:
            scores[bench] = extracted
    return model, scores


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True, type=Path)
    args = ap.parse_args()

    results_dir: Path = args.results_dir
    if not results_dir.exists():
        print(f"ERROR: results dir {results_dir} does not exist", file=sys.stderr)
        return 1

    by_model: dict = {}
    for json_path in sorted(results_dir.rglob("results_*.json")):
        try:
            model, scores = parse_results_file(json_path)
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"WARN: skipping malformed {json_path.relative_to(results_dir)}: {e}", file=sys.stderr)
            continue
        print(f"Parsed {json_path.relative_to(results_dir)}: {model} -> {list(scores.keys())}")
        by_model.setdefault(model, {}).update(scores)

    if not by_model:
        print(f"ERROR: no results_*.json files found under {results_dir}", file=sys.stderr)
        return 1

    all_benchmarks = sorted({b for scores in by_model.values() for b in scores})

    rows = []
    for model, scores in by_model.items():
        row = {"model": model}
        vals = []
        for bench in all_benchmarks:
            if bench in scores:
                _, v = scores[bench]
                row[bench] = v
                vals.append(v)
            else:
                row[bench] = None
        row["mean"] = sum(vals) / len(vals) if vals else 0.0
        rows.append(row)
    rows.sort(key=lambda r: r["mean"], reverse=True)

    csv_path = results_dir / "leaderboard.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model"] + all_benchmarks + ["mean"])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                k: (f"{v:.4f}" if isinstance(v, float) else ("N/A" if v is None else v))
                for k, v in row.items()
            })
    print(f"\nWrote {csv_path}")

    md = ["# LLM Leaderboard", ""]
    md.append(f"Models: {len(rows)} | Benchmarks: {', '.join(all_benchmarks)}")
    md.append("")
    md.append("| Rank | Model | " + " | ".join(all_benchmarks) + " | **Mean** |")
    md.append("|------|-------|" + "|".join(["-----"] * (len(all_benchmarks) + 1)) + "|")
    for i, row in enumerate(rows, 1):
        cells = [f"{row[b]:.4f}" if row[b] is not None else "—" for b in all_benchmarks]
        md.append(f"| {i} | `{row['model']}` | " + " | ".join(cells) + f" | **{row['mean']:.4f}** |")
    md_path = results_dir / "leaderboard.md"
    md_path.write_text("\n".join(md) + "\n")
    print(f"Wrote {md_path}")
    print("\n" + "\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
