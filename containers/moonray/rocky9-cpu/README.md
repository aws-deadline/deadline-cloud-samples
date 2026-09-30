# MoonRay on Rocky Linux 9 (CPU, source build)

This sample builds [MoonRay](https://openmoonray.org/) from source in a
[Rocky Linux 9](https://hub.docker.com/_/rockylinux) container, following the official
[Rocky 9 container build procedure](https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/).
Where the official docs run the steps interactively and `docker commit` the result, this
`Dockerfile` encodes the same steps so the image is reproducible with one command.

The resulting image needs no snapd, no systemd, and no `--privileged` — MoonRay is compiled into
`/installs/openmoonray` and runs in a plain unprivileged container.

## Prerequisites

* Docker (or a compatible CLI such as `finch`; substitute `finch` for `docker` below)
* Time and resources: the build compiles MoonRay's dependency stack (OpenEXR, OpenVDB, USD, ...)
  and then MoonRay itself. On a native x86_64 machine expect roughly 1–2 hours and 8+ GB of RAM;
  under emulation on Apple Silicon it can take many hours.
* ~20 GB of free disk for intermediate layers

## Build

```console
docker build --platform linux/amd64 -t openmoonray-rocky9 .
```

### Choosing a MoonRay version

`OPENMOONRAY_REF` selects which MoonRay to build. It defaults to the released tag
`v2026.29.1` rather than a branch, so rebuilding this `Dockerfile` months from now produces the
same MoonRay instead of whatever `main` happens to be that day.

Available versions are listed on the
[openmoonray tags page](https://github.com/dreamworksanimation/openmoonray/tags) (also on the
[releases page](https://github.com/dreamworksanimation/openmoonray/releases)). Upstream has used
two tag series: the older `openmoonray-<major>.<minor>.0.0` scheme, which ends at
`openmoonray-3.6.0.1`, and the current date-based `v<year>.<week>.<n>` scheme.

```console
docker build --platform linux/amd64 \
    --build-arg OPENMOONRAY_REF=openmoonray-3.6.0.1 \
    -t openmoonray-rocky9:3.6.0.1 .
```

The value goes to `git clone --branch`, so a tag or a branch name works — pass `main` to build the
tip of development — but a bare commit sha does not. Older tags are not tested by this sample and
may need different system packages than `building/Rocky9/install_packages.sh` installs at the
pinned version.

The version that was actually built is recorded in the image at `/openmoonray-ref.txt`, as the
requested ref plus the commit it resolved to:

```console
docker run --rm openmoonray-rocky9 'cat /openmoonray-ref.txt'
```

Two deviations from the official docs, both encoded in the `Dockerfile` with comments:

* The `moonray/materialx_shaders` submodule points at a repository that is not public, so it is
  deactivated before `git submodule update`.
* cmake is installed from pip (`pip3 install "cmake<4"`): the EPEL cmake crashes in libuv's
  signal handling when the build runs under x86_64 emulation on an arm64 host.

MoonRay itself is configured through upstream's `rocky9-release` CMake preset, as the official
docs do. The preset is what links step 3 to step 2: the dependencies install to
`/opt/MoonRay/installs`, and the preset supplies the `CMAKE_PREFIX_PATH` and per-dependency
`*_ROOT` variables that point there. Configuring by hand without it stops at
`Could NOT find JsonCpp`.

## Where to get the scenes

No scene files ship with this sample. There are two sources:

* **Bundled test scenes** — small `.rdla` and `.usd` files already present in the image at
  `/source/testdata`, carried in from the
  [MoonRay source tree](https://github.com/dreamworksanimation/openmoonray). Nothing to download.
* **Official example scenes** — the larger `pbrt_scenes` set, published by MoonRay as
  [example_scenes.zip](https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip) on the
  [test scenes page](https://docs.openmoonray.org/getting-started/test-scenes/). Download it
  yourself; it unpacks to roughly 700 MB, and the sample's `.gitignore` keeps `scenes/`,
  `output/`, and the zip out of git.

## Running moonray needs `CAP_SYS_NICE`

This is a run-time requirement only. `docker build` needs nothing beyond the flags shown above.

`moonray` sets memory affinity by default (`-auto_affinity on`), which calls `mbind(2)` to bind
memory to a NUMA node. Docker's default seccomp profile permits that syscall only when the
container has `CAP_SYS_NICE`, so under a plain `docker run` the container starts and the scene
loads, then the render thread aborts as it initializes:

```
what():  numaNodeMBInd() sysCallMBind() failed. numaNodeId:0 size:33554432
```

The official docs work around this with `--security-opt seccomp=unconfined`. Two narrower options
work as well, and the `docker run` commands below use the first:

* `--cap-add SYS_NICE` — keeps the default seccomp profile and leaves affinity control enabled.
* `-auto_affinity off` on the `moonray` command line — no added capability or relaxed sandbox, at
  the cost of NUMA-aware allocation. Sensible on a single-socket machine.

`hd_render` is unaffected and needs neither.

## Render the bundled test scene

The source tree (kept at `/source` in the image) includes small test scenes:

```console
mkdir -p output
docker run --rm --cap-add SYS_NICE -v "$(pwd)/output:/output" openmoonray-rocky9 \
    'moonray -in /source/testdata/rectangle.rdla -out /output/rectangle.exr'
```

## Render the example scenes

Download and unpack the example scenes, then mount them into the container:

```console
curl -LO https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip
mkdir -p scenes output
unzip example_scenes.zip -d scenes/
docker run --rm --cap-add SYS_NICE -v "$(pwd)/scenes:/scenes" -v "$(pwd)/output:/output" \
    -w /scenes/example_scenes/pbrt_scenes/veach-mis openmoonray-rocky9 \
    'moonray -in scene.rdla -in scene.rdlb -exec_mode scalar -out /output/veach-mis.exr'
```

`hd_render` (the USD Hydra delegate CLI) is also on `PATH`:

```console
docker run --rm -v "$(pwd)/output:/output" openmoonray-rocky9 \
    'hd_render -in /source/testdata/sphere.usd -out /output/sphere.exr'
```

## Links

* [Official Rocky 9 container build docs](https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/)
* [MoonRay test scenes (example_scenes.zip)](https://docs.openmoonray.org/getting-started/test-scenes/)
* [OpenMoonRay source](https://github.com/dreamworksanimation/openmoonray)
