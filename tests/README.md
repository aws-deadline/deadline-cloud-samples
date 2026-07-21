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
`rattler-build`, `bash`, `pwsh`) **fails** if that tool is missing -- it is
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
| Host configuration scripts | `test_host_configuration_scripts.py` | Byte length is within the Deadline Cloud service limit (`HostConfiguration.scriptBody` max **15000**); Linux (`*.sh`) scripts pass `bash -n`; Windows (`*.ps1`) scripts parse with the PowerShell parser. |
| Queue environments | `test_openjd_templates.py` | Serialized `environment-2023-09` templates are within the service limit for `EnvironmentTemplate` (max **15000**). |
| CloudFormation templates | `test_cloudformation.py` | Templates parse as CloudFormation YAML (intrinsic tags such as `!Sub`/`!Ref` supported) and pass `cfn-lint` (errors only). |
| Conda recipes | `test_conda_recipes.py` | `deadline-cloud.yaml` matches the expected schema and its `buildTool` has a matching recipe file; **rattler-build** recipes (`recipe.yaml`) are validated with `rattler-build build --render-only`; **conda-build** recipes (`meta.yaml`) are rendered (Jinja + `# [selector]`) and structurally validated offline. |

A few recipes are deliberately fill-in-the-blanks templates that ship a
placeholder source checksum for the user to replace (e.g.
`blender-plugin-bundle`). `rattler-build` rejects a non-hex placeholder, so the
check substitutes a syntactically valid dummy checksum into a temporary copy
before rendering — the full recipe is still validated, only the
intentionally-blank checksum field is normalized. Genuinely invalid recipes
(unknown fields, bad structure) still fail.

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
`HostConfiguration.scriptBody`, whose maximum length is **15000** characters — a
host configuration script that exceeds it is rejected by `UpdateFleet`, which is
exactly the class of failure these checks are meant to catch early.
