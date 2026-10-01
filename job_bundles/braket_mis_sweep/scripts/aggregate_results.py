"""Aggregate the sweep into a phase map and a summary.

Reads every per-point JSON file written by solve_point.py, averages the
approximation ratio across graph instances, and writes a two panel figure plus
a machine readable summary.
"""

import argparse
import json
import sys
import traceback
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import ahs_mis  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True)
    return parser.parse_args()


def load_points(results_dir: Path):
    files = sorted(results_dir.glob("point_*.json"))
    if not files:
        raise FileNotFoundError(f"no point_*.json files found under {results_dir}")
    points = []
    for path in files:
        try:
            points.append(json.loads(path.read_text()))
        except json.JSONDecodeError as exc:
            print(f"Skipping unreadable {path.name}: {exc}")
    if not points:
        raise ValueError("every result file failed to parse")
    print(f"Loaded {len(points)} of {len(files)} result files")
    return points


def build_grid(points, metric):
    """Average `metric` over graph seeds for each (anneal, detuning) cell."""
    anneal_indices = sorted({p["anneal_index"] for p in points})
    detuning_indices = sorted({p["detuning_index"] for p in points})

    buckets = defaultdict(list)
    for p in points:
        buckets[(p["anneal_index"], p["detuning_index"])].append(p[metric])

    grid = np.full((len(detuning_indices), len(anneal_indices)), np.nan)
    for (a, d), values in buckets.items():
        grid[detuning_indices.index(d), anneal_indices.index(a)] = float(np.mean(values))

    anneal_axis = [
        next(p["anneal_time_seconds"] for p in points if p["anneal_index"] == a) * 1e6
        for a in anneal_indices
    ]
    detuning_axis = [
        next(p["detuning_end_rad_per_second"] for p in points if p["detuning_index"] == d) / 1e6
        for d in detuning_indices
    ]
    return grid, anneal_axis, detuning_axis


def plot(grid, anneal_axis, detuning_axis, best, out_path: Path):
    fig, (heat, graph_ax) = plt.subplots(1, 2, figsize=(14, 5.5))

    mesh = heat.imshow(
        grid,
        origin="lower",
        aspect="auto",
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        extent=[
            min(anneal_axis),
            max(anneal_axis),
            min(detuning_axis),
            max(detuning_axis),
        ],
    )
    fig.colorbar(mesh, ax=heat, label="approximation ratio (1.0 = optimal)")
    heat.set_xlabel("anneal time (microseconds)")
    heat.set_ylabel("final detuning (Mrad/s)")
    heat.set_title("Schedule quality, averaged over graph instances")
    heat.plot(
        best["anneal_time_seconds"] * 1e6,
        best["detuning_end_rad_per_second"] / 1e6,
        marker="*",
        markersize=18,
        color="red",
        markeredgecolor="white",
        linestyle="none",
        label="best schedule",
        # The best point often sits on an axis limit; do not clip the marker.
        clip_on=False,
        zorder=5,
    )
    heat.legend(loc="lower right")

    # Right panel: the instance solved at the best schedule, with the exact
    # classical optimum highlighted.
    positions = {int(k): tuple(v) for k, v in best["positions"].items()}
    optimum = set(best["classical_optimum"])
    xs = np.array([positions[n][0] for n in sorted(positions)]) * 1e6
    ys = np.array([positions[n][1] for n in sorted(positions)]) * 1e6

    for u, v in best["graph_edges"]:
        graph_ax.plot(
            [positions[u][0] * 1e6, positions[v][0] * 1e6],
            [positions[u][1] * 1e6, positions[v][1] * 1e6],
            color="0.75",
            linewidth=1.2,
            zorder=1,
        )

    in_set = [n in optimum for n in sorted(positions)]
    graph_ax.scatter(
        xs[np.array(in_set)],
        ys[np.array(in_set)],
        s=260,
        color="crimson",
        edgecolor="black",
        zorder=2,
        label=f"maximum independent set ({len(optimum)} vertices)",
    )
    graph_ax.scatter(
        xs[~np.array(in_set)],
        ys[~np.array(in_set)],
        s=260,
        color="white",
        edgecolor="black",
        zorder=2,
        label="excluded",
    )
    for n in sorted(positions):
        graph_ax.annotate(
            str(n),
            (positions[n][0] * 1e6, positions[n][1] * 1e6),
            ha="center",
            va="center",
            fontsize=8,
            zorder=3,
        )

    graph_ax.set_xlabel("x (micrometres)")
    graph_ax.set_ylabel("y (micrometres)")
    graph_ax.set_title(
        f"Instance seed {best['graph_seed']}: "
        f"{best['vertices']} vertices, {best['edges']} edges"
    )
    graph_ax.set_aspect("equal")
    graph_ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=False)

    fig.suptitle(
        "Maximum independent set by analog Hamiltonian simulation, "
        "swept across annealing schedules",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Wrote {out_path}")


def main():
    args = parse_args()
    results_dir = Path(args.results_dir)

    ahs_mis.emit_status("Loading sweep results")
    ahs_mis.emit_progress(0.1)
    points = load_points(results_dir)

    ahs_mis.emit_status("Averaging across graph instances")
    grid, anneal_axis, detuning_axis = build_grid(points, "approximation_ratio")

    best = max(
        points,
        key=lambda p: (p["approximation_ratio"], p["probability_of_optimum"]),
    )
    ahs_mis.emit_progress(0.5)

    ahs_mis.emit_status("Rendering figure")
    plot(grid, anneal_axis, detuning_axis, best, results_dir / "mis_schedule_map.png")

    total_sim_seconds = sum(p["simulation_seconds"] for p in points)
    # A point "found" the optimum if any valid shot reached the classical
    # optimum size. Requiring the mean to reach it would be a much stronger
    # claim and would read as zero on almost every real sweep.
    found_optimum = [
        p for p in points if p["best_set_size"] >= p["classical_optimum_size"] > 0
    ]
    reliable = [p for p in points if p["probability_of_optimum"] >= 0.5]
    summary = {
        "points": len(points),
        "total_simulation_seconds": total_sim_seconds,
        "mean_simulation_seconds": total_sim_seconds / len(points),
        "graph_seeds": sorted({p["graph_seed"] for p in points}),
        "vertices": sorted({p["vertices"] for p in points}),
        "best_point": {
            "anneal_time_microseconds": best["anneal_time_seconds"] * 1e6,
            "detuning_end_megarad_per_second": best["detuning_end_rad_per_second"] / 1e6,
            "graph_seed": best["graph_seed"],
            "approximation_ratio": best["approximation_ratio"],
            "probability_of_optimum": best["probability_of_optimum"],
            "valid_fraction": best["valid_fraction"],
            "classical_optimum_size": best["classical_optimum_size"],
        },
        "points_that_found_optimum": len(found_optimum),
        "points_finding_optimum_in_most_shots": len(reliable),
        "mean_approximation_ratio": float(
            np.mean([p["approximation_ratio"] for p in points])
        ),
        "mean_valid_fraction": float(np.mean([p["valid_fraction"] for p in points])),
    }
    ahs_mis.write_json(results_dir / "summary.json", summary)

    print()
    print(f"Swept {summary['points']} points over {len(summary['graph_seeds'])} instances")
    print(f"Mean approximation ratio: {summary['mean_approximation_ratio']:.3f}")
    print(f"Mean valid-shot fraction: {summary['mean_valid_fraction']:.3f}")
    print(
        f"Best schedule: {summary['best_point']['anneal_time_microseconds']:.3f} us, "
        f"{summary['best_point']['detuning_end_megarad_per_second']:.2f} Mrad/s "
        f"-> ratio {summary['best_point']['approximation_ratio']:.3f}"
    )
    print(
        f"{summary['points_that_found_optimum']} of {summary['points']} points found "
        "the exact classical optimum in at least one shot"
    )
    print(
        f"{summary['points_finding_optimum_in_most_shots']} of {summary['points']} points "
        "found it in a majority of shots"
    )
    print(f"Total simulator time across all tasks: {total_sim_seconds:.1f}s")
    ahs_mis.emit_progress(1.0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"openjd_fail: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        sys.exit(1)
