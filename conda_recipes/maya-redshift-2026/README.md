# Redshift for Maya conda build recipe

Redshift 2026.8.1 support for Maya versions 2025, 2026 and 2027.

## Supported Maya Versions

- Maya 2025
- Maya 2026
- Maya 2027

Maya 2027 requires Redshift 2026.6.0 or later, so do not downgrade this recipe below that version
if you need Maya 2027 support.

## Download the installer file for Linux

Download the redshift_2026.8.1_2741261432_linux_x64.run installer, or suitable alternate version from Maxon, and
place it in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for
submitting package build jobs.

Please note that if the installer version used differs from "redshift_2026.8.1_2741261432_linux_x64.run", version
and filename updates will need to be made to deadline-cloud.yaml and recipe/recipe.yaml
