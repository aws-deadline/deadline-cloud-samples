# MuJoCo on Rocky Linux 9 (CPU)

The image behind the [MuJoCo hand sweep](../README.md) sample.
It holds [MuJoCo](https://github.com/google-deepmind/mujoco) 3.11.0, headless offscreen rendering, and two models.

MuJoCo publishes manylinux wheels, so nothing is compiled.
The image is about 950 MB, or 350 MB compressed in Amazon ECR.

## What's in the image

| Path | Contents |
|---|---|
| `/usr/local/bin/mj-hand-sweep` | One sweep point: scale the physics, simulate, render PNG frames, encode an MP4, write `metrics.json` |
| `/models/mujoco_menagerie/shadow_hand/` | The Shadow Dexterous Hand from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) |
| `/models/mujoco_menagerie/shadow_hand/scene_right_ball.xml` | Added by this sample: the right hand holding a checkered ball |
| `/models/mujoco_cube/` | The [3x3x3 puzzle cube](https://github.com/kevinzakka/mujoco_cube) model |
| `/mujoco-refs.txt` | The MuJoCo version and the two model commits in the image |

The model repositories are pinned to commits. A rebuild gets the same geometry.
Override them with `--build-arg MUJOCO_VERSION=...`, `CUBE_REF=...` or `MENAGERIE_REF=...`.

## Build

```console
docker build --platform linux/amd64 -t mujoco-rocky9:3.11.0 .
```

The build renders one frame of the cube and fails if the pixels are empty.
A broken GL stack shows up at build time, not in your first job.

## Test locally

The image has no entrypoint, so pass the command and its arguments directly.
Deadline Cloud runs job commands the same way.

```console
docker run --rm mujoco-rocky9:3.11.0
```

That prints `/mujoco-refs.txt`. To render one sweep point into `./output`:

```console
mkdir -p output
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/output:/output" \
  mujoco-rocky9:3.11.0 \
  mj-hand-sweep --model /models/mujoco_menagerie/shadow_hand/scene_right_ball.xml \
    --damping-scale 4.0 --stiffness-scale 2.0 --friction-scale 0.25 \
    --out-dir /output/damp4.0-kp2.0-fr0.25 --label damp4.0-kp2.0-fr0.25
```

You get 40 PNG frames, `clip.mp4` and `metrics.json`. Run `mj-hand-sweep --help` for every option.

## How mj-hand-sweep applies parameters

`mj-hand-sweep` compiles the model once, then scales values on the compiled `mjModel`.
Editing the MJCF XML by element name would miss most of them on this model.

The damping scale multiplies `dof_damping` on hinge joints only.
The stiffness scale multiplies `kp` on the 20 position actuators.
The friction scale multiplies the friction of the ball's geoms.

The command exits non-zero if a parameter matches nothing in the model.
A parameter that silently does nothing would make every combination identical.
Each `metrics.json` records the before and after values, so you can check.

The hand closes and opens on a 2-second cycle.
Each actuator moves between an open pose and the top of its control range.

## Rendering notes

Rendering uses EGL with Mesa's llvmpipe software rasterizer, and `MUJOCO_GL=egl` is set.
Rocky Linux 9 has no OSMesa package, so EGL is the only headless backend.

Software rendering is the main cost of each task. Lower `--fps` for a faster sweep.
The image is CPU-only. GPU rendering through the same EGL path is untested.

PyOpenGL loads `libOpenGL.so.0` and `libGL.so.1` at run time. The image installs both.
Without them you get an unhelpful `'NoneType' object has no attribute 'glGetError'`.

Each render prints `Exception ignored in: <function GLContext.__del__ ...>` at exit.
Python discards it after the frames are written, and the command still exits 0.

ffmpeg comes from EPEL as `ffmpeg-free`, which encodes H.264 through `libopenh264`.
`mj-hand-sweep` falls back to MPEG-4 if that encoder is missing and records the codec in `metrics.json`.

## Wheel and glibc

The MuJoCo 3.11.0 wheel targets `manylinux_2_28` and needs Python 3.11 or later.
Rocky Linux 9 has glibc 2.34 and Python 3.12, so `pip` installs the wheel with no compile step.

## Scope

The cube model has no hand, and its core body is welded to the world.
The sample doesn't solve a Rubik's cube. That takes a trained policy, which neither model repository provides.
The image gives you the physics and the rendering. The controller is yours to supply.
