"""Independently verify the simulator against a from-scratch Schrodinger solve.

The other validation layers check the scoring, the graph correspondence, and a
published reference point. None of them prove that *this* sample's annealing
schedule is simulated correctly, because the schedule matches no published
example.

This check closes that gap without needing a reference. It reads the Analog
Hamiltonian Simulation program that the job actually submits, rebuilds the
Rydberg Hamiltonian from first principles, integrates the Schrodinger equation
with scipy, and compares the resulting state against what the Braket local
simulator reports.

Two independent implementations of the same physics agreeing to within shot
noise is the strongest correctness evidence available offline.

    python scripts/verify_dynamics.py
"""

import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ahs_mis  # noqa: E402


def read_program_waveforms(program):
    """Pull the drive out of the submitted program IR, not from a reimplementation.

    Reading the intermediate representation means this check validates the exact
    object the job sends to the simulator, including any unit conversion or
    rounding applied on the way.
    """
    ir = program.to_ir()
    drive = ir.hamiltonian.drivingFields[0]

    def series(field):
        return (
            np.array([float(t) for t in field.time_series.times]),
            np.array([float(v) for v in field.time_series.values]),
        )

    sites = np.array([[float(c) for c in site] for site in ir.setup.ahs_register.sites])
    filling = np.array([int(f) for f in ir.setup.ahs_register.filling])
    return series(drive.amplitude), series(drive.detuning), series(drive.phase), sites[filling == 1]


def build_hamiltonian_parts(coordinates):
    """Build the time-independent pieces of the Rydberg Hamiltonian.

    H(t) = diag(vdw) - Delta(t) * diag(n) + (Omega(t) / 2) * X

    where n counts Rydberg excitations per basis state, vdw is the van der Waals
    energy of each basis state, and X couples basis states differing by a single
    excitation. Basis state index bits are 1 for Rydberg, 0 for ground.
    """
    n_atoms = len(coordinates)
    dim = 2**n_atoms

    # Pairwise van der Waals couplings V_jk = C6 / d_jk^6.
    deltas = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt((deltas**2).sum(axis=-1))
    np.fill_diagonal(distances, np.inf)
    couplings = ahs_mis.C6 / distances**6

    indices = np.arange(dim)
    bits = ((indices[:, None] >> np.arange(n_atoms)) & 1).astype(float)

    excitations = bits.sum(axis=1)
    vdw = 0.5 * np.einsum("si,ij,sj->s", bits, couplings, bits)

    # Single-excitation-flip adjacency, which the drive term acts through.
    flip = np.zeros((dim, dim))
    for atom in range(n_atoms):
        partners = indices ^ (1 << atom)
        flip[indices, partners] = 1.0

    return excitations, vdw, flip


def integrate(program, coordinates, rtol=1e-10, atol=1e-12):
    """Integrate the Schrodinger equation and return per-state probabilities."""
    (amp_t, amp_v), (det_t, det_v), (pha_t, pha_v), _ = read_program_waveforms(program)
    excitations, vdw, flip = build_hamiltonian_parts(coordinates)
    dim = len(excitations)

    if np.any(np.abs(pha_v) > 1e-12):
        raise NotImplementedError("this check assumes zero drive phase")

    duration = float(amp_t[-1])

    def rhs(t, psi):
        omega = np.interp(t, amp_t, amp_v)
        detuning = np.interp(t, det_t, det_v)
        diagonal = vdw - detuning * excitations
        h_psi = diagonal * psi + (omega / 2.0) * (flip @ psi)
        return -1j * h_psi

    psi0 = np.zeros(dim, dtype=complex)
    psi0[0] = 1.0  # every atom starts in its ground state

    solution = solve_ivp(
        rhs, (0.0, duration), psi0, method="DOP853", rtol=rtol, atol=atol, dense_output=False
    )
    if not solution.success:
        raise RuntimeError(f"integration failed: {solution.message}")

    psi = solution.y[:, -1]
    norm = np.abs(psi) ** 2
    return norm / norm.sum()


def densities_from_probabilities(probabilities, n_atoms):
    """Per-atom Rydberg density implied by a basis-state probability vector."""
    indices = np.arange(len(probabilities))
    bits = ((indices[:, None] >> np.arange(n_atoms)) & 1).astype(float)
    return probabilities @ bits


def main() -> int:
    print("Independent verification of the simulated dynamics")
    print("Comparing the Braket local simulator against a from-scratch")
    print("Schrodinger integration of the same submitted program.\n")

    shots = 40000
    cases = [
        ("7 atoms, long anneal, positive detuning", (4, 3, 0.45, 3), 3.8e-6, 6.0e7),
        ("7 atoms, short anneal, positive detuning", (4, 3, 0.45, 3), 0.8e-6, 6.0e7),
        ("7 atoms, long anneal, negative detuning", (4, 3, 0.45, 3), 3.8e-6, -2.0e7),
        ("8 atoms, mid anneal, mid detuning", (3, 3, 0.1, 5), 2.4e-6, 3.0e7),
    ]

    worst_density = 0.0
    worst_tv = 0.0
    failures = 0

    for label, (width, height, dropout, seed), anneal, detuning in cases:
        register, graph, positions = ahs_mis.build_instance(width, height, dropout, seed)
        n_atoms = graph.number_of_nodes()
        program = ahs_mis.build_program(register, anneal, detuning)

        coordinates = np.array([positions[node] for node in sorted(positions)])
        exact = integrate(program, coordinates)
        exact_density = densities_from_probabilities(exact, n_atoms)

        result = ahs_mis.run_simulation(program, shots=shots, time_steps=400, seed=17)
        # The SDK reports densities with empty sites excluded; the local
        # simulator never drops atoms, so the two are directly comparable.
        sim_density = result.get_avg_density()

        # Braket orders sites in the order they were added, which is sorted node
        # order, matching `coordinates`.
        density_error = float(np.abs(exact_density - sim_density).max())

        # Also compare the full distributions. Shot noise on a multinomial with
        # this many shots is about 1/sqrt(shots) in total variation.
        counts = result.get_counts()
        sampled = np.zeros(len(exact))
        for state, count in counts.items():
            index = sum(
                (1 << position) for position, ch in enumerate(state) if ch == "r"
            )
            sampled[index] += count
        sampled /= sampled.sum()
        total_variation = 0.5 * float(np.abs(sampled - exact).sum())

        noise_floor = 3.0 / np.sqrt(shots)
        ok_density = density_error < 0.02
        ok_tv = total_variation < max(0.05, noise_floor * np.sqrt(2**n_atoms))
        if not (ok_density and ok_tv):
            failures += 1

        worst_density = max(worst_density, density_error)
        worst_tv = max(worst_tv, total_variation)

        print(f"  {label}")
        print(f"    atoms {n_atoms}, anneal {anneal * 1e6:.2f} us, detuning {detuning / 1e6:+.1f} Mrad/s")
        print(f"    max per-atom density error : {density_error:.5f}  [{'PASS' if ok_density else 'FAIL'}]")
        print(f"    distribution total variation: {total_variation:.5f}  [{'PASS' if ok_tv else 'FAIL'}]")
        print(f"    mean Rydberg density        : exact {exact_density.mean():.4f} "
              f"vs simulator {sim_density.mean():.4f}")
        print()

    print(f"worst per-atom density error across cases: {worst_density:.5f}")
    print(f"worst distribution total variation       : {worst_tv:.5f}")
    print()
    if failures:
        print(f"FAILED: {failures} case(s) disagree beyond tolerance")
        return 1
    print("Independent integration agrees with the Braket simulator.")
    print("The sample's Hamiltonian and annealing schedule are correct as submitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
