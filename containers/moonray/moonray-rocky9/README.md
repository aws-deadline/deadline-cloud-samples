# MoonRay image for Rocky Linux 9 (CPU)

The Dockerfile builds [MoonRay](https://openmoonray.org/) from source on Rocky Linux 9.
It follows the official [Rocky 9 container build steps](https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/).

The Docker queue environment runs each command in the container without a login shell.
The image puts every MoonRay tool on `PATH` without one.

## Build requirements

* An x86_64 machine. The build took about 45 minutes on 16 cores and produced a 3.6 GB image.
  Under x86_64 emulation on Apple Silicon it takes many hours.
* 8 GB of RAM or more, and about 20 GB of free disk for intermediate layers.

## Build and test

```console
docker build --platform linux/amd64 -t moonray-rocky9:v2026.29.1 .
docker run --rm moonray-rocky9:v2026.29.1 \
    moonray -in /source/testdata/rectangle.rdla -auto_affinity off -out /tmp/rectangle.exr
```

The image's default command prints `moonray -help`.
To push the image, follow [Build and push the image](../README.md#build-and-push-the-image).

## Choose a MoonRay version

The `OPENMOONRAY_REF` build argument selects the MoonRay version. It defaults to the release tag `v2026.29.1`.
Use the same version as the image tag. The tag then identifies the MoonRay version inside.

```console
docker build --platform linux/amd64 \
    --build-arg OPENMOONRAY_REF=<tag> -t moonray-rocky9:<tag> .
```

Pick a tag from the [openmoonray tags page](https://github.com/dreamworksanimation/openmoonray/tags).
Upstream uses two tag series: `openmoonray-<major>.<minor>.0.<n>` up to `openmoonray-3.6.0.1`, then `v<year>.<week>.<n>`.
The value goes to `git clone --branch`, which accepts a tag or a branch name. It doesn't accept a commit SHA.

The sample tests only `v2026.29.1`. Other versions may need other packages or a different `ENV` block.
The image records the requested ref and its commit in `/openmoonray-ref.txt`.

```console
docker run --rm moonray-rocky9:v2026.29.1 cat /openmoonray-ref.txt
```

## Changes from the official build steps

* The build skips the `moonray/materialx_shaders` submodule, which points at a private repository.
* cmake comes from pip. The EPEL cmake crashes in libuv when the build runs under x86_64 emulation.
* The dependency step deletes its `/build` tree in the same layer, which keeps about 3.8 GB of build files out of the image.
* `ENV` sets the variables that `scripts/setup.sh` exports, because the queue environment never runs a login shell.
* The build generates the shader descriptions that `setup.sh` would otherwise create on first use.
* A smoke render of a bundled test scene fails the build if `moonray` is not on `PATH`.

When you change `OPENMOONRAY_REF`, compare the `ENV` block with that version's `scripts/setup.sh`.

## MoonRay needs CAP_SYS_NICE for NUMA memory binding

By default, `moonray` binds memory to NUMA nodes with `mbind(2)`.
Docker's default seccomp profile allows that call only for containers with `CAP_SYS_NICE`.

The Docker queue environment doesn't add capabilities. A render with default flags aborts with this message.

```text
what():  numaNodeMBInd() sysCallMBind() failed. numaNodeId:0 size:33554432
```

Pass `-auto_affinity off` to `moonray`, as the job template and the test command do.

## Related resources

* [Official Rocky 9 container build docs](https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/)
* [MoonRay test scenes](https://docs.openmoonray.org/getting-started/test-scenes/)
* [OpenMoonRay source](https://github.com/dreamworksanimation/openmoonray)
