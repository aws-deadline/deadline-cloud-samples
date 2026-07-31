# Rez shim queue environment

Applies a resolved Rez context to each task by wrapping its command, instead of copying environment variables out of the queue environment and replaying them.

Choose this if your Rez packages configure software with anything other than plain environment variables. Studios commonly hit this when a package defines an `alias` for a launcher, relies on a shell function, or prepends to `PATH` expecting its own binary to shadow a system one. If your packages only set variables, the simpler [rez_queue_env.yaml](../rez_queue_env.yaml) works and needs no extra pieces.

## Contents

| File | Purpose |
|---|---|
| [`rez_queue_env_shim.yaml`](rez_queue_env_shim.yaml) | The queue environment to deploy on a farm |
| [`rez_demo_setup_queue_env.yaml`](rez_demo_setup_queue_env.yaml) | Test scaffolding: installs Rez and builds a demo package so the shim environment can run on a worker that has neither |
| [`demo_job_bundle/template.yaml`](demo_job_bundle/template.yaml) | A job that calls a Rez tool by bare name and verifies environment fidelity |

Only the first file belongs on a production queue. The other two exist to demonstrate and test it.

## Why the simpler sample cannot cover these cases

The limitation is structural. A queue environment action runs in its own subprocess, so the only way it can affect later actions is by printing `openjd_env: NAME=value` directives. To work within that, [rez_queue_env.yaml](../rez_queue_env.yaml) activates a context and then replays the difference between the environment before and after. Anything that is not a name-value pair does not survive that round trip.

A Rez `alias` is the clearest casualty. Rez implements it as an exported shell function, which Bash exports under a name like `BASH_FUNC_launch%%` with a multi-line value. The session runtime rejects that assignment outright:

```text
openjd_env: "BASH_FUNC_demoalias%%=() {  demorender --via-alias \"$@\"\n}"
  -- ERROR: Failed to parse environment variable assignment.
```

The alias is gone before any task runs.

## How the shim environment works

`onEnter` resolves the requested packages once and saves the context to a `.rxt` file in the session directory. It then asks Rez which executables those packages provide and writes one small shim per tool, prepending the shim directory to `PATH`:

```bash
#!/usr/bin/env bash
exec rez env --input "$REZ_CONTEXT_FILE" --shell bash -- "/abs/path/to/tool" "$@"
```

Job templates keep calling tools by bare name, such as `command: mayapy`, so each call re-enters the saved context in its own shell and Rez applies the full context inside the task's own process. Job bundles need no changes.

Tool names come from `rez context -t` on the saved context, so no list of executables is hard-coded. Set `RezExtraTools` for commands a package provides without declaring them in its `tools` list.

Each tool is resolved to an absolute path with `command -v` inside the context when its shim is written, rather than being re-resolved by name at task time. The reason is a recursion risk. By default Rez rebuilds `PATH` from the context and drops the shim directory, so a bare name is safe. On a farm whose Rez config lists `PATH` in `parent_variables`, though, the shim directory stays ahead of the package's own `bin`, and a bare name would find the shim again and fork until the worker ran out of processes. Resolving once up front removes that risk whatever the Rez configuration.

A tool that resolves back into the shim directory, or that the context cannot resolve at all, gets no shim. The environment reports it at startup and tasks fall back to whatever the worker provides.

## Parameters

The shim environment defines these:

| Parameter | Default | Purpose |
|---|---|---|
| `RezPackages` | `""` | Space-separated packages to resolve. Empty skips the environment |
| `RezRepositories` | `REZ_REPOSITORY_PATH` | Colon-separated package search path. Edit the per-platform defaults in the script for your farm |
| `RezExtraTools` | `""` | Extra command names to shim, for tools a package does not declare |

The demo setup environment and job add these:

| Parameter | Default | Purpose |
|---|---|---|
| `RezDemoRepository` | `/tmp/rez-demo-repository` | Where to build the demo package. Pass the same value as `RezRepositories` |
| `ToolName` | `demorender` | The command the first demo step invokes by bare name |
| `CancelSleepSeconds` | `600` | How long `CancelThroughShim` sleeps, giving you time to cancel the job |

## Deploy on a farm

Edit `LINUX_REZ_REPOSITORY_PATH` and `MACOS_REZ_REPOSITORY_PATH` in `rez_queue_env_shim.yaml` to your repository location, then create the queue environment:

```console
aws deadline create-queue-environment \
   --farm-id FARM_ID \
   --queue-id QUEUE_ID \
   --priority 2 \
   --template-type YAML \
   --template file://queue_environments/rez_shim/rez_queue_env_shim.yaml
```

Give it a higher priority number than any other environment that edits `PATH`, such as a Conda environment, because the last writer wins.

Workers need Rez installed and read access to the package repository. Neither is provided by service-managed fleet images by default.

## Try it without a farm

The demo setup environment installs Rez and builds a `demotool` package into the session, so the shim environment runs unmodified against it. Apply both environments in order:

```console
openjd run queue_environments/rez_shim/demo_job_bundle/template.yaml \
  --environment queue_environments/rez_shim/rez_demo_setup_queue_env.yaml \
  --environment queue_environments/rez_shim/rez_queue_env_shim.yaml \
  -p RezDemoRepository=/tmp/rez-demo-repository \
  -p RezPackages=demotool \
  -p RezRepositories=/tmp/rez-demo-repository \
  --step VerifyEnvironment
```

Pass the same directory as the setup environment's `RezDemoRepository` and the shim environment's `RezRepositories`.

To run it on a queue, attach the setup environment at a lower priority number than the shim environment and submit with the same parameters:

```console
deadline bundle submit queue_environments/rez_shim/demo_job_bundle \
  -p RezDemoRepository=/tmp/rez-demo-repository \
  -p RezPackages=demotool \
  -p RezRepositories=/tmp/rez-demo-repository
```

The demo needs a fleet of Linux or macOS workers with `python3` and network access to PyPI. A production farm provides Rez on the worker image and does not need the setup environment at all.

## What the demo verifies

`RunRezTool` calls `demorender` by bare name, so the shim is what runs. `VerifyEnvironment` then runs three checks and fails the task if any regress:

| Check | State under test | Under harvest-and-replay |
|---|---|---|
| 1 | A plain variable, `DEMOTOOL_VERSION` | Survives |
| 2 | A Rez `alias`, which becomes an exported shell function | Lost, rejected by the runtime |
| 3 | A `PATH` prepend where the package provides its own `sort` | Depends on environment order rather than the resolved context |

Every check reads its result from a tool called by bare name, so each one depends on the shim mechanism end to end rather than on the saved context alone. Deleting the `PATH` injection from the environment fails all three, which is how the checks were confirmed to test what they claim.

A third step, `CancelThroughShim`, is a manual check rather than an automatic one. It sleeps inside a shimmed tool for `CancelSleepSeconds` so you can cancel the job and watch the signal arrive. The tool reports the signal it caught before exiting. Cancel it from the monitor or with:

```console
aws deadline update-job --farm-id FARM_ID --queue-id QUEUE_ID \
  --job-id JOB_ID --target-task-run-status CANCELED
```

Expect the step to end as `CANCELED` with `demosleep: caught SIGTERM, exiting` in the session log. Left alone it simply runs to completion.

A successful session log shows the variable absent from the session but present inside the tool, then all three checks passing:

```text
=== DEMOTOOL_VERSION as seen by the session (expected UNSET) ===
DEMOTOOL_VERSION=UNSET
=== DEMOTOOL_VERSION as seen inside the tool (expected 1.0.0) ===
demorender: DEMOTOOL_VERSION=1.0.0
=== Check 1: plain variable reaches the tool ===
PASS: variable visible inside the tool
=== Check 2: Rez alias survives into the task ===
PASS: alias is callable
=== Check 3: package PATH prepend shadows the system command ===
PASS: package command shadows the system one
All 3 environment fidelity checks passed.
```

Running the same bundle under [rez_queue_env.yaml](../rez_queue_env.yaml) instead shows the runtime refusing the alias, which is the failure this environment avoids.

## Tradeoffs

* Only bare command names are intercepted. A template invoking an absolute path bypasses the shims.
* Linux and macOS workers only. The shims are POSIX shell scripts that depend on a shebang line, which does not work on Windows, so the environment fails immediately there with a message pointing at the alternative. Use [rez_queue_env.yaml](../rez_queue_env.yaml) for Windows fleets.
* Each task pays a context re-entry. Rez's resolve cache keeps this small, but it is not free.

Cancelation does reach through a shim. Rez runs the tool in a shell of its own, so the process tree is `shim` → `rez env` → shell → tool rather than flat, but a `SIGTERM` sent to the top process propagates to the tool and no orphans are left behind. Verified on a Linux service-managed fleet worker: canceling the `CancelThroughShim` step below produced

```text
INTERRUPT: Sending signal "term" to process 39247
demosleep: caught SIGTERM, exiting
```

Applications that install their own signal handlers still get the chance to shut down cleanly. Give `cancelation` a `NOTIFY_THEN_TERMINATE` mode in your step if a tool needs a grace period.

## A future specification change removes the need for this

This environment is a workaround for a gap in the environment specification rather than a permanent design. [RFC0008: Environment Wrap Actions](https://github.com/OpenJobDescription/openjd-specifications/issues/132) proposes `onWrapTaskRun`, letting a queue environment wrap each task's command directly instead of exporting variables to it. Once the worker agent supports that hook, it replaces both the shim directory and the `PATH` manipulation, and the tradeoffs above go away. The RFC has reached final comments upstream.

## Cleanup

The Rez installation, the `.rxt` context, and the shims are written under the session working directory and removed with the session. The demo package repository is not: it is created at `RezDemoRepository`, which defaults to `/tmp/rez-demo-repository` and persists on the worker until the instance is replaced. Delete it if you are testing on a long-lived worker, and detach the setup environment when finished.
