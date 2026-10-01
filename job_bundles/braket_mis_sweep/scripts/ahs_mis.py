"""Shared helpers for the maximum independent set sweep.

Builds unit-disk graphs from neutral atom registers, constructs Analog
Hamiltonian Simulation programs that encode the maximum independent set
problem, decodes shot results, and scores them against an exact classical
solver.

All waveform values stay inside QuEra Aquila's published limits so that the
same program can be submitted to hardware without modification, even though
this sample only runs the free local simulator.
"""

import json
import math
from pathlib import Path

import networkx as nx
import numpy as np
from braket.ahs.analog_hamiltonian_simulation import AnalogHamiltonianSimulation
from braket.ahs.atom_arrangement import AtomArrangement
from braket.ahs.driving_field import DrivingField
from braket.timings.time_series import TimeSeries

# van der Waals coefficient for the |70S_1/2> Rydberg state of rubidium 87,
# in rad * m^6 / s. Matches the local simulator's default.
C6 = 5.42e-24

# QuEra Aquila limits, from the device capabilities in the Braket docs. The
# program is kept inside these bounds so it stays hardware-submittable.
AQUILA_RABI_MAX = 1.58e7  # rad / s
AQUILA_RABI_SLEW_MAX = 4e14  # (rad / s) / s
AQUILA_DETUNING_ABS_MAX = 1.25e8  # rad / s
AQUILA_TIME_MAX = 4e-6  # s
AQUILA_TIME_DELTA_MIN = 5e-8  # s
AQUILA_SPACING_MIN = 4e-6  # m

# Chosen so the Rydberg blockade covers nearest and diagonal neighbours on a
# square lattice but not next-nearest neighbours. See blockade_radius().
RABI_MAX = 1.5e7  # rad / s
LATTICE_SPACING = 5.0e-6  # m
DETUNING_START = -1.0e8  # rad / s


def blockade_radius(rabi: float = RABI_MAX, detuning: float = 0.0) -> float:
    """Rydberg blockade radius in metres.

    Two atoms closer than this cannot both be excited, which is what turns the
    register geometry into the edge set of a unit-disk graph.
    """
    # math.hypot rather than sqrt(a**2 + b**2): it avoids intermediate overflow
    # and loses less precision for widely separated magnitudes.
    return (C6 / math.hypot(rabi, detuning)) ** (1.0 / 6.0)


def build_instance(width: int, height: int, dropout: float, seed: int):
    """Build a unit-disk graph instance and its matching atom register.

    Starts from a `width` by `height` square lattice, drops a fraction of the
    sites at random, and keeps the register and the graph consistent. Edges
    connect nearest and diagonal neighbours, which is the King's graph
    topology realised by the blockade at LATTICE_SPACING.

    Returns (register, graph, positions) where positions maps each surviving
    graph node to its (x, y) coordinate in metres.
    """
    if not 0.0 <= dropout < 1.0:
        raise ValueError(f"dropout must be in [0, 1), got {dropout}")
    if LATTICE_SPACING < AQUILA_SPACING_MIN:
        raise ValueError("lattice spacing is below the Aquila minimum")

    rng = np.random.default_rng(seed)

    # Index every lattice site, then build the full King's graph over them.
    sites = {}
    for i in range(width):
        for j in range(height):
            sites[i * height + j] = (i, j)

    full = nx.Graph()
    full.add_nodes_from(sites)
    for node, (i, j) in sites.items():
        for di, dj in ((1, 0), (0, 1), (1, 1), (1, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < width and 0 <= nj < height:
                full.add_edge(node, ni * height + nj)

    # Drop sites at random, keeping at least two so the problem is non-trivial.
    keep_count = max(2, int(round(len(sites) * (1.0 - dropout))))
    kept = sorted(rng.choice(sorted(sites), size=keep_count, replace=False).tolist())

    graph = full.subgraph(kept).copy()

    register = AtomArrangement()
    positions = {}
    for node in kept:
        i, j = sites[node]
        x, y = i * LATTICE_SPACING, j * LATTICE_SPACING
        register.add((x, y))
        positions[node] = (x, y)

    return register, graph, positions


def build_program(register, anneal_time: float, detuning_end: float):
    """Build the AHS program that anneals into the maximum independent set.

    The drive ramps the amplitude up, sweeps the global detuning from strongly
    negative (every atom in its ground state) to `detuning_end`, then ramps the
    amplitude back down. The blockade forbids adjacent excitations, so low
    energy states are independent sets and a positive final detuning rewards
    larger ones.
    """
    if anneal_time > AQUILA_TIME_MAX:
        raise ValueError(f"anneal_time {anneal_time} exceeds Aquila's {AQUILA_TIME_MAX} s")
    if abs(detuning_end) > AQUILA_DETUNING_ABS_MAX:
        raise ValueError(f"detuning_end {detuning_end} exceeds Aquila's detuning range")

    # Keep the amplitude slew inside the device limit, and round the ramp up to
    # the minimum representable time step.
    min_ramp = RABI_MAX / AQUILA_RABI_SLEW_MAX
    ramp = max(AQUILA_TIME_DELTA_MIN, math.ceil(min_ramp / AQUILA_TIME_DELTA_MIN) * AQUILA_TIME_DELTA_MIN)
    if anneal_time <= 2 * ramp:
        raise ValueError(f"anneal_time {anneal_time} is too short for the {ramp} s ramps")

    amplitude = TimeSeries()
    amplitude.put(0.0, 0.0)
    amplitude.put(ramp, RABI_MAX)
    amplitude.put(anneal_time - ramp, RABI_MAX)
    amplitude.put(anneal_time, 0.0)

    detuning = TimeSeries()
    detuning.put(0.0, DETUNING_START)
    detuning.put(ramp, DETUNING_START)
    detuning.put(anneal_time - ramp, detuning_end)
    detuning.put(anneal_time, detuning_end)

    phase = TimeSeries().put(0.0, 0.0).put(anneal_time, 0.0)

    drive = DrivingField(amplitude=amplitude, phase=phase, detuning=detuning)
    return AnalogHamiltonianSimulation(register=register, hamiltonian=drive)


# The local simulator switches from its numpy Runge-Kutta solver to
# scipy.integrate.ode once the Hilbert space exceeds 1000 configurations, which
# happens around 10 atoms. The scipy path fails outright with "Try to increase
# the allowed number of substeps" unless nsteps is raised well above its default
# of 1000. Passing it unconditionally costs nothing when the numpy path is used.
SOLVER_SUBSTEPS = 10000


def run_simulation(program, shots: int, time_steps: int, seed: int, blockade_radius: float = 0.0):
    """Run one AHS program on the local simulator, reproducibly.

    The simulator has no seed argument. Its shot sampling draws from numpy's
    global legacy RNG, so seeding immediately before the call is the only way to
    make a task retry produce the same shots. The time evolution itself is
    deterministic; only the sampling is stochastic.
    """
    from braket.devices import LocalSimulator

    np.random.seed(seed)
    # blockade_radius=0.0 means "use the full Hilbert space". Setting it to a
    # real distance projects out doubly-excited configurations, which is much
    # faster but changes the physics, so it stays opt-in.
    return LocalSimulator("braket_ahs").run(
        program,
        shots=shots,
        steps=time_steps,
        nsteps=SOLVER_SUBSTEPS,
        blockade_radius=blockade_radius,
        progress_bar=False,
    ).result()


def decode_shots(result, nodes):
    """Turn shot results into candidate vertex sets.

    Uses both the pre-sequence and the post-sequence. A post-sequence value of
    0 means either "excited to Rydberg" or "the site was empty", so reading the
    post-sequence alone would count a site that never loaded as an excitation.
    Combining them as pre * (1 + post) separates the three cases:
    0 = empty site, 1 = Rydberg, 2 = ground state.

    Returns (selections, empty_shot_count) where selections is a list of
    frozensets of graph nodes marked as Rydberg.
    """
    selections = []
    shots_with_empty_sites = 0

    for shot in result.measurements:
        pre = np.asarray(shot.pre_sequence)
        post = np.asarray(shot.post_sequence)
        state = pre * (1 + post)

        if np.any(state == 0):
            shots_with_empty_sites += 1

        selections.append(frozenset(node for node, s in zip(nodes, state) if s == 1))

    return selections, shots_with_empty_sites


def exact_max_independent_set(graph):
    """Exact maximum independent set, for use as the classical baseline.

    A maximum independent set of a graph is a maximum clique of its complement,
    so this defers to networkx's exact max_weight_clique with unit weights.
    Exact and fast at the sizes this sample simulates; do not point it at a
    large graph.
    """
    if graph.number_of_nodes() == 0:
        return frozenset()
    clique, _ = nx.max_weight_clique(nx.complement(graph), weight=None)
    return frozenset(clique)


def score(selections, graph, optimum_size):
    """Score decoded shots against the classical optimum.

    Independent sets are counted as valid; shots containing an edge are
    violations and are excluded from the approximation ratio rather than
    silently inflating it.
    """
    total = len(selections)
    if total == 0:
        return {
            "shots": 0,
            "valid_fraction": 0.0,
            "approximation_ratio": 0.0,
            "probability_of_optimum": 0.0,
            "mean_set_size": 0.0,
            "best_set_size": 0,
        }

    valid_sizes = []
    optimum_hits = 0
    all_sizes = []

    for selected in selections:
        all_sizes.append(len(selected))
        is_independent = not any(
            u in selected and v in selected for u, v in graph.edges()
        )
        if is_independent:
            valid_sizes.append(len(selected))
            if len(selected) == optimum_size:
                optimum_hits += 1

    denominator = optimum_size if optimum_size > 0 else 1
    return {
        "shots": total,
        "valid_fraction": len(valid_sizes) / total,
        # Averaged over valid shots only. Zero if no shot was independent.
        "approximation_ratio": (
            float(np.mean(valid_sizes)) / denominator if valid_sizes else 0.0
        ),
        "probability_of_optimum": optimum_hits / total,
        "mean_set_size": float(np.mean(all_sizes)),
        "best_set_size": max(valid_sizes) if valid_sizes else 0,
    }


def linspace_value(index: int, count: int, low: float, high: float) -> float:
    """Map a 1-based task index onto a value in [low, high].

    Task parameters are integers so that the grid resolution can be a job
    parameter; the physical value is recovered here.
    """
    if index < 1 or index > count:
        raise ValueError(f"index {index} outside 1..{count}")
    if count == 1:
        return low
    return low + (high - low) * (index - 1) / (count - 1)


def emit_progress(fraction: float) -> None:
    """Report progress to the Deadline Cloud monitor."""
    print(f"openjd_progress: {max(0.0, min(100.0, fraction * 100.0)):.1f}", flush=True)


def emit_status(message: str) -> None:
    """Report a human readable status to the Deadline Cloud monitor."""
    print(f"openjd_status: {message}", flush=True)


def write_json(path: Path, payload: dict) -> None:
    """Write a result file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
