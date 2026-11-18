"""Total LIBERO results from every Eval task into one scorecard.

Reads <output>/tasks/*/eval/eval_info.json, written by lerobot-eval, and writes:
  scorecard.json  per-suite and overall success, with per-task detail
  scorecard.csv   one row per suite and task
  tensorboard/<run>/  TensorBoard scalars and HParams, if tensorboard is installed

Exits non-zero when overall success is below --min-success-rate.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

SUITES = ["libero_spatial", "libero_object", "libero_goal", "libero_10"]


def load_tasks(output: Path) -> list[dict]:
    rows = []
    for info_path in sorted(output.glob("tasks/*/eval/eval_info.json")):
        info = json.loads(info_path.read_text())
        worker_path = info_path.parent.parent / "worker.json"
        worker = json.loads(worker_path.read_text()) if worker_path.exists() else {}
        for task in info["per_task"]:
            successes = task["metrics"]["successes"]
            rows.append(
                {
                    "suite": task["task_group"],
                    "task_id": task["task_id"],
                    "episodes": len(successes),
                    "successes": sum(bool(s) for s in successes),
                    "eval_seconds": info["overall"].get("eval_s"),
                    "gpu": worker.get("gpu"),
                }
            )
    return rows


def summarize(rows: list[dict]) -> dict:
    def rate(items):
        episodes = sum(r["episodes"] for r in items)
        return round(100.0 * sum(r["successes"] for r in items) / episodes, 1) if episodes else None

    suites = {}
    for suite in sorted({r["suite"] for r in rows}, key=lambda s: SUITES.index(s) if s in SUITES else 99):
        items = [r for r in rows if r["suite"] == suite]
        suites[suite] = {"success_rate": rate(items), "tasks": len(items), "episodes": sum(r["episodes"] for r in items)}
    return {
        "overall_success_rate": rate(rows),
        "episodes": sum(r["episodes"] for r in rows),
        "tasks": len(rows),
        "suites": suites,
        "gpus": sorted({r["gpu"] for r in rows if r["gpu"]}),
        "task_eval_seconds_total": round(sum(r["eval_seconds"] or 0 for r in rows)),
        "per_task": rows,
    }


def write_tensorboard(output: Path, card: dict, run_name: str, hparams: dict) -> bool:
    """Write TensorBoard logs under tensorboard/<run_name>.

    - task_success/<suite>: one point per task, with the task index as the step,
      so tasks that fail stand out.
    - HParams: this job's policy and settings next to its overall and per-suite
      success rates, so jobs that test different settings line up in one table.
      Each of those rates is a single number, so it is logged only here and not
      as its own Scalars chart.
    """
    try:
        from torch.utils.tensorboard import SummaryWriter
    except ImportError:
        return False
    writer = SummaryWriter(log_dir=str(output / "tensorboard" / run_name))
    for row in sorted(card["per_task"], key=lambda r: (r["suite"], r["task_id"])):
        if row["episodes"]:
            writer.add_scalar(f"task_success/{row['suite']}", 100.0 * row["successes"] / row["episodes"], row["task_id"])
    metrics = {"hparam/overall": card["overall_success_rate"] or 0}
    metrics.update({f"hparam/{suite}": values["success_rate"] or 0 for suite, values in card["suites"].items()})
    writer.add_hparams({"policy": card["policy"], **hparams}, metrics, run_name=".")
    writer.close()
    return True


def parse_hparams(pairs: list[str]) -> dict:
    """Turn KEY=VALUE strings into a dict, converting integer values."""
    result = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        result[key] = int(value) if value.lstrip("-").isdigit() else value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("--policy", default="")
    parser.add_argument("--min-success-rate", type=float, default=0.0)
    parser.add_argument("--run-name", default="", help="TensorBoard run name. Defaults to the policy name.")
    parser.add_argument("--hparam", action="append", default=[], metavar="KEY=VALUE",
                        help="A setting to show in TensorBoard's HParams view. Repeat for each setting.")
    args = parser.parse_args()
    run_name = args.run_name or (args.policy.replace("/", "_") or "run")

    rows = load_tasks(args.output)
    if not rows:
        print(f"No eval_info.json files found under {args.output}/tasks", file=sys.stderr)
        return 1
    card = {"policy": args.policy, **summarize(rows)}
    (args.output / "scorecard.json").write_text(json.dumps(card, indent=2))
    with (args.output / "scorecard.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["suite", "task_id", "episodes", "successes", "eval_seconds", "gpu"])
        writer.writeheader()
        writer.writerows(rows)
    has_tb = write_tensorboard(args.output, card, run_name, parse_hparams(args.hparam))

    def pct(value):
        return "  n/a" if value is None else f"{value:5.1f}%"

    print(f"Policy: {args.policy}")
    for suite, values in card["suites"].items():
        print(f"  {suite:15s} {pct(values['success_rate'])}  ({values['tasks']} tasks, {values['episodes']} episodes)")
    print(f"  {'overall':15s} {pct(card['overall_success_rate'])}  ({card['episodes']} episodes)")
    print(f"TensorBoard logs written to tensorboard/{run_name}" if has_tb else "TensorBoard not installed; skipped.")

    if args.min_success_rate and (card["overall_success_rate"] or 0) < args.min_success_rate:
        print(f"FAIL: overall success {card['overall_success_rate']}% is below {args.min_success_rate}%", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
