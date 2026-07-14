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

## Find and query samples

[`sample_catalog.json`](sample_catalog.json) is the human-edited, machine-readable source of truth.
[`SAMPLES.md`](SAMPLES.md) is generated for browsing and must not be edited directly. Query catalog
metadata without third-party dependencies, for example:

```console
python3 scripts/query_samples.py --task render-content
python3 scripts/query_samples.py --journey custom-plugins --platform windows
python3 scripts/query_samples.py --category job-bundle --tag blender
```

Run `python3 scripts/query_samples.py --help` for all filters. Paths are stable sample identities.
Discovery roots and intentional support-only exclusions are declared in the catalog's `inventory`
section and enforced against tracked Git files.

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
├── docs/                       Navigation and contributor contracts
├── scripts/                    Catalog generation and repository validation
├── sample_catalog.json         Human-edited sample metadata and inventory policy
└── SAMPLES.md                  Generated browseable sample index
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
* New, renamed, or removed samples must update `sample_catalog.json`; run
  `python3 scripts/generate_samples.py` after editing metadata.
* Do not add third-party runtime dependencies to repository validation.

## Pre-PR checklist

* [ ] Run `python3 scripts/validate_repository.py` successfully.
* [ ] Run the affected sample's own relevant tests or static checks.
* [ ] Update the sample README when behavior, prerequisites, parameters, outputs, or risks change.
* [ ] Update catalog metadata and regenerate `SAMPLES.md` when sample inventory or metadata changes.
* [ ] Use a [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) title.
* [ ] Sign off every commit under the [Developer Certificate of Origin](https://developercertificate.org/).
* [ ] Check changed content for inclusive language.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full contribution and licensing workflow.

## External references

* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [Open Job Description specification](https://github.com/OpenJobDescription/openjd-specifications/wiki)
