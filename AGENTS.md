# AGENTS.md — deadline-cloud-samples

This file gives AI coding assistants the context they need to work effectively in this repository.

## What this repo is

`deadline-cloud-samples` is a public collection of samples for
[AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/). It is not a single buildable package;
each sample is self-contained. The repository does have one top-level, standard-library-only static
validation command:

```console
python3 scripts/validate_repository.py
```

Run it after every repository change, in addition to tests or validation owned by the sample you edit.
External Markdown links use a separate network-dependent command:

```console
python3 scripts/check_external_links.py
```

Use `--no-ignore` to audit the narrowly documented domain ignore list before changing it; genuine
broken links must be fixed rather than ignored.

## Find samples

The filesystem is the exhaustive sample inventory. Browse the top-level area directories directly and
search their paths or contents (for example, with `find` and `git grep`) when looking for a specific
application, renderer, workflow, or platform. Start with the task table and repository map in
[`README.md`](README.md) when you want recommendations. Folder READMEs and
[`docs/sample-navigation.md`](docs/sample-navigation.md) are curated introductions; they may
intentionally highlight only recommended canonical examples and are not complete inventories.

## Where things live

```text
deadline-cloud-samples/
├── cloudformation/             CloudFormation farm and infrastructure templates
├── terraform/                  Terraform farm and infrastructure templates
├── job_bundles/                OpenJD job bundles (template.yaml plus assets)
├── conda_recipes/              DCC and application Conda recipes
├── containers/                 Worker-compatible and application containers
├── queue_environments/         Session software environments (Conda, Rez, and pip)
├── host_configuration_scripts/ Privileged service-managed fleet setup scripts
├── submission_hooks/           Pre-submission Deadline Cloud CLI hooks
├── utility_scripts/            Standalone workflow helpers
├── skills/                     Task-specific guides for coding agents
├── docs/                       Curated navigation and contributor contracts
└── scripts/                    Standard-library repository validation
```

Read the relevant sample `README.md` before modifying its files. Use
[`docs/sample-navigation.md`](docs/sample-navigation.md) to choose an application, plugin, or studio
integration path, and [`docs/SAMPLE_README_TEMPLATE.md`](docs/SAMPLE_README_TEMPLATE.md) when adding
a nontrivial sample.

## Skills — task-specific instructions

Before starting sample implementation, check [`skills/`](skills/) for a matching guide and read it.
Each skill has YAML frontmatter followed by instructions, references, and examples.

| Skill | Use when |
|---|---|
| [`skills/deadline-cloud-job/`](skills/deadline-cloud-job/SKILL.md) | Creating or updating an OpenJD job bundle under `job_bundles/` |
| [`skills/conda-builder/`](skills/conda-builder/SKILL.md) | Creating or updating a DCC Conda recipe under `conda_recipes/` |
| [`skills/3dsmax-host-config/`](skills/3dsmax-host-config/SKILL.md) | Creating or updating a 3ds Max host configuration script |
| [`skills/host-config-from-installer/`](skills/host-config-from-installer/SKILL.md) | Creating a Windows host configuration script from a vendor installer |

Skills are auto-discovered through `.claude/skills` and `.kiro/skills` symlinks.

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
* Keep the filesystem as the inventory; update curated folder, root, or journey guidance only when
  recommended starting points change.
* Do not add third-party runtime dependencies to repository validation.

## Pre-PR checklist

* [ ] Run `python3 scripts/validate_repository.py` successfully (unit tests and static local-link checks).
* [ ] Run `python3 scripts/check_external_links.py` successfully when Markdown links change.
* [ ] Run the affected sample's own relevant tests or static checks.
* [ ] Update the sample README when behavior, prerequisites, parameters, outputs, or risks change.
* [ ] Update curated folder or journey guidance only when recommended starting points change.
* [ ] Use a [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) title.
* [ ] Sign off every commit under the [Developer Certificate of Origin](https://developercertificate.org/).
* [ ] Check changed content for inclusive language.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution and licensing workflow.

## External references

* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [Open Job Description specification](https://github.com/OpenJobDescription/openjd-specifications/wiki)
