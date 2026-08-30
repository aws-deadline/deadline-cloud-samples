# MoonRay in a container, as an Open Job Description job

An [Open Job Description](https://github.com/OpenJobDescription) job that renders a MoonRay example
scene inside the [`rocky9-cpu`](../rocky9-cpu/) image, using the `WRAP_ACTIONS` and `EXPR`
extensions to put the render in a container without the job template knowing anything about
containers.

The job template describes a render. The wrap environment describes a container. They are separate
files on purpose: the same job runs unchanged on a host with `moonray` on `PATH`, or on a render
farm where the container comes from a queue environment.

## Files

| File | Purpose |
|---|---|
| `moonray-render-job.yaml` | The job. `EXPR` only — no mention of docker. |
| `local-docker-wrap-env.yaml` | Environment template with the `WRAP_ACTIONS` hooks that run each action in a container on this workstation. |
| `run-render.sh` | Downloads the scenes, then runs the job with the Python CLI, the Rust CLI, or both. |
| `.gitignore` | Keeps `sessions/` and the scene archive out of git. |

## Prerequisites

* Docker, with the `openmoonray-rocky9` image built from the sibling sample:

  ```console
  cd ../rocky9-cpu
  docker build --platform linux/amd64 -t openmoonray-rocky9 .
  ```

  That build compiles MoonRay from source and takes hours. See its
  [README](../rocky9-cpu/README.md).

* An `openjd` CLI on `PATH` — either
  [openjd-cli](https://github.com/OpenJobDescription/openjd-cli) (Python) or
  [openjd-rs](https://github.com/OpenJobDescription/openjd-rs) (Rust). Both are supported and
  produce identical container invocations.

* `curl` and `unzip`, for fetching the example scenes.

## Quick start

```console
./run-render.sh rust      # render with the Rust openjd CLI, from $RUST_BIN
./run-render.sh python    # render with the Python openjd-cli, from $VENV/bin
./run-render.sh path      # use whichever openjd is already on PATH
./run-render.sh           # python then rust, one after the other
./run-render.sh --fetch-only   # just download and unpack the scenes
```

`python` and `rust` look in the source-checkout locations in the table below, which suits a machine
with both built from source; `path` is for a normally installed CLI. Each run prints and logs the
`openjd` it resolved and its version, so an `.exr` can always be traced back to the CLI that made
it. A missing or mislocated CLI fails immediately with the variable to set, rather than surfacing as
`openjd: command not found` from inside a session.

On the first run this downloads
[example_scenes.zip](https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip)
(379 MB, unpacking to ~705 MB) into `sessions/scenes/`. Later runs reuse it.

Output lands in `sessions/output/<impl>-<scene>.exr`, prefixed per implementation so the two runs
do not overwrite each other.

Overrides, as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `IMAGE` | `openmoonray-rocky9` | Image to run |
| `SCENE` | `veach-mis` | Scene under `pbrt_scenes/` |
| `EXEC_MODE` | `scalar` | `scalar` or `vectorized` |
| `DOCKER_USER` | invoking user | `docker --user` value |
| `KEEP_SESSIONS` | `1` | Pass `--preserve` to keep session dirs |
| `VENV` | `~/work/openjd/.venv` | Venv holding the Python `openjd-cli` |
| `RUST_BIN` | `~/work/openjd/openjd-rs/target/release` | Directory holding the Rust `openjd` |

## Running it by hand

`run-render.sh` is a convenience wrapper. The underlying invocation is:

```console
openjd run moonray-render-job.yaml \
    --environment local-docker-wrap-env.yaml \
    --step Render \
    -p SessionsDir="$PWD/sessions" \
    -p ContainerMount=/mnt/session \
    -p OutputPrefix=rust
```

## How it works

`WRAP_ACTIONS` lets one environment replace the lifecycle actions of everything inside it. Each of
the three hooks — `onWrapEnvEnter`, `onWrapTaskRun`, `onWrapEnvExit`, which must all be defined
together — receives the action it replaced through `WrappedAction.*` variables, and here re-runs it
with `docker run`.

So the job's `onRun`:

```yaml
command: moonray
args: [-in, "{{ scene_dir }}/scene.rdla", ..., -out, "{{ out_exr }}"]
```

becomes, at run time:

```console
docker run --rm --cap-add SYS_NICE --platform linux/amd64 --user <uid>:<gid> \
    -e HOME=/tmp -v <templates>/sessions:/mnt/session openmoonray-rocky9 \
    'env  moonray -in /mnt/session/scenes/.../veach-mis/scene.rdla \
         -in /mnt/session/scenes/.../veach-mis/scene.rdlb \
         -exec_mode scalar -out /mnt/session/output/rust-veach-mis.exr'
```

Three details in that command are load-bearing:

* **One argument after the image name.** The image's `ENTRYPOINT` is `bash -lc`, which takes the
  whole command as a single string. The hook composes one string rather than separate argv entries.
* **`repr_sh()`**, from `EXPR`, shell-quotes the forwarded command and args so metacharacters,
  spaces and quotes reach the process verbatim instead of being interpreted by that login shell.
* **`env` prefix** applies any session-defined variables (`WrappedAction.Environment`) inside the
  container. With none defined the list is empty and `env` is a passthrough.

`EXPR` also supplies the job's `let` bindings, which build the in-container paths once from
`Task.Param.Scene`.

The wrap environment's own `onEnter`/`onExit` run on the **host**, not in a container — a wrap
environment's own lifecycle is never intercepted by its own hooks. `onEnter` uses that to check the
image exists up front, so a missing image fails once with a clear message instead of once per task.

## Notes and gotchas

**`--cap-add SYS_NICE` is required.** MoonRay binds NUMA memory with `mbind(2)`, which Docker's
default seccomp profile blocks unless the container has `CAP_SYS_NICE`. Without it every render
aborts during thread-local setup:

```
terminate called after throwing an instance of 'scene_rdl2::except::RuntimeError'
  what():  numaNodeMBInd() sysCallMBind() failed. numaNodeId:0 size:33554432
```

This affects plain `docker run` too, not just this job — including the render command in the
`rocky9-cpu` README.

**Two harmless log lines when running non-root.** `docker --user` with a uid that has no entry in
the image's `/etc/passwd` produces `id: cannot find name for user ID <uid>`, and MoonRay logs
`ERROR: boost::filesystem::create_directory: Permission denied:
"/installs/openmoonray/shader_json/"`. Neither stops the render. Set `DOCKER_USER=0:0` to run as
root and silence both, at the cost of root-owned files in `sessions/output/`.

**Session directories.** Neither CLI exposes a session-directory flag; both derive the session root
from the system temp dir on POSIX. `run-render.sh` therefore sets `TMPDIR` to `sessions/`, so
session working directories appear as `sessions/OpenJD/…` rather than in `/tmp`. The whole
`sessions/` directory is what gets bind mounted, which is how the container sees the scenes and how
output gets back to the host.

**Parameters shared across the two templates.** `ContainerMount` is declared in both files with the
same type and default. That is legal — the CLI merges job and environment template parameter
definitions into one parameter space — and it means one `-p ContainerMount=…` moves the mount target
and the job's paths together instead of letting them drift. It is also why `-p SessionsDir=…`
works at all: `SessionsDir` is declared by the *environment* template, not the job.

**GPU.** The image is built `--nocuda`, so `EXEC_MODE=xpu` is not available.

## Verified run

Both implementations, on a 16-core x86_64 Linux host with docker 25.0:

```
IMPL     RESULT  SECONDS      EXR_BYTES  LOG
python   PASS        153        5826348  sessions/logs/render-python.log
rust     PASS        149        5826348  sessions/logs/render-rust.log
```

`openjd-cli 0.7.5.post21+g4e9a38421` (Python) and the Rust `openjd` built from `openjd-rs`
`af7e3c2`. The two outputs differ by exactly **3 bytes**, all inside the EXR `capDate` header
attribute — the capture timestamp. Every pixel is byte-identical, so the wrap environment behaves
the same under both implementations.

Each render produced a `sessions/output/<impl>-veach-mis.exr`:

| Property | Value |
|---|---|
| Format | OpenEXR, version 2 |
| Resolution | 1280 × 720 |
| Channels | A, B, G, R |
| Compression | ZIP |
| Size | 5,826,348 bytes |

MoonRay reported `Render time = 00:02:26.97` inside the container on the Rust run, against 149 s of
wall time for the whole session — so container startup, scene load and session setup account for
roughly two seconds. The 4 s spread between the two implementations is render noise, not a
meaningful difference: the CLI does nothing but start one container per task. For reference, the
`scene.exr` that ships alongside `veach-mis` is 5,798,529 bytes, within 0.5% of what these renders
produced.
