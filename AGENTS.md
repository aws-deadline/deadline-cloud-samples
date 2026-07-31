# AGENTS.md: deadline-cloud-samples

This file gives AI coding assistants the context they need to work effectively in this repository.

## What this repo is

`deadline-cloud-samples` is a public collection of samples for
[AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/). It is not a single buildable package;
each sample is self-contained. The repository does have one top-level, standard-library-only static
validation command:

```console
python3 scripts/validate_repository.py
```

Run it after every repository change, along with tests or validation owned by the sample you edit.
External Markdown links use a separate network-dependent command:

```console
python3 scripts/check_external_links.py
```

Use `--no-ignore` to audit the narrowly documented domain ignore list before changing it. Real
broken links must be fixed rather than ignored.

## Find samples

Start with the task paths and repository map in [`README.md`](README.md), then use the nearest area or
collection README. Its index table is complete for the scope it declares. Search tracked paths or
contents directly when you need implementation or support files that are intentionally excluded from
user-selectable sample tables.

## Where things live

```text
deadline-cloud-samples/
├── cloudformation/             CloudFormation farm and infrastructure templates
├── terraform/                  Terraform farm and infrastructure templates
├── cdk/                        AWS CDK farm apps (TypeScript)
├── job_bundles/                OpenJD job bundles (template.yaml plus assets)
├── conda_recipes/              DCC and application Conda recipes
├── containers/                 Worker-compatible and application containers
├── queue_environments/         Session software environments (Conda, Rez, and pip)
├── host_configuration_scripts/ Privileged service-managed fleet setup scripts
├── submission_hooks/           Pre-submission Deadline Cloud CLI hooks
├── utility_scripts/            Standalone workflow helpers
├── skills/                     Task-specific guides for coding agents
├── docs/                       Contributor guidance and documentation starting points
└── scripts/                    Standard-library repository validation
```

Read the relevant sample `README.md` before modifying its files. Use
[`docs/SAMPLE_README_TEMPLATE.md`](docs/SAMPLE_README_TEMPLATE.md) as an adaptable starting point when
adding a nontrivial sample.

Before implementing a sample, inspect [`skills/`](skills/) for a matching `SKILL.md` guide.

## Repository conventions

* Use inclusive language: prefer `primary`/`replica` and `allowlist`/`denylist`.
* Use `pip install ...` in cross-platform Python instructions; avoid `pip3` unless the sample is
  explicitly Linux/macOS-only.
* Job bundles live under `job_bundles/<name>/` with a `template.yaml`, optional
  `parameter_values.yaml`, and a `README.md` for nontrivial samples.
* Conda recipes live under `conda_recipes/<package>-<version>/` with a `recipe/` directory and
  `deadline-cloud.yaml`.
* For OpenJD templates, run `openjd check` and `openjd run --tasks <one>` to verify a representative
  task locally before submitting the full parameter range when possible.
* Add, rename, move, or delete a sample in the nearest category table. Change root navigation only
  when a recommended path changes.
* Keep indexes in Markdown. Do not add catalog or metadata-generation machinery.
* Do not add third-party runtime dependencies to repository validation.

## Pre-PR checklist

* [ ] Run `python3 scripts/validate_repository.py` successfully (unit tests and static local-link checks).
* [ ] Run `python3 scripts/check_external_links.py` successfully when Markdown links change.
* [ ] Run the affected sample's own relevant tests or static checks.
* [ ] Update the sample README when behavior, prerequisites, parameters, outputs, or risks change.
* [ ] Update the nearest category table when a sample is added, renamed, moved, or deleted.
* [ ] Update root task paths only when a recommended starting point changes.
* [ ] Use a [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) title.
* [ ] Sign off every commit under the [Developer Certificate of Origin](https://developercertificate.org/).
* [ ] Check changed content for inclusive language.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution and licensing workflow.

## External references

* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [Open Job Description specification](https://github.com/OpenJobDescription/openjd-specifications/wiki)
