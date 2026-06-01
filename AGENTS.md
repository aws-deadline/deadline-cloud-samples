# AGENTS.md — deadline-cloud-samples

This file gives AI coding assistants (Codex CLI, Aider, Cline, Continue,
Cursor, Copilot, Gemini, ChatGPT, Claude Code, Kiro, etc.) the context they
need to work effectively in this repository.

## What this repo is

`deadline-cloud-samples` is a public collection of samples for
[AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/). It is **not** a
single buildable package — there is no top-level build, test, or lint command.
Each sample is self-contained.

## Where things live

```
deadline-cloud-samples/
├── job_bundles/          OpenJD job bundle samples (template.yaml + assets)
├── conda_recipes/        Conda recipes for DCC packages used by Deadline Cloud
├── queue_environments/   Queue environment YAMLs (Conda/Rez software providers)
├── host_configuration_scripts/  Per-OS scripts for service-managed fleet workers
├── submission_hooks/     Pre-submission Python hooks for the Deadline Cloud CLI
├── containers/           Dockerfiles (e.g. AL2023 worker-equivalent for local builds)
├── cloudformation/       CloudFormation farm + infra templates
├── terraform/            Terraform farm + infra templates
├── utility_scripts/      Standalone CLI helpers
└── skills/               LLM-agnostic, task-specific guides (see below)
```

**Most samples have their own `README.md`** with prerequisites, parameters,
and run/submit instructions. Read the relevant `README.md` before modifying
or adding to a sample directory.

## Skills — task-specific instructions

The [`skills/`](./skills/) directory contains self-contained, LLM-agnostic
guides for common tasks. Each skill is a Markdown file with YAML frontmatter
(`name`, `description`, `tags`) followed by step-by-step instructions,
references, and examples.

**Before starting work, check `skills/` for a matching guide and read it.**
The `description` field tells you when to use each skill.

| Skill | Use when |
|-------|----------|
| [`skills/deadline-cloud-job/`](./skills/deadline-cloud-job/SKILL.md) | Creating or updating a Deadline Cloud job (OpenJD job bundle) under `job_bundles/` |
| [`skills/conda-builder/`](./skills/conda-builder/SKILL.md) | Creating or updating a DCC conda recipe under `conda_recipes/` |
| [`skills/3dsmax-host-config/`](./skills/3dsmax-host-config/SKILL.md) | Creating or updating a 3ds Max host configuration script |
| [`skills/host-config-from-installer/`](./skills/host-config-from-installer/SKILL.md) | Creating a host configuration script from a vendor installer |

Skills are auto-discovered via `.claude/skills` and `.kiro/skills` symlinks.
For other tools, point your assistant at the relevant `SKILL.md` directly
(paste, `@`-mention, or include in context).

## Repo conventions

- **Inclusive language** — avoid `master`/`slave`, `whitelist`/`blacklist`.
  Use `primary`/`replica`, `allowlist`/`denylist`.
- **Python install commands** — use `pip install ...` (works on Windows,
  macOS, and Linux). Avoid `pip3` unless the sample is Linux/macOS-only.
- **Job bundles** live under `job_bundles/<name>/` with a `template.yaml`,
  optional `parameter_values.yaml`, and a `README.md`.
- **Conda recipes** live under `conda_recipes/<package>-<version>/` with a
  `recipe/` subdirectory and a `deadline-cloud.yaml`.
- **Iterate locally before submitting** — for OpenJD templates, run
  `openjd check` and `openjd run --tasks <one>` to verify a single task end-
  to-end before submitting the full parameter range to a Deadline Cloud farm.

## Before You Commit

**Every commit title MUST use [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) syntax.**
PRs without it will be blocked by CI. Use one of these types:

| Type       | Use for                                                   |
|------------|-----------------------------------------------------------|
| `feat`     | New sample, new feature in an existing sample             |
| `fix`      | Bug fix                                                   |
| `docs`     | Documentation only                                        |
| `test`     | Test additions or changes only                            |
| `refactor` | Code refactor with no behavior change                     |
| `ci`       | CI infrastructure changes                                 |
| `chore`    | Generic maintenance                                       |
| `feat!` / `fix!` | Breaking change (also add `BREAKING CHANGE:` footer) |

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full contribution workflow.

## External references

- [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
- [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
- [Open Job Description spec](https://github.com/OpenJobDescription/openjd-specifications/wiki)
- [`README.md`](./README.md) — directory overview and high-level usage
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — full contribution workflow, MIT-0 licensing, security reporting
