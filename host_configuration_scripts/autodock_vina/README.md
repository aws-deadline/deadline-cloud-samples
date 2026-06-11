# AutoDock VINA Host Configuration

Installs AutoDock VINA on Linux SMF fleet workers for molecular docking (virtual screening) workloads.

## Preferred approach: Conda recipe

Use the conda recipe at [`conda_recipes/autodock-vina-1.2.5/`](../../conda_recipes/autodock-vina-1.2.5/) with your queue's Conda environment. Add both `autodock-vina` (from your S3 channel) and `openbabel` (from conda-forge) to the queue environment packages. This eliminates the need for a host config script entirely.

## Fallback: Host config script

This script is a fallback for fleets without a Conda queue environment. It downloads the VINA static binary at worker boot. If using this approach, also add `openbabel` to your queue's Conda environment packages.

## Usage

See [job_bundles/virtual_screening_vina](../../job_bundles/virtual_screening_vina/) for the corresponding job template.
