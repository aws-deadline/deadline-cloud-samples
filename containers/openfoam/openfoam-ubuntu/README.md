# OpenFOAM image on Ubuntu 24.04

The image installs OpenFOAM from the [openfoam.com apt repository](https://www.openfoam.com/download/openfoam-installation-on-linux), so nothing is compiled.
It runs on CPU and adds a small tool that turns OpenFOAM output into PNG plots.

Build and push steps are in the [sample README](../README.md#build-and-push-the-image).

## What's installed

| Component | Details |
|---|---|
| Base image | `ubuntu:24.04` |
| OpenFOAM | `openfoam2512-default`: solvers, utilities, tutorials and MPI. ParaView and X11 are left out. |
| `hostname`, `bc` | Called by OpenFOAM's shell tools, and missing from the minimal base image. |
| matplotlib | Version 3.10.7, in a virtual environment at `/opt/foamplot`. |
| `foam-plot` | [`scripts/foam_plot.py`](scripts/foam_plot.py), installed at `/usr/local/bin/foam-plot`. |

## Which OpenFOAM

OpenCFD and the OpenFOAM Foundation both publish software called OpenFOAM, with different versions and solver names.
The image uses the openfoam.com line from OpenCFD.

| | openfoam.com | openfoam.org |
|---|---|---|
| Maintainer | OpenCFD | OpenFOAM Foundation |
| Versions | `v2506`, `v2512` | `11`, `12` |
| Install prefix | `/usr/lib/openfoam/openfoam<VERSION>` | `/opt/openfoam<VERSION>` |

The openfoam.com and openfoam.org lines are not drop-in replacements for each other.
If you switch, change the apt source, the install path in the Dockerfile, and the job's `Solver` parameter.

## Build arguments

| Argument | Default | Meaning |
|---|---|---|
| `OPENFOAM_VERSION` | `2512` | The release in the package name. Versions are the pool directories in the [repository](https://dl.openfoam.com/repos/deb/dists/noble/main/pool/). |
| `APT_SUITE` | `noble` | The apt suite. It must match the release of the `FROM` image. |
| `MATPLOTLIB_VERSION` | `3.10.7` | The matplotlib release for `foam-plot`. |

Tag the image with the OpenFOAM version you build, such as `openfoam-ubuntu:2412`.

## How OpenFOAM loads

OpenFOAM works only after its `etc/bashrc` is sourced, which puts the solvers on `PATH`.
The queue environment runs each command in the session container without a login shell, so `/etc/profile.d` is never read.

The image sets `BASH_ENV=/etc/profile.d/openfoam.sh`, which every non-interactive `bash` reads first.
A guard in that file skips the reload when a parent shell already loaded OpenFOAM.
Use `bash` to run OpenFOAM commands, because `sh` ignores `BASH_ENV`.

## foam-plot

`foamToVTK` writes data for ParaView. `foam-plot` draws that data headless, with the matplotlib Agg renderer.

```console
foam-plot field   OUT.png CASE_DIR                  # velocity magnitude and flow direction for one case
foam-plot profile OUT.png CASE_DIR [CASE_DIR ...]   # horizontal velocity on the vertical centreline
```

Both read the newest time under the case's `VTK/` directory, so run `foamToVTK` first.
They handle 2D cases only, and refuse a 3D mesh rather than flatten it.

## Notes

- The build solves, converts and plots the cavity tutorial, and fails if the PNG is under 20 KB.
- `dl.openfoam.com` redirects to SourceForge mirrors. The build retries, so a slow install step is often a dead mirror.
- The apt source pins `arch=amd64`, so the image is x86_64 only.
- The queue environment runs commands as root in the container. MPI runs then need `mpirun --allow-run-as-root`.
