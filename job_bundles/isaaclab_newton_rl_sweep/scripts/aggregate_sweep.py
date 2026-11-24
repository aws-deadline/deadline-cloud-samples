"""Collect every sweep run's metrics, rank them, and publish the winning policy.

The TrainSweep step writes one directory per hyperparameter combination under
``<output-dir>/runs/``. This step runs once afterwards and produces:

* ``results.csv``     one ranked row per run
* ``report.html``     the same table with a bar chart, self-contained
* ``best_policy/``    the winning run's checkpoints and the hyperparameters behind them

Metrics are read from the TensorBoard event files rsl_rl writes, so they are the values the
training loop recorded rather than parsed stdout. Each run's ``config.json`` supplies its
hyperparameters, so they are never inferred from directory names.

A run with no event file is reported as ``no-metrics`` and ranked last, so one failed task
still leaves the remaining results usable.
"""

import argparse
import csv
import html
import json
import os
import shutil
import sys

# Tags rsl_rl 5.x writes, from rsl_rl/utils/logger.py. "Train/mean_reward" is the primary
# learning signal for an on-policy run.
DEFAULT_METRIC = "Train/mean_reward"
REPORTED_METRICS = ("Train/mean_reward", "Train/mean_episode_length", "Perf/total_fps")


def _find_event_file(run_dir):
    """Return the largest TensorBoard event file under run_dir, or None.

    Largest rather than newest: a run that was resumed leaves a near-empty second file, and
    the bigger one holds the history worth reading.
    """
    candidates = []
    for root, _dirs, files in os.walk(run_dir):
        for name in files:
            if name.startswith("events.out.tfevents."):
                path = os.path.join(root, name)
                candidates.append((os.path.getsize(path), path))
    if not candidates:
        return None
    return max(candidates)[1]


def _read_scalars(event_file, tags):
    """Read the requested scalar tags from a TensorBoard event file.

    Returns a dict of tag -> {"final", "best", "steps"}, plus the list of tags the file
    actually contains so a wrong --metric can be reported with the real options.
    """
    from tensorboard.backend.event_processing import event_accumulator

    accumulator = event_accumulator.EventAccumulator(
        event_file, size_guidance={event_accumulator.SCALARS: 0}
    )
    accumulator.Reload()
    available = accumulator.Tags().get("scalars", [])

    out = {}
    for tag in tags:
        if tag not in available:
            continue
        events = accumulator.Scalars(tag)
        if not events:
            continue
        values = [event.value for event in events]
        out[tag] = {"final": values[-1], "best": max(values), "steps": len(values)}
    return out, available


def _collect(runs_dir, metric):
    """Build one record per run directory. Never raises for a single bad run."""
    if not os.path.isdir(runs_dir):
        return [], []

    records = []
    all_available = set()
    for name in sorted(os.listdir(runs_dir)):
        run_dir = os.path.join(runs_dir, name)
        if not os.path.isdir(run_dir):
            continue

        record = {"run": name, "status": "ok"}

        config_path = os.path.join(run_dir, "config.json")
        if os.path.isfile(config_path):
            with open(config_path, encoding="utf8") as handle:
                record.update(json.load(handle))
        else:
            # The training step writes this before training starts, so its absence means the
            # task failed almost immediately.
            record["status"] = "no-config"

        event_file = _find_event_file(run_dir)
        if event_file is None:
            record["status"] = "no-metrics"
            records.append(record)
            continue

        scalars, available = _read_scalars(event_file, REPORTED_METRICS)
        all_available.update(available)
        for tag, stats in scalars.items():
            record[tag] = stats["final"]
            record[tag + " (best)"] = stats["best"]
        record["iterations"] = scalars.get(metric, {}).get("steps", 0)
        if metric not in scalars:
            record["status"] = "metric-missing"
        records.append(record)

    return records, sorted(all_available)


def _write_csv(path, records, columns):
    with open(path, "w", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def _write_html(path, records, columns, metric, best):
    """Write a self-contained report. No external CSS or JS: job output is read offline."""
    values = [r.get(metric) for r in records if isinstance(r.get(metric), (int, float))]
    span = (min(values), max(values)) if values else (0.0, 1.0)
    spread = (span[1] - span[0]) or 1.0

    rows = []
    for record in records:
        cells = []
        for column in columns:
            value = record.get(column, "")
            if isinstance(value, float):
                value = "{:.4f}".format(value)
            cells.append("<td>{}</td>".format(html.escape(str(value))))
        value = record.get(metric)
        if isinstance(value, (int, float)):
            width = 100.0 * (value - span[0]) / spread
            bar = '<div class="bar" style="width:{:.1f}%"></div>'.format(max(width, 1.0))
        else:
            bar = '<span class="miss">{}</span>'.format(html.escape(str(record.get("status", ""))))
        winner = ' class="win"' if record is best else ""
        rows.append("<tr{}>{}<td class='barcell'>{}</td></tr>".format(winner, "".join(cells), bar))

    headers = "".join("<th>{}</th>".format(html.escape(c)) for c in columns)
    summary = "no run produced the ranking metric"
    if best is not None:
        summary = "Best run <code>{}</code> with {} = {:.4f}".format(
            html.escape(str(best.get("run"))), html.escape(metric), best.get(metric, float("nan"))
        )

    with open(path, "w", encoding="utf8") as handle:
        handle.write(
            """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Isaac Lab Newton sweep results</title>
<style>
 body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #111; }}
 h1 {{ font-size: 1.3rem; }}
 table {{ border-collapse: collapse; font-size: 0.85rem; width: 100%; }}
 th, td {{ border-bottom: 1px solid #ddd; padding: 0.35rem 0.6rem; text-align: right; }}
 th:first-child, td:first-child {{ text-align: left; font-family: ui-monospace, monospace; }}
 thead th {{ background: #f4f4f4; text-align: right; }}
 tr.win {{ background: #eaf7ea; font-weight: 600; }}
 .barcell {{ width: 25%; }}
 .bar {{ background: #4a7fd4; height: 0.75rem; border-radius: 2px; }}
 .miss {{ color: #a00; font-size: 0.75rem; }}
 p.summary {{ background: #f4f4f4; padding: 0.6rem 0.8rem; border-left: 3px solid #4a7fd4; }}
</style></head><body>
<h1>Isaac Lab 3.0 Newton PPO sweep</h1>
<p class="summary">{summary}. Ranked by <code>{metric}</code> over {count} runs.</p>
<table><thead><tr>{headers}<th>{metric}</th></tr></thead><tbody>
{rows}
</tbody></table>
</body></html>
""".format(
                summary=summary,
                metric=html.escape(metric),
                count=len(records),
                headers=headers,
                rows="\n".join(rows),
            )
        )


def _publish_best(run_dir, destination, record):
    """Copy the winning run's checkpoints and the config that produced them."""
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)

    copied = 0
    for root, _dirs, files in os.walk(run_dir):
        for name in files:
            if name.endswith(".pt"):
                shutil.copy2(os.path.join(root, name), os.path.join(destination, name))
                copied += 1
    with open(os.path.join(destination, "metadata.json"), "w", encoding="utf8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Shared job output directory.")
    parser.add_argument(
        "--metric",
        default=DEFAULT_METRIC,
        help="Scalar tag to rank runs by. Default: {}".format(DEFAULT_METRIC),
    )
    parser.add_argument(
        "--mode",
        choices=("final", "best"),
        default="final",
        help="Rank on the last recorded value or the run's best. Default: final.",
    )
    args = parser.parse_args()

    runs_dir = os.path.join(args.output_dir, "runs")
    metric = args.metric if args.mode == "final" else args.metric + " (best)"
    records, available = _collect(runs_dir, args.metric)

    if not records:
        print(
            "ERROR: no run directories under {}. The TrainSweep step produced nothing, so "
            "there is nothing to aggregate.".format(runs_dir),
            file=sys.stderr,
        )
        return 1

    ranked = sorted(
        records,
        key=lambda r: (isinstance(r.get(metric), (int, float)), r.get(metric, float("-inf"))),
        reverse=True,
    )
    for position, record in enumerate(ranked, start=1):
        record["rank"] = position

    scored = [r for r in ranked if isinstance(r.get(metric), (int, float))]
    if not scored:
        print(
            "ERROR: no run recorded {!r}. Tags present across runs: {}".format(
                metric, ", ".join(available) or "(none)"
            ),
            file=sys.stderr,
        )
        return 1

    columns = ["rank", "run", "status", "learning_rate", "entropy_coef", "seed", "iterations"]
    columns += [c for c in REPORTED_METRICS if any(c in r for r in records)]

    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = os.path.join(args.output_dir, "results.csv")
    html_path = os.path.join(args.output_dir, "report.html")
    _write_csv(csv_path, ranked, columns)

    best = scored[0]
    _write_html(html_path, ranked, columns, metric, best)
    copied = _publish_best(
        os.path.join(runs_dir, best["run"]), os.path.join(args.output_dir, "best_policy"), best
    )

    failed = [r for r in records if r.get("status") != "ok"]
    print("aggregated {} runs, {} with metrics".format(len(records), len(scored)))
    for record in ranked:
        value = record.get(metric)
        shown = "{:.4f}".format(value) if isinstance(value, (int, float)) else record.get("status")
        print("  {:>2}. {:<34} {}".format(record["rank"], record["run"], shown))
    if failed:
        print("{} run(s) did not report metrics: {}".format(
            len(failed), ", ".join(r["run"] for r in failed)))
    print("wrote {}".format(csv_path))
    print("wrote {}".format(html_path))
    print("published {} checkpoint file(s) to best_policy/".format(copied))
    if copied == 0:
        # Ranking succeeded but there is no policy to hand downstream.
        print("WARNING: the winning run has no .pt checkpoint. Check save_interval against "
              "max_iterations.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
