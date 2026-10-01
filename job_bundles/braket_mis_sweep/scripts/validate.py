"""Validation checks for the maximum independent set sweep.

Run before trusting a sweep, after changing the physics, or after a Braket SDK
upgrade:

    python scripts/validate.py

Four independent checks, in order of what they establish:

1. Reference reproduction. Reruns the published 1D Z2 ordered-phase result from
   Braket's own example notebook and compares against externally measured
   values. Validates the simulator build and the shot decoding.
2. Graph correspondence. Confirms the Rydberg blockade at the configured lattice
   spacing produces exactly the edge set the scoring code assumes.
3. Classical baseline. Checks the networkx solver against exhaustive
   enumeration on many instances.
4. End to end. Confirms a long anneal actually recovers the verified optimum,
   and that a negative final detuning does not.
"""

import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahs_mis  # noqa: E402

# Measured independently on amazon-braket-sdk 1.127.3 with numpy seed 0, using
# the register, drive, and run arguments published in notebook 02
# (02_Ordered_phases_in_Rydberg_systems.ipynb).
Z2_REFERENCE_MODAL_STATE = "rgrgrgrgr"
Z2_REFERENCE_DENSITY = np.array(
    [0.855, 0.115, 0.601, 0.334, 0.530, 0.323, 0.616, 0.115, 0.868]
)

failures = []


def check(name: str, passed: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not passed:
        failures.append(name)


def check_reference_reproduction() -> None:
    """Reproduce notebook 02's 1D Z2 phase and compare to measured values."""
    from braket.ahs.analog_hamiltonian_simulation import AnalogHamiltonianSimulation
    from braket.ahs.atom_arrangement import AtomArrangement
    from braket.ahs.driving_field import DrivingField
    from braket.devices import LocalSimulator

    print("\n1. Reference reproduction (notebook 02, 1D Z2 ordered phase)")

    register = AtomArrangement()
    for k in range(9):
        register.add([k * 6.1e-6, 0])

    drive = DrivingField.from_lists(
        [0, 2.5e-7, 2.75e-6, 3e-6],
        [0, 1.57e7, 1.57e7, 0],
        [-5.5e7, -5.5e7, 5.5e7, 5.5e7],
        [0, 0, 0, 0],
    )

    np.random.seed(0)
    result = LocalSimulator("braket_ahs").run(
        AnalogHamiltonianSimulation(register=register, hamiltonian=drive),
        shots=1000,
        blockade_radius=6.7e-6,
        steps=30,
    ).result()

    modal = max(result.get_counts().items(), key=lambda kv: kv[1])
    density = result.get_avg_density()
    deviation = float(np.abs(density - Z2_REFERENCE_DENSITY).max())

    check(
        "modal state is the Z2 antiferromagnet",
        modal[0] == Z2_REFERENCE_MODAL_STATE,
        f"got {modal[0]} at {modal[1]}/1000",
    )
    check(
        "average density matches reference",
        deviation < 0.02,
        f"max deviation {deviation:.4f}",
    )


def check_graph_correspondence() -> None:
    """The blockade must realise exactly the edges the scoring code assumes."""
    print("\n2. Graph correspondence (blockade radius vs assumed edge set)")

    radius = ahs_mis.blockade_radius()
    spacing = ahs_mis.LATTICE_SPACING
    nearest = spacing
    diagonal = spacing * np.sqrt(2)
    next_nearest = 2 * spacing

    check(
        "nearest neighbours are blockaded (edge)",
        nearest < radius,
        f"{nearest * 1e6:.2f} um < {radius * 1e6:.2f} um",
    )
    check(
        "diagonal neighbours are blockaded (edge)",
        diagonal < radius,
        f"{diagonal * 1e6:.2f} um < {radius * 1e6:.2f} um",
    )
    check(
        "next-nearest neighbours are free (no edge)",
        next_nearest > radius,
        f"{next_nearest * 1e6:.2f} um > {radius * 1e6:.2f} um",
    )
    check(
        "lattice spacing respects the Aquila minimum",
        spacing >= ahs_mis.AQUILA_SPACING_MIN,
        f"{spacing * 1e6:.1f} um",
    )


def brute_force_mis(graph):
    nodes = sorted(graph.nodes())
    for size in range(len(nodes), 0, -1):
        for combo in itertools.combinations(nodes, size):
            chosen = set(combo)
            if not any(u in chosen and v in chosen for u, v in graph.edges()):
                return frozenset(combo)
    return frozenset()


def check_classical_baseline() -> None:
    """The networkx solver must agree with exhaustive enumeration."""
    print("\n3. Classical baseline (networkx vs exhaustive enumeration)")

    mismatches = 0
    checked = 0
    for width, height, dropout in [
        (4, 3, 0.25),
        (5, 3, 0.2),
        (4, 4, 0.25),
        (3, 3, 0.0),
        (2, 2, 0.0),
    ]:
        for seed in range(1, 7):
            _, graph, _ = ahs_mis.build_instance(width, height, dropout, seed)
            solver = ahs_mis.exact_max_independent_set(graph)
            brute = brute_force_mis(graph)
            independent = not any(
                u in solver and v in solver for u, v in graph.edges()
            )
            checked += 1
            if len(solver) != len(brute) or not independent:
                mismatches += 1

    check(
        "solver is exact and returns independent sets",
        mismatches == 0,
        f"{checked} instances, {mismatches} mismatches",
    )


def check_end_to_end() -> None:
    """A long anneal should recover the verified optimum; a negative one should not."""
    print("\n4. End to end (does the anneal find the proven optimum?)")

    register, graph, positions = ahs_mis.build_instance(4, 3, 0.25, 1)
    optimum = ahs_mis.exact_max_independent_set(graph)
    nodes = sorted(positions)

    good = ahs_mis.score(
        *ahs_mis.decode_shots(
            ahs_mis.run_simulation(
                ahs_mis.build_program(register, 3.8e-6, 6.0e7),
                shots=1000, time_steps=150, seed=11,
            ),
            nodes,
        )[:1],
        graph,
        len(optimum),
    )
    bad = ahs_mis.score(
        *ahs_mis.decode_shots(
            ahs_mis.run_simulation(
                ahs_mis.build_program(register, 3.8e-6, -2.0e7),
                shots=1000, time_steps=150, seed=11,
            ),
            nodes,
        )[:1],
        graph,
        len(optimum),
    )

    check(
        "positive detuning finds the optimum in most shots",
        good["probability_of_optimum"] > 0.5,
        f"P(optimum) = {good['probability_of_optimum']:.3f}, |MIS| = {len(optimum)}",
    )
    check(
        "shots are valid independent sets",
        good["valid_fraction"] > 0.75,
        f"valid = {good['valid_fraction']:.3f}",
    )
    check(
        "negative detuning suppresses excitation (falsification control)",
        bad["approximation_ratio"] < 0.3,
        f"ratio = {bad['approximation_ratio']:.3f}",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        choices=["full", "quick", "skip"],
        default="full",
        help="full adds the independent Schrodinger integration; skip exits immediately.",
    )
    args = parser.parse_args()

    if args.level == "skip":
        print("Validation skipped by request (ValidationLevel=skip).")
        print("openjd_status: validation skipped")
        return 0

    print("Validating the quantum maximum independent set sweep")
    print(f"openjd_status: validating ({args.level})")
    check_reference_reproduction()
    check_graph_correspondence()
    check_classical_baseline()
    check_end_to_end()

    if args.level == "full":
        print("\n5. Independent dynamics check (scipy integration vs simulator)")
        import verify_dynamics

        code = verify_dynamics.main()
        check("independent integration agrees with the simulator", code == 0)

    print()
    if failures:
        print(f"openjd_fail: validation failed: {', '.join(failures)}")
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("All validation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
