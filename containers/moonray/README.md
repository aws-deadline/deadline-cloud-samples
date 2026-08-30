# MoonRay containers

Container samples for running [MoonRay](https://openmoonray.org/), DreamWorks' open-source
production path tracer, on the CPU.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Rocky Linux 9 CPU image](rocky9-cpu/) | Compiling MoonRay from source per the [official container build docs](https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/) | You want an unprivileged CPU image, or need to build a specific MoonRay revision |

The source build takes hours to compile but produces a self-contained image that runs as a normal
unprivileged container, with no systemd, or `--privileged` requirement.

## Where to get the sample scenes

No scene files ship with this sample. MoonRay publishes the example scenes itself, and the sample's
`.gitignore` keeps any local copy out of git — the archive unpacks to roughly 700 MB.

* **Bundled test scenes** — small `.rdla` and `.usd` files already inside the image at
  `/source/testdata`, from the [MoonRay source tree](https://github.com/dreamworksanimation/openmoonray).
  Use these to confirm the build works.
* **Official example scenes** — download
  [example_scenes.zip](https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip) from the
  [MoonRay test scenes page](https://docs.openmoonray.org/getting-started/test-scenes/), then mount
  the unpacked directory into the container.

See [rocky9-cpu/README.md](rocky9-cpu/README.md) for the exact download and render commands.
