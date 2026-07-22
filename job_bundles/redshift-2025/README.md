# Redshift Rendering Job Template 

This job template allows you to render Redshift scenes using the standalone redshiftCmdLine.exe executable that comes with Cinema 4D 2025. The template is designed for Windows systems only and uses the Redshift command line renderer directly. Cinema4D is used because the deadline-cloud conda channel includes it along with the redshift CLI renderer.

## Overview

This template demonstrates how to create an AWS Deadline Cloud job template for rendering with Redshift's standalone command line executable. The template:
- Installs Cinema 4D 2025 via conda package (which includes Redshift)
- Configures Windows host requirements
- Uses redshiftCmdLine.exe directly for rendering

## Requirements

- Windows operating system
- Redshift compatible GPU
- Cinema 4D 2025 conda package (cinema4d=2025) with Redshift included
- Valid Redshift scene file (.rs)

## Template Parameters

### Scene Parameters
- **SceneFile**: The Redshift scene file (.rs) to render (default: jet.rs)

### Output Parameters
- **OutputDir**: Directory where the rendered output will be saved (default: ./output)

### Render Settings
- **Width**: The width of the rendered image (default: 1920)
- **Height**: The height of the rendered image (default: 1080)

### Software Environment
- **CondaPackages**: Conda package for Cinema 4D 2025 (default: cinema4d=2025)

## How to Use

### Creating a Valid Scene File

Redshift scene files (.rs) can be created by:
1. Creating a scene in Cinema 4D with Redshift materials and lighting
2. Exporting the scene as a Redshift scene file (.rs)

### Using the Template

1. Use `deadline bundle gui-submit redshift-2025` and select your Redshift scene file as a job parameter
3. Adjust render resolution and output directory as needed
4. Submit the job to a queue with an associated Windows GPU fleet with access to a cinema4d=2025 conda package and Redshift licensing
4a. A Deadline Cloud Windows GPU service-managed fleet will work with no further configuration necessary

## Command Line Interface

The template uses redshiftCmdLine.exe with these parameters:
- `<scene_file>`: Input Redshift scene file (.rs)
- `-ores <width>x<height>`: Set render resolution
- `-oip <output_directory>`: Output directory path 

## Executable Path

The template uses the Redshift command line executable at:
```
%CONDA_PREFIX%\cinema4d\RedshiftData\bin\redshiftCmdLine.exe
```

This path is automatically resolved when the Cinema 4D conda package is installed.

## Sample Scene File

The included `SimpleCubec4d.rs` file is a sample Redshift scene created by the Deadline Cloud team for testing.

## Job Submission Example

```bash
# Submit with default parameters
deadline bundle submit .

# Submit with custom parameters
deadline bundle submit .  -p Width=1280 -p Height=720 -p SceneFile=MyScene.rs

```