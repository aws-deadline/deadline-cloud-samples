# Rez shim demo

Verifies that a Rez-provided tool can be invoked by bare command name from a job template, with the Rez environment applied per task by the [Rez shim queue environment](../../queue_environments/rez_queue_env_shim.yaml) rather than replayed from captured variables.

## What this sample demonstrates

A queue environment action runs in its own subprocess, so the only way it can affect later actions is by emitting `openjd_env` directives. The [Rez environment](../../queue_environments/rez_queue_env.yaml) therefore resolves a context, diffs the environment before and after, and replays the difference. That flattening loses shell functions, aliases, and ordered `PATH` edits.

The shim approach resolves once to a `.rxt` context file, writes one executable per Rez tool into the session directory, and prepends that directory to `PATH`. This bundle proves the result with two steps:

* `RunRezTool` calls `demorender` as a bare command name, so the shim is what actually runs.
* `VerifyEnvironment` shows that the tool's own variables are visible inside the tool's process but were never exported into the session.

## Prerequisites

* A Linux queue with the [Rez shim demo queue environment](../../queue_environments/rez_queue_env_shim_demo.yaml) attached.
* Workers with `python3` and network access to PyPI, because the demo environment installs Rez into the session directory. Real farms use `rez_queue_env_shim.yaml` and provide Rez on the worker image instead.
* No Rez installation or package repository is required on the worker for this demo.

## How it works

The demo queue environment builds a `demotool` Rez package whose `commands()` sets `DEMOTOOL_VERSION` and `DEMOTOOL_LICENSE_SERVER`, then discovers tool names with `rez context -t` and generates a shim per tool. Each shim re-enters the saved context and `exec`s the real tool, forwarding all arguments.

## Run or submit

```console
deadline bundle submit job_bundles/rez_shim_demo
```

Run a single task locally against the demo environment without a farm:

```console
openjd run job_bundles/rez_shim_demo/template.yaml \
  --environment queue_environments/rez_queue_env_shim_demo.yaml \
  --step RunRezTool --task-param Frame=1
```

## Parameters and outputs

| Parameter | Default | Purpose |
|---|---|---|
| `ToolName` | `demorender` | The Rez-provided command the first step invokes by bare name |

The job writes no output files. Success is shown in the session log:

```text
=== DEMOTOOL_VERSION as seen by the session (expected UNSET) ===
DEMOTOOL_VERSION=UNSET
=== DEMOTOOL_VERSION as seen inside the tool (expected 1.0.0) ===
demorender: DEMOTOOL_VERSION=1.0.0
```

`UNSET` in the session with `1.0.0` inside the tool is the point of the sample. The variable was never harvested and replayed; Rez applied it inside the task's own process.

## Security, cost, and cleanup

Everything the demo creates, including the Rez installation, the demo package repository, the `.rxt` context, and the shims, is written under the session working directory and removed with the session. Costs are the usual worker running time, plus a first-session Rez install of roughly a minute. Detach the demo queue environment when finished.
