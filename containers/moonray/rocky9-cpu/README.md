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

The MoonRay git ref defaults to the `main` branch; override it with
`--build-arg OPENMOONRAY_REF=<tag-or-branch>`.

Two deviations from the official docs, both encoded in the `Dockerfile` with comments:

* The `moonray/materialx_shaders` submodule points at a repository that is not public, so it is
  deactivated before `git submodule update`.
* cmake is installed from pip (`pip3 install "cmake<4"`): the EPEL cmake crashes in libuv's
  signal handling when the build runs under x86_64 emulation on an arm64 host.

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

## Render the bundled test scene

The source tree (kept at `/source` in the image) includes small test scenes:

```console
mkdir -p output
docker run --rm -v "$(pwd)/output:/output" openmoonray-rocky9 \
    'moonray -in /source/testdata/rectangle.rdla -out /output/rectangle.exr'
```

## Render the example scenes

Download and unpack the example scenes, then mount them into the container:

```console
curl -LO https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip
mkdir -p scenes output
unzip example_scenes.zip -d scenes/
docker run --rm -v "$(pwd)/scenes:/scenes" -v "$(pwd)/output:/output" \
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
