# Enforce Fixed License Limits with Submission Hooks

This sample demonstrates how to use [AWS Deadline Cloud Limits](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/deadline-cloud-limits.html) together with a [submission hook](https://github.com/aws-deadline/deadline-cloud/blob/mainline/docs/submission-hooks.md) to enforce a fixed number of concurrent VRay licenses across all job submissions, without requiring artists to configure anything manually.

## Overview

Studios often have a fixed number of floating licenses for renderers like V-Ray. AWS Deadline Cloud's **Limits** feature throttles task scheduling so that no more than N tasks requiring a license run concurrently. However, for the limit to take effect, each job must declare the license as a **host requirement** in its template.

The **pre-submission hook** in this sample injects the license host requirement into every job template at submission time, so:

- Artists submit jobs normally, with no extra steps required
- The hook ensures every job declares its need for the VRay license
- Deadline Cloud's scheduler enforces the concurrency limit

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Artist Workstation                                               │
│                                                                  │
│  deadline bundle submit my_job/                                  │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────────────────┐                           │
│  │ Pre-submission hook              │                           │
│  │ (inject_license_limit.py)        │                           │
│  │                                  │                           │
│  │ Reads template.yaml from bundle  │                           │
│  │ Injects hostRequirements:        │                           │
│  │   amounts:                       │                           │
│  │     - name: amount.vray          │                           │
│  │       min: 1                     │                           │
│  └──────────────────────────────────┘                           │
│       │                                                          │
│       ▼                                                          │
│  Job submitted with host requirement                             │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ AWS Deadline Cloud                                               │
│                                                                  │
│  Limit: "VRay License" (maxCount=5)                             │
│       │                                                          │
│       ▼                                                          │
│  Scheduler enforces: at most 5 tasks with amount.vray           │
│  run concurrently across all jobs in the queue                  │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- AWS CLI configured with permissions to manage Deadline Cloud resources
- [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) >= 0.58.0 (requires [PR #1162](https://github.com/aws-deadline/deadline-cloud/pull/1162) for environment hook template modification support)
- An existing Deadline Cloud farm, queue, and fleet
- Python 3.9+ with PyYAML installed (`pip install pyyaml`)

## Platform Support

This sample works on **Linux**, **macOS**, and **Windows**. The hook script is pure Python with no OS-specific code.

The `hooks.yaml` uses `python` as the command. If your environment only has `python3` on PATH (common on some Linux distributions), either:
- Create a symlink: `sudo ln -s /usr/bin/python3 /usr/local/bin/python`
- Or edit `hooks.yaml` to use `python3` instead

## Setup

### Step 1: Create a Limit

Create a limit on your farm that represents your VRay license pool. The `amountRequirementName` is the identifier that connects the limit to job host requirements.

```bash
aws deadline create-limit \
    --farm-id farm-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX \
    --display-name "VRay License" \
    --amount-requirement-name "amount.vray" \
    --max-count 5 \
    --description "Fixed pool of 5 VRay render licenses"
```

Note the `limitId` from the response.

### Step 2: Associate the Limit with Your Queue

```bash
aws deadline create-queue-limit-association \
    --farm-id farm-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX \
    --queue-id queue-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX \
    --limit-id limit-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Step 3: Verify Fleet Compatibility

When a limit is associated with a queue, fleets associated with that queue can schedule tasks that require the limit, with no additional fleet configuration needed.

> Do not add `amount.vray` as a `customAmounts` entry in your fleet's capabilities. If the fleet declares the amount as a capability, it treats it as a per-worker resource and bypasses the queue-level limit entirely. The limit association alone provides compatibility.

### Step 4: Deploy the Submission Hook

1. Copy the `license_limits/` directory to a shared location accessible by all artist workstations:

   **Linux/macOS:**
   ```bash
   cp -r license_limits/ /studio/pipeline/hooks/
   ```

   **Windows:**
   ```powershell
   Copy-Item -Recurse license_limits\ \\server\pipeline\hooks\
   ```

2. Configure each artist workstation to enable environment hooks:

   ```bash
   deadline config set settings.allow_environment_hooks true
   ```

3. Set the `DEADLINE_HOOKS_DIR` environment variable in your application launcher scripts:

   **Linux/macOS:**
   ```bash
   # Example: blender_launcher.sh
   export DEADLINE_HOOKS_DIR=/studio/pipeline/hooks/license_limits
   exec blender "$@"
   ```

   **Windows:**
   ```powershell
   # Example: blender_launcher.ps1
   $env:DEADLINE_HOOKS_DIR = "\\server\pipeline\hooks\license_limits"
   & "C:\Program Files\Blender Foundation\Blender\blender.exe" @args
   ```

   Or set it system-wide via System Environment Variables on Windows.

## Configuration

Edit `license_limits.json` to configure your license limits:

```json
{
    "limits": {
        "vray": {
            "amount_requirement_name": "amount.vray",
            "min": 1
        }
    }
}
```

| Field | Description |
|-------|-------------|
| `amount_requirement_name` | Must match the `amountRequirementName` used when creating the Limit |
| `min` | The number of license units each task consumes (typically 1) |

## How It Works

1. Artist submits a job via `deadline bundle submit` or a DCC submitter (Maya, Blender, etc.)
2. The pre-submission hook reads the job bundle's `template.yaml`
3. For each step, the hook injects a `hostRequirements.amounts` entry for `amount.vray`
4. The modified template is submitted to Deadline Cloud
5. The scheduler sees the `amount.vray` requirement and checks it against the Limit
6. If the limit's `maxCount` is already reached, the task stays in `READY` state until a slot frees up

## Testing

To verify the setup is working:

1. Set the limit to 1:
   ```bash
   aws deadline update-limit \
       --farm-id farm-XXX --limit-id limit-XXX --max-count 1
   ```

2. Submit two jobs with `sleep 60` as the render command

3. Observe that Job A runs while Job B stays in `READY` state

4. When Job A completes, Job B starts automatically

5. Reset the limit to your actual license count:
   ```bash
   aws deadline update-limit \
       --farm-id farm-XXX --limit-id limit-XXX --max-count 5
   ```

## Files

```
license_limits/
├── hooks.yaml                  # Hook configuration
├── inject_license_limit.py     # Pre-submission hook script
└── license_limits.json         # License limit configuration
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job marked `NOT_COMPATIBLE` | Limit not associated with the queue | Run `create-queue-limit-association` (Step 2) |
| Limit not enforced (jobs run concurrently) | Fleet has `customAmounts` with the limit name | Remove `customAmounts` from fleet (the limit association handles it) |
| Hook not running | Environment hooks not enabled | Run `deadline config set settings.allow_environment_hooks true` |
| Hook not running | `DEADLINE_HOOKS_DIR` not set | Set the environment variable in your launcher script |
| Limit not enforced | Queue-limit association missing | Run `create-queue-limit-association` (Step 2) |
| Limit not enforced | `amountRequirementName` mismatch | Ensure the limit name matches `license_limits.json` |

## Extending to Other Licenses

To add limits for additional products (e.g., Houdini, Nuke), add entries to `license_limits.json`:

```json
{
    "limits": {
        "vray": {
            "amount_requirement_name": "amount.vray",
            "min": 1
        },
        "houdini": {
            "amount_requirement_name": "amount.houdini",
            "min": 1
        },
        "nuke": {
            "amount_requirement_name": "amount.nuke",
            "min": 1
        }
    }
}
```

Then create corresponding Limits and queue associations for each product, and add the custom amounts to your fleet capabilities.
