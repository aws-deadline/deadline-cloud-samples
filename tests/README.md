# Static validation tests

Static, offline checks for the sample assets in this repository. They run in CI
on every pull request (see `.github/workflows/static_checks.yml`) and can be run
locally with:

```bash
python -m pip install -r tests/requirements.txt
python -m pytest tests -v
```

These checks exist to catch problems *before* a customer does. They are
deliberately fast and require no AWS credentials or network access.

## No skips

Every check that shells out to an external tool (`openjd`, `cfn-lint`,
`rattler-build`, `bash`, `pwsh`) **fails** if that tool is missing. It is
never skipped. A skipped check looks the same as a passing one in the CI
summary, which is precisely how a bad sample slips through. The CI workflow
installs all of these tools and verifies they are present before running the
suite. To run locally, install the tools listed in
[`requirements.txt`](./requirements.txt) plus `rattler-build`, `bash`, and
`pwsh` (PowerShell).

## What is checked

| Area | File | Check |
|------|------|-------|
| Open Job Description job & environment templates | `test_openjd_templates.py` | Every standalone template with an OpenJD `specificationVersion` passes `openjd check`. |
| Host configuration scripts | `test_host_configuration_scripts.py` | Byte length is within the Deadline Cloud service limit (`HostConfiguration.scriptBody` max **15000**). Linux (`*.sh`) scripts pass `bash -n`, and Windows (`*.ps1`) scripts parse with the PowerShell parser. |
| Utility scripts | `test_utility_scripts.py` | Linux (`*.sh`) scripts pass `bash -n`, and Windows (`*.ps1`) scripts parse with the PowerShell parser. Unlike a host configuration script, a utility script runs on a workstation rather than being uploaded to the service, so no `scriptBody` length limit applies. Some also run end to end in their own workflow. See [Beyond parsing](#beyond-parsing). |
| Queue environments | `test_openjd_templates.py` | Serialized `environment-2023-09` templates are within the service limit for `EnvironmentTemplate` (max **15000**). |
| CloudFormation templates | `test_cloudformation.py` | Templates parse as CloudFormation YAML (intrinsic tags such as `!Sub`/`!Ref` supported) and pass `cfn-lint` (errors only). |
| CDK apps | `test_cdk.py` | A queue environment copied into a CDK app is byte-identical to its original under `queue_environments/`. Everything else about a CDK app is proven by building it. See [Why so little here for CDK?](#why-so-little-here-for-cdk) |
| Conda recipes | `test_conda_recipes.py` | `deadline-cloud.yaml` matches the expected schema and its `buildTool` has a matching recipe file; **rattler-build** recipes (`recipe.yaml`) are validated with `rattler-build build --render-only`. **conda-build** recipes (`meta.yaml`) are rendered (Jinja + `# [selector]`) and structurally validated offline. |

A few recipes are deliberately fill-in-the-blanks templates that include a
placeholder source checksum for the user to replace (e.g.
`blender-plugin-bundle`). `rattler-build` rejects a non-hex placeholder, so the
check substitutes a syntactically valid dummy checksum into a temporary copy
before rendering. The full recipe is still validated, and only the
intentionally-blank checksum field is normalized. Genuinely invalid recipes
(unknown fields, bad structure) still fail.

### Beyond parsing

Parsing is the most this offline suite can prove about a script it must not run:
these install system packages and download roughly 1 GB, so executing one here
would defeat the "fast and offline" property the whole suite depends on.

Where a script is worth proving further, that belongs in its own workflow. The
[virtual workstation](../utility_scripts/virtual_workstation/) sample is run end
to end by
[`virtual_workstation_checks.yml`](../.github/workflows/virtual_workstation_checks.yml)
on Ubuntu 22.04 and Windows Server 2022, which asserts against the resulting
machine rather than against the script's own output. It is path-filtered to that
sample and also runs weekly, because the submitter and monitor it installs are
resolved as "latest" and can change with no commit here.

### Why so little here for CDK?

The CDK samples are TypeScript, and they are validated by building them: the
[`cdk_checks.yml`](../.github/workflows/cdk_checks.yml) workflow runs `npm ci`,
`tsc`, `jest`, `cdk synth` (with the default fleets and again with every fleet
enabled), and `cfn-lint` over the synthesized CloudFormation. Each of those
steps fails on its own if the app is misconfigured (a missing lock file breaks
`npm ci`, a bad entry point breaks `cdk synth`), so restating those invariants
as Python assertions would add maintenance without adding coverage. The app's
own assertions about the resources it produces live in its `test/` directory as
jest tests against the synthesized template.

That leaves one gap a per-app check cannot see: each CDK app carries a copy of a
queue environment that also lives under `queue_environments/`, and nothing
notices if the two drift apart. That comparison spans two directories, so it
lives in `test_cdk.py`. The copied template is also picked up by the repo-wide
OpenJD discovery above, so `openjd check` validates it like any other.

`cdk synth` needs the app's npm dependencies installed, which needs network
access. That is why it is a separate workflow rather than part of this offline
suite.

### Why not `conda render` for `meta.yaml`?

`conda-build`'s own `conda render` resolves dependencies against remote conda
channels, which needs network access and is non-deterministic (a solve can
start failing when an upstream package changes). That is a poor fit for a fast,
offline CI check, so `meta.yaml` is validated by rendering its Jinja/selectors
and checking the resulting document structure. `rattler-build --render-only`, by
contrast, validates fully offline without a dependency solve, so it is used
directly.

## Where the limits come from

The numeric limits in `service_limits.py` are taken from the AWS Deadline Cloud
API model (the `deadline` botocore service definition, API version
`2023-10-12`). The most important one for this repository is
`HostConfiguration.scriptBody`, whose maximum length is **15000** characters. A
host configuration script that exceeds it is rejected by `UpdateFleet`, which is
exactly the class of failure these checks are meant to catch early.
