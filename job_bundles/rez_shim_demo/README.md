# Rez shim demo

Verifies that a Rez-provided tool can be invoked by bare command name from a job template, with the Rez environment applied per task by the [Rez shim queue environment](../../queue_environments/rez_queue_env_shim.yaml) rather than replayed from captured variables.

## What this sample demonstrates

A queue environment action runs in its own subprocess, so the only way it can affect later actions is by emitting `openjd_env` directives. The [Rez environment](../../queue_environments/rez_queue_env.yaml) therefore resolves a context, diffs the environment before and after, and replays the difference. That flattening loses shell functions, aliases, and ordered `PATH` edits.

The shim approach resolves once to a `.rxt` context file, writes one executable per Rez tool into the session directory, and prepends that directory to `PATH`. This bundle proves the result with two steps:

* `RunRezTool` calls `demorender` as a bare command name, so the shim is what actually runs.
* `VerifyEnvironment` runs three fidelity checks and fails the task if any of them regress.

The three checks cover increasingly demanding kinds of environment state:

| Check | State under test | Under harvest-and-replay |
|---|---|---|
| 1 | A plain variable, `DEMOTOOL_VERSION` | Survives |
| 2 | A Rez `alias`, which becomes an exported shell function | Lost. The session runtime rejects the `BASH_FUNC_demoalias%%` assignment |
| 3 | A `PATH` prepend where the package ships its own `sort` | Depends on environment order rather than the resolved context |

Check 2 is the sharpest: run this bundle under [rez_queue_env.yaml](../../queue_environments/rez_queue_env.yaml) and the session log shows the runtime refusing the alias with `ERROR: Failed to parse environment variable assignment`, which is why the alias cannot reach a task that way.

A future specification change will make this unnecessary. [RFC0008: Environment Wrap Actions](https://github.com/OpenJobDescription/openjd-specifications/issues/132), now in final comments upstream, adds `onWrapTaskRun` so a queue environment can wrap a task's command directly instead of exporting variables to it.

## Prerequisites

* A queue with two queue environments attached, in this order: [Rez demo setup](../../queue_environments/rez_demo_setup_queue_env.yaml) at the lower priority number, then [Rez shim](../../queue_environments/rez_queue_env_shim.yaml). The shim environment is used unmodified, so this exercises the same code a farm would run.
* A fleet of Linux or macOS workers. The shims are POSIX shell scripts and the environments fail on Windows workers.
* Workers with `python3` and network access to PyPI, because the setup environment installs Rez into the session directory. A production farm provides Rez on the worker image and does not need the setup environment.
* No Rez installation or package repository is required on the worker.

## How it works

The setup environment builds a `demotool` Rez package whose `commands()` sets `DEMOTOOL_VERSION` and `DEMOTOOL_LICENSE_SERVER`, and puts Rez on `PATH`. The shim environment then resolves that package, discovers tool names with `rez context -t`, and writes one shim per tool. Each shim re-enters the saved context and `exec`s the real tool, forwarding all arguments.

Pass the same directory as the setup environment's `RezDemoRepository` and the shim environment's `RezRepositories`.

## Run or submit

Run locally without a farm, applying both environments in order:

```console
openjd run job_bundles/rez_shim_demo/template.yaml \
  --environment queue_environments/rez_demo_setup_queue_env.yaml \
  --environment queue_environments/rez_queue_env_shim.yaml \
  -p RezDemoRepository=/tmp/rez-demo-repository \
  -p RezPackages=demotool \
  -p RezRepositories=/tmp/rez-demo-repository \
  --step RunRezTool --task-param Frame=1
```

Submit to a queue that has both environments attached:

```console
deadline bundle submit job_bundles/rez_shim_demo
```

## Parameters and outputs

| Parameter | Default | Purpose |
|---|---|---|
| `ToolName` | `demorender` | The Rez-provided command the first step invokes by bare name |

The job writes no output files. It reports through the session log and fails the task if any check regresses:

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
=== Result ===
All 3 environment fidelity checks passed.
```

`UNSET` in the session with `1.0.0` inside the tool is the core of the sample. The variable was never harvested and replayed; Rez applied it inside the task's own process.

## Security, cost, and cleanup

The Rez installation, the `.rxt` context, and the shims are written under the session working directory and removed with the session. The demo package repository is not: it is created at `RezDemoRepository`, which defaults to `/tmp/rez-demo-repository` and persists on the worker until the instance is replaced. Delete it if you are testing on a long-lived worker.

Costs are the usual worker running time, plus a per-session Rez install of roughly a minute. Detach the setup environment when finished, and detach or reconfigure the shim environment before pointing it at a real package repository.
