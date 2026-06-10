# GROMACS Host Configuration

Installs GROMACS on Linux SMF fleet workers for molecular dynamics simulation workloads.

## What it installs

- **GROMACS** (latest from conda-forge) — molecular dynamics simulation engine with thread-MPI support

## Usage

Apply this script as the host configuration on your SMF fleet. Workers will have `gmx` available system-wide after boot.

See [job_bundles/gromacs_md](../../job_bundles/gromacs_md/) for the corresponding job template.
