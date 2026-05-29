---
name: deadline-cloud-job
description: >
  Create AWS Deadline Cloud jobs as Open Job Description (OpenJD) job bundles, 
  with optional conda packaging. Use when asked to "create a Deadline Cloud
  job", "create a job bundle", "write an OpenJD template", "add a new sample
  job", "create a render job for <DCC>", or when a new workflow needs a job
  template with parameters, steps, and environments.
tags: [skill, deadline-cloud, job-bundle, openjd, template, conda]
---

# Deadline Cloud Job Skill

Create AWS Deadline Cloud jobs as Open Job Description (OpenJD) job bundles,
with optional conda packaging.

## Overview

Open Job Description is a portable job definition language. This skill helps
create job bundle templates targeting AWS Deadline Cloud, optionally with conda
package recipes for dependency management.

New job bundles live under `job_bundles/`. Conda recipes live under
`conda_recipes/`. Both directories already contain working samples that this
skill uses as references.

## Usage

Use this skill when:
- A new workflow or DCC needs an OpenJD job bundle template
- An existing job bundle needs new parameters, steps, or environments
- A custom dependency needs a conda package recipe for a Deadline Cloud queue
- Someone asks "create a job bundle for X" or "add a sample job that does Y"

## Process

1. **Design the job** — Define parameters, steps, environments, and dependencies
2. **Write the template** — Create the OpenJD YAML template
3. **Test locally** (optional, recommended) — Iterate with `openjd run --tasks <one>` until end-to-end success (see Testing section). Skip if you prefer to iterate directly on Deadline Cloud.
4. **Add a conda recipe** (optional) — For custom software dependencies
5. **Submit to a farm** — Test on Deadline Cloud

## Testing with openjd CLI

Install the CLI tool for local template validation if it isn't already
installed:

```bash
pip install openjd-cli
```

Key commands for testing templates:

```bash
# Validate template syntax
openjd check template.yaml

# List steps in a template
openjd summary template.yaml

# Run a template locally
openjd run --step StepName template.yaml

# Run with parameter values
openjd run --step StepName -p ParamName=value template.yaml

# Run a specific task
openjd run --step StepName --tasks Frame=1 template.yaml
```

**Iterate locally until the job runs end-to-end before submitting to Deadline
Cloud.** Use `openjd check` to catch schema errors, then `openjd run` each step
with realistic parameter values until every step exits cleanly. Farm
submissions are slow and consume queue resources — fix template bugs, missing
dependencies, and path issues locally first.

For local iteration, run a **minimal subset** of the parameter space — one
frame, one chunk, one task — to verify the script works. Use `--tasks` to pin
a single value:

```bash
openjd run --step RenderStep --tasks Frame=1 template.yaml
```

If the job depends on a queue environment (e.g. for conda packages), pass it
with `--environment` so the local run sets up the same software environment
the farm would:

```bash
openjd run template.yaml \
    --environment ../../queue_environments/conda_queue_env_pyrattler.yaml \
    --step RenderStep --tasks Frame=1
```

See [`job_bundles/gsplat_pipeline/README.md`](../../job_bundles/gsplat_pipeline/README.md)
("Run the job anywhere with the Open Job Description CLI") for a worked example.

Once a single task succeeds locally, submit to Deadline Cloud with the full
parameter range (e.g. `Frames=1-100`) so the farm fans the work out across
workers in parallel.

## Reference Sources

Read these in order based on what you need.

### Core OpenJD Specification

| Source | When to Read |
|--------|--------------|
| [Template Schemas](https://raw.githubusercontent.com/OpenJobDescription/openjd-specifications/mainline/wiki/2023-09-Template-Schemas.md) | Complete schema reference for job templates |
| [How Jobs Are Run](https://raw.githubusercontent.com/OpenJobDescription/openjd-specifications/mainline/wiki/How-Jobs-Are-Run.md) | Sessions, environments, path mapping, stdout messages |
| [Introduction to Creating a Job](https://raw.githubusercontent.com/OpenJobDescription/openjd-specifications/mainline/wiki/Introduction-to-Creating-a-Job.md) | Step-by-step tutorial walkthrough |

### Sample job bundles in this repo

| Source | When to Read |
|--------|--------------|
| [`job_bundles/README.md`](../../job_bundles/README.md) | Overview of all sample job bundles |
| [`job_bundles/cli_job/template.yaml`](../../job_bundles/cli_job/template.yaml) | Minimal CLI-driven template example |
| [`job_bundles/blender_render/template.yaml`](../../job_bundles/blender_render/template.yaml) | Full DCC render job with parameters |
| [`job_bundles/gui_control_showcase/template.yaml`](../../job_bundles/gui_control_showcase/template.yaml) | All UI control types |
| [`job_bundles/job_dev_progression/`](../../job_bundles/job_dev_progression/) | Progressive complexity examples |

### Conda packaging (only if creating custom packages)

| Source | When to Read |
|--------|--------------|
| [Configure jobs with an S3 conda channel](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html) | Setting up and using an S3 conda channel with Deadline Cloud |
| [`conda_recipes/README.md`](../../conda_recipes/README.md) | Recipe structure and submission |
| [`skills/conda-builder/SKILL.md`](../conda-builder/SKILL.md) | End-to-end recipe creation and local build/test workflow |

## Template Structure Quick Reference

```yaml
specificationVersion: 'jobtemplate-2023-09'
# Opt into OpenJD extensions; see the "Extensions available for specification
# version 2023-09" list in the spec for the full set:
# https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#1-job-template
extensions:
  - REDACTED_ENV_VARS  # redact env var values from session logs
name: "{{Param.JobName}}"  # Format strings use {{ }}

parameterDefinitions:
  - name: InputFile
    type: PATH           # PATH, STRING, INT, FLOAT
    objectType: FILE     # FILE or DIRECTORY (for PATH)
    dataFlow: IN         # IN, OUT, INOUT, NONE
    userInterface:
      control: CHOOSE_INPUT_FILE
      label: "Input File"
      groupLabel: "Input Settings"

  - name: Frames
    type: STRING
    default: "1-10"

jobEnvironments:
  # Fetch a secret once per session and expose it as $API_TOKEN to all steps.
  # `openjd_redacted_env:` requires the REDACTED_ENV_VARS extension above; it
  # sets the variable like `openjd_env:` but redacts the value to ******** in
  # session logs. The variable is still readable by other processes on the
  # host — this only protects log output.
  - name: Credentials
    script:
      actions:
        onEnter:
          command: bash
          args: ['{{Env.File.Enter}}']
      embeddedFiles:
        - name: Enter
          type: TEXT
          data: |
            set -euo pipefail
            SECRET="$(aws secretsmanager get-secret-value \
                --secret-id my/api/token --query SecretString --output text)"
            echo "openjd_redacted_env: API_TOKEN=$SECRET"

steps:
  - name: RenderStep
    parameterSpace:           # Creates tasks from parameter combinations
      taskParameterDefinitions:
        - name: Frame
          type: INT
          range: "{{Param.Frames}}"

    script:
      actions:
        onRun:
          command: bash
          args: ['{{Task.File.Run}}']
      embeddedFiles:
        - name: Run
          type: TEXT
          data: |
            set -xeuo pipefail
            echo "Rendering frame {{Task.Param.Frame}} (token: $API_TOKEN)"
```

## Dependency Management Options

For Deadline Cloud samples, prefer these approaches in order:

1. **Conda package recipe** (preferred for service-managed fleets) — check into
   `conda_recipes/`. See [`skills/conda-builder/SKILL.md`](../conda-builder/SKILL.md).
2. **Job/Step environment** — install from pypi/apt/etc. in the template's
   environment section.
3. **Pre-installed on the fleet** — for customer-managed fleets with custom AMIs.

### Conda recipe structure

```
conda_recipes/
└── my-package-1.0/
    ├── deadline-cloud.yaml    # Build platforms and metadata
    └── recipe/
        ├── meta.yaml          # conda-build recipe (or recipe.yaml for rattler-build)
        └── build.sh           # Build script
```

### Job environment for dependencies used in multiple steps

```yaml
jobEnvironments:
  - name: PythonDeps
    script:
      actions:
        onEnter:
          command: bash
          args: ['{{Env.File.Setup}}']
      embeddedFiles:
        - name: Setup
          type: TEXT
          data: |
            pip install some-package==1.2.3
```

Use a step environment for dependencies used in only one step.

## Submitting Jobs

```bash
# GUI submission
deadline bundle gui-submit path/to/job_bundle/

# CLI submission
deadline bundle submit path/to/job_bundle/ \
    -p InputFile=/path/to/input \
    -p OutputDir=/path/to/output

# Submit to a specific queue
deadline bundle submit path/to/job_bundle/ --queue "My Queue"

# Wait up to 5 minutes for the job to finish
deadline job wait --job-id {jobId} --timeout 300
```

## Key Concepts

- **Format strings**: `{{Param.Name}}`, `{{Task.Param.Name}}`, `{{Task.File.Name}}`
- **Parameter space**: defines how tasks are generated from parameter combinations
- **Sessions**: runtime environment on a worker; environments are entered/exited around tasks
- **Path mapping**: automatic path translation between submission and worker hosts
- **Host requirements**: CPU, memory, GPU constraints for scheduling
