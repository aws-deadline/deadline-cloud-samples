# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.

Table of contents:

* [Reporting Bugs/Feature Requests](#reporting-bugsfeature-requests)
* [Development](#development)
    * [Finding contributions to work on](#finding-contributions-to-work-on)
    * [Talk with us first](#talk-with-us-first)
    * [Contributing via Pull Requests](#contributing-via-pull-requests)
    * [Adding or updating a sample](#adding-or-updating-a-sample)
    * [Conventional Commits](#conventional-commits)
* [Licensing](#licensing)

## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can.

## Development

We welcome you to contribute features to existing samples, bug fixes, and new samples via a
[pull request](https://help.github.com/articles/creating-a-pull-request/). If you are new to contributing
to GitHub repositories, then you may find the
[GitHub documentation on collaborating with the fork and pull model](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/about-collaborative-development-models#fork-and-pull-model)
informative; this is the model that we follow.

### Finding contributions to work on

If you are not sure what you would like to contribute, then looking at the existing issues is a great way to find
something to contribute on. [Issues that have the "help wanted" or "good first issue" labels](https://github.com/aws-deadline/deadline-cloud-samples/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22%2C%22help+wanted%22)
are a good place to start, but please dive into any issue that interests you whether it has those labels or not.

### Talk with us first

We ask that you please [open a feature request issue](https://github.com/aws-deadline/deadline-cloud-samples/issues/new/choose)
(if one does not already exist) and talk with us before posting a pull request that contains a significant amount of work.
We want to make sure that your time and effort is respected by working with you to design the change before you spend much
of your time on it. If you want to create a draft pull request to show what you are thinking and then talk with us, then that
works with us as well.

### Contributing via Pull Requests

Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *mainline* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.
4. Your pull request will be focused on a single change - it is easier for us to understand when a change is focused rather
   than changing multiple things at once.

To send us a pull request, please:

1. Fork the repository.
2. Modify and test the sample that you are modifying/adding.
3. Commit to your fork using clear commit messages. Note that all AWS Deadline Cloud GitHub repositories require the use
   of [conventional commit](#conventional-commits) syntax for the title of your commit.
4. Send us a pull request, answering any default questions in the pull request interface.
5. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional documentation on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).

### Adding or updating a sample

Each sample area and nested collection declares its tracked scope in a category README. Its table is
the complete index of user-selectable samples in that scope; implementation files and support
infrastructure can be documented in nearby prose instead. Do not add a generated catalog, metadata
schema, or other parallel inventory. When you add, rename, move, or delete a sample:

1. Put it in the appropriate top-level area and give a nontrivial sample its own README.
2. Update the nearest category table so its relative link and task-oriented description remain
   accurate. If a move crosses category boundaries, update both affected tables.
3. Change the root README navigation only when a recommended path or starting point changes; do not
   duplicate the category's exhaustive index at the root.
4. Use [`docs/SAMPLE_README_TEMPLATE.md`](docs/SAMPLE_README_TEMPLATE.md) as a suggested starting point
   for a nontrivial sample. Adapt it freely: remove irrelevant prompts, rename/reorder/combine
   sections, and add material that helps users choose, run, and clean up the sample.
5. Run the complete local unit and static validation from the repository root:

   ```console
   python3 scripts/validate_repository.py
   ```

The top-level command uses only the Python standard library. It runs all checker unit tests and checks
local links, including same-document and cross-document anchors, in every tracked Markdown file. Also
run tests specific to the sample you changed; for OpenJD templates, validate and run a representative
task locally when possible.

Live external links are intentionally a separate network-dependent validation mode:

```console
python3 scripts/check_external_links.py
```

The live checker aggregates source locations, validates every URL, redirect, and DNS answer against
public-network-only rules, tries `HEAD` before a minimal one-byte `GET`, and does not honor environment
proxy settings. It checks all external Markdown links on pull requests, mainline pushes, the weekly
schedule, and manual workflow runs.

The narrow [external-link ignore file](.github/external-link-ignore.txt) is only for domains that
empirically reject both checker requests as bot traffic. Before adding an exact domain, run the audit:

```console
python3 scripts/check_external_links.py --no-ignore
```

Confirm the failure is a repeatable bot rejection rather than a missing page, then add the exact domain
with an immediately preceding dated comment that records the observed status or error. Entries match
the domain and true subdomains by DNS-label boundary only; wildcards and substring matching are not
supported. Ignores apply only to original link hosts, never redirect destinations. Fix genuine broken
links, including HTTP 404 responses, instead of ignoring them.

### Conventional commits

The commits in this repository are all required to use [conventional commit syntax](https://www.conventionalcommits.org/en/v1.0.0/)
in their title to help us identify the kind of change that is being made, automatically generate the changelog, and
automatically identify next release version number. Only the first commit that deviates from mainline in your pull request
must adhere to this requirement.

We ask that you use these commit types in your commit titles:

* `feat` - When the pull request adds a new feature or functionality to an existing sample, or adds a new sample;
* `fix` - When the pull request is implementing a fix to a bug;
* `test` - When the pull request is only implementing an addition or change to tests or the testing infrastructure;
* `docs` - When the pull request is primarily implementing an addition or change to the package's documentation;
* `refactor` - When the pull request is implementing only a refactor of existing code;
* `ci` - When the pull request is implementing a change to the CI infrastructure of the package;
* `chore` - When the pull request is a generic maintenance task.

We also require that the type in your conventional commit title end in an exclamation point (e.g. `feat!` or `fix!`)
if the pull request should be considered to be a breaking change in some way. Please also include a "BREAKING CHANGE" footer
in the description of your commit in this case ([example](https://www.conventionalcommits.org/en/v1.0.0/#commit-message-with-both--and-breaking-change-footer)).
Examples of breaking changes include any change that implements a backwards-incompatible change to a public Python interface,
the command-line interface, or the like.

If you need to change a commit message, then please see the
[GitHub documentation on the topic](https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/changing-a-commit-message)
to guide you.

## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.

## Contributing a 3ds Max Host Config Add-on

The `skills/3dsmax-host-config/add-ons/` folder contains building blocks that Kiro uses to generate
host configuration scripts for 3ds Max plugins. If you have tested a plugin combination that isn't
covered yet, you can contribute a new add-on by:

1. Create a new `.md` file in `skills/3dsmax-host-config/add-ons/` named after the plugin (e.g. `redshift.md`)
2. Follow the structure of the existing add-ons — include a brief description, a reference script path, a "What to add to the script" section, and any important notes
3. Add a working example `.ps1` script under `host_configuration_scripts/3dsmax/` that has been tested
4. Open a pull request with both the add-on `.md` and the example script
