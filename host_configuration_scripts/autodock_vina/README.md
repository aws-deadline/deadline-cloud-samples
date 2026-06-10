# AutoDock VINA Host Configuration

Installs AutoDock VINA and Open Babel on Linux SMF fleet workers for molecular docking (virtual screening) workloads.

## What it installs

- **AutoDock VINA 1.2.5** — molecular docking engine (static binary from GitHub releases)
- **Open Babel 3.1.x** — chemical format converter (via micromamba/conda-forge)

## Usage

Apply this script as the host configuration on your SMF fleet. Workers will have `vina` and `obabel` available system-wide after boot.

See [job_bundles/virtual_screening_vina](../../job_bundles/virtual_screening_vina/) for the corresponding job template.
