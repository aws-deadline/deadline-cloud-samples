"""Solve one point of the maximum independent set schedule sweep.

Runs a single Analog Hamiltonian Simulation on the free local simulator for one
combination of anneal time, final detuning, and graph instance, then scores the
shots against an exact classical solver and writes one JSON result file.
"""

import argparse
import shlex
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahs_mis  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--anneal-index", type=int, required=True)
    parser.add_argument("--anneal-points", type=int, required=True)
    parser.add_argument("--anneal-min-microseconds", type=float, required=True)
    parser.add_argument("--anneal-max-microseconds", type=float, required=True)
    parser.add_argument("--detuning-index", type=int, required=True)
    parser.add_argument("--detuning-points", type=int, required=True)
    parser.add_argument("--detuning-min-megarad", type=float, required=True)
    parser.add_argument("--detuning-max-megarad", type=float, required=True)
    parser.add_argument("--graph-seed", type=int, required=True)
    parser.add_argument("--lattice-width", type=int, required=True)
    parser.add_argument("--lattice-height", type=int, required=True)
    parser.add_argument("--dropout", type=float, required=True)
    parser.add_argument("--shots", type=int, required=True)
    parser.add_argument("--time-steps", type=int, required=True)
    # Optional knobs. Reachable from the job template's ExtraSolverArgs
    # parameter, so new dials can be added without editing the template.
    parser.add_argument(
        "--blockade-radius",
        type=float,
        default=0.0,
        help="Project onto the blockade subspace. Much faster, slightly approximate.",
    )
    parser.add_argument("--extra-args", default="")

    argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if args.extra_args.strip():
        # Re-parse with the extras appended so they win over the defaults.
        args = parser.parse_args(argv + shlex.split(args.extra_args))
    return args


def main():
    args = parse_args()

    # Parameters are given in microseconds and Mrad/s for readable GUI controls;
    # the Braket SDK wants seconds and rad/s.
    anneal_time = 1e-6 * ahs_mis.linspace_value(
        args.anneal_index,
        args.anneal_points,
        args.anneal_min_microseconds,
        args.anneal_max_microseconds,
    )
    detuning_end = 1e6 * ahs_mis.linspace_value(
        args.detuning_index,
        args.detuning_points,
        args.detuning_min_megarad,
        args.detuning_max_megarad,
    )

    label = (
        f"anneal={anneal_time * 1e6:.3f}us "
        f"detuning={detuning_end / 1e6:.2f}Mrad/s "
        f"seed={args.graph_seed}"
    )
    ahs_mis.emit_status(f"Building instance for {label}")
    ahs_mis.emit_progress(0.0)

    register, graph, positions = ahs_mis.build_instance(
        args.lattice_width, args.lattice_height, args.dropout, args.graph_seed
    )
    nodes = sorted(positions)

    ahs_mis.emit_status(
        f"Solving classical baseline for {graph.number_of_nodes()} vertices"
    )
    optimum = ahs_mis.exact_max_independent_set(graph)
    ahs_mis.emit_progress(0.1)

    program = ahs_mis.build_program(register, anneal_time, detuning_end)

    ahs_mis.emit_status(
        f"Simulating {graph.number_of_nodes()} atoms, "
        f"{args.time_steps} steps, {args.shots} shots"
    )
    started = time.monotonic()
    # Seed from the task coordinates so a retried task reproduces its shots.
    shot_seed = (
        args.graph_seed * 1_000_003
        + args.anneal_index * 1009
        + args.detuning_index
    ) % (2**31 - 1)
    result = ahs_mis.run_simulation(
        program,
        shots=args.shots,
        time_steps=args.time_steps,
        seed=shot_seed,
        blockade_radius=args.blockade_radius,
    )
    elapsed = time.monotonic() - started
    ahs_mis.emit_progress(0.9)

    selections, shots_with_empty_sites = ahs_mis.decode_shots(result, nodes)
    metrics = ahs_mis.score(selections, graph, len(optimum))

    payload = {
        "anneal_index": args.anneal_index,
        "detuning_index": args.detuning_index,
        "graph_seed": args.graph_seed,
        "anneal_time_seconds": anneal_time,
        "detuning_end_rad_per_second": detuning_end,
        "vertices": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "classical_optimum_size": len(optimum),
        "classical_optimum": sorted(optimum),
        "blockade_radius_metres": ahs_mis.blockade_radius(),
        "lattice_spacing_metres": ahs_mis.LATTICE_SPACING,
        "positions": {str(node): list(positions[node]) for node in nodes},
        "graph_edges": [list(edge) for edge in graph.edges()],
        "shot_seed": shot_seed,
        "blockade_radius_applied": args.blockade_radius,
        "shots_with_empty_sites": shots_with_empty_sites,
        "simulation_seconds": elapsed,
        **metrics,
    }

    out = Path(args.results_dir) / (
        f"point_a{args.anneal_index:03d}"
        f"_d{args.detuning_index:03d}"
        f"_s{args.graph_seed:03d}.json"
    )
    ahs_mis.write_json(out, payload)
    ahs_mis.emit_progress(1.0)

    print(
        f"{label} -> approximation ratio {metrics['approximation_ratio']:.3f}, "
        f"P(optimum) {metrics['probability_of_optimum']:.3f}, "
        f"valid {metrics['valid_fraction']:.3f}, "
        f"optimum size {len(optimum)}, {elapsed:.1f}s"
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # surface the reason in the monitor, not just the log
        print(f"openjd_fail: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        sys.exit(1)
