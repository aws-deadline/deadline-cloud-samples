# MuJoCo 4.0 on Rocky Linux 9 (CPU)

The image behind the [MuJoCo 4.0 feature sweeps](../README.md) sample.
It holds [MuJoCo](https://github.com/google-deepmind/mujoco) 4.0.0, headless offscreen rendering, and
the 4.0 example models for elasto-plasticity and speculative contacts.

MuJoCo publishes manylinux wheels, so nothing is compiled.
The image is about 860 MB, or 300 MB compressed in Amazon ECR.

## What's in the image

| Path | Contents |
|---|---|
| `/usr/local/bin/mj4-sweep` | One sweep point: set the physics, simulate, render PNG frames, encode an MP4, write `metrics.json` |
| `/usr/local/bin/mj4-summarize` | Read a directory of `metrics.json` files and print a table, or write `summary.csv` |
| `/models/mujoco/model/plastic/` | The [elasto-plasticity examples](https://github.com/google-deepmind/mujoco/tree/4.0.0/model/plastic), including `torsion.xml` |
| `/models/mujoco/model/speculative/` | The [speculative contacts examples](https://github.com/google-deepmind/mujoco/tree/4.0.0/model/speculative), including `newton.xml` |
| `/mujoco-refs.txt` | The MuJoCo version and the source commit the models came from |

The models come from the commit that the `4.0.0` tag points to, so a rebuild gets the same scenes.
Override with `--build-arg MUJOCO_VERSION=...` or `MUJOCO_REF=...`.

## Build

```console
docker build --platform linux/amd64 -t mujoco4-rocky9:4.0.0 .
```

The build runs a short point of each sweep, encoding one MP4, and fails if it writes no metrics or
renders only black frames. A broken GL stack or encoder shows up at build time, not in your first job.

## Test locally

The image has no entrypoint, so pass the command and its arguments directly.
Deadline Cloud runs job commands the same way.

```console
docker run --rm mujoco4-rocky9:4.0.0
```

That prints `/mujoco-refs.txt`. To render one point of each sweep into `./output`:

```console
mkdir -p output
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/output:/output" \
  mujoco4-rocky9:4.0.0 \
  mj4-sweep torsion --yield-strain 0.05 --duration 2 --out-dir /output/yield0.05 --label yield0.05
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/output:/output" \
  mujoco4-rocky9:4.0.0 \
  mj4-sweep cradle --timestep-ms 8 --speculative enable --out-dir /output/dt8 --label dt8
docker run --rm -v "$PWD/output:/output" mujoco4-rocky9:4.0.0 mj4-summarize /output
```

Each point writes about 40 PNG frames, `clip.mp4` and `metrics.json`.
Run `mj4-sweep torsion --help` or `mj4-sweep cradle --help` for every option.

## How mj4-sweep applies parameters

`mj4-sweep` compiles the model once, then changes values on the compiled `mjModel`.
Each `metrics.json` records the before and after values under `applied`, so you can check.

### torsion

`--yield-strain` sets `flex_yield[plastic_bar, 0]`, the stretching yield strain of the orange bar.
A 3D flex has only a stretching mode.

MuJoCo allocates plastic state in `mjData.plastic` only for a mode whose yield is above zero when the
model compiles. Raising `flex_yield` at run time on a bar that compiled with `yield="0"` does nothing.
The command checks `flex_plasticmode` and exits non-zero in that case.
It also rejects `--yield-strain 0`: at run time zero means full plastic flow, not an elastic bar.

The command reports the plastic bar's peak and final twist from its `twist_1` hinge, the same for the
elastic bar as a control, and the L1 norm of the bar's slice of `mjData.plastic`.

### cradle

`--timestep-ms` sets `opt.timestep`. `--speculative` sets or clears `mjENBL_SPECULATIVE` in
`opt.enableflags`, the same bit as `<flag speculative="enable"/>`.
`--release-angle` swings plate 1 back. `newton.xml` builds that plate at 58 degrees.

The plates use a direct `solref="0 -499"`, tuned so that `timestep * 499 = 1.996` at 4 ms.
That product makes one contact step reverse the normal velocity, the cradle's elastic impact.
The command rescales the damping to `1.996 / timestep` for every timestep. Without that, the
restitution changes with the timestep, and at 8 ms with speculative contacts the solver diverges.

A run counts as `tunneled` when any plate's centre passes its neighbour's, from the plates' x positions
after each step. `travel_per_step_mm` is the peak of `|qvel| * 1.0 m * timestep` for plate 1, the same
pre-step velocity that speculative sweeps use.

## Rendering notes

Rendering uses EGL with Mesa's llvmpipe software rasterizer, and `MUJOCO_GL=egl` is set.
A 480x360 frame takes about 0.08 seconds. Lower `--fps` for a faster sweep.
The image is CPU-only. GPU rendering through the same EGL path is untested.

ffmpeg comes from EPEL as `ffmpeg-free`, which encodes H.264 through `libopenh264`.
`mj4-sweep` falls back to MPEG-4 if that encoder is missing and records the codec in `metrics.json`.

## Wheel and glibc

MuJoCo 4.0 splits the Python distribution into `mujoco-core`, `mujoco-studio` and a `mujoco`
meta-package that installs both. The image installs `mujoco-core[rendering]`, which adds PyOpenGL and
glfw for `mujoco.Renderer`. It leaves out `mujoco-studio`, the Filament renderer and Studio viewer, which a
headless sweep doesn't use. That saves about 35 MB and the `websockets` dependency.

The 4.0.0 wheels target `manylinux_2_28` and need Python 3.11 or later.
Rocky Linux 9 has glibc 2.34 and Python 3.12, so `pip` installs them with no compile step.

## MuJoCo 4.0.1

MuJoCo 4.0.1 fixes a sparse Cholesky factorization bug from 4.0.0 that gives the Newton solver a
wrong Hessian factor when the constraint Jacobian is sparse, per the
[4.0.1 changelog](https://github.com/google-deepmind/mujoco/blob/4.0.1/doc/changelog.rst). Neither scene
here takes that path:
`newton.xml` uses the Newton solver with a dense Jacobian, and `torsion.xml` uses the CG solver.
To use 4.0.1 for other scenes, build with `--build-arg MUJOCO_VERSION=4.0.1` and set `MUJOCO_REF` to
that release's commit.
