# Nuke Render Job Bundle

## Job summary

This job bundle renders Nuke scripts using Nuke's headless rendering mode with the `nuke -x` command.

To run it, you will need a Nuke installation available in the PATH in one of the following ways:
* As a conda package when your queue has a conda queue environment set up to
  provide virtual environments for jobs. For more information see the developer guide section
  [Provide applications for your jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html).
* Installed on the worker hosts that run the job. You can customize your Deadline Cloud
  queues, fleets, and this job to fit your own production pipeline.

The core of this job is an embedded bash script that runs the `nuke` command with these flags:
* `-F {frame}` - Renders a specific frame number
* `--sro` - Skip render output logging
* `-V 2` - Set verbosity level to 2
* `-x` - Execute the script without opening the GUI

The job creates one task per frame using Open Job Description's parameter space feature,
where the Frames parameter (e.g. "1-10") gets expanded into individual frame tasks.
The job is restricted to Linux workers through host requirements.

## What this sample does

This job bundle takes a Nuke script file and renders it frame by frame using Nuke's command-line interface. The sample includes:

- **MotionBlur3D Scene**: A pre-configured Nuke script that demonstrates 3D motion blur effects
- **Frame-based rendering**: Supports single frames or frame ranges
- **Flexible output**: Configurable output directory and project paths
- **Environment support**: Works with both Conda and Rez package management systems

## Requirements

- Nuke installed and available in your queue environment
- A queue environment configured with Nuke packages (see [queue environments](../../queue_environments/README.md))
- The `deadline` CLI configured for your farm

## Sample scene

The included `scene/motionblur3d_10.nk` file is based on Foundry's MotionBlur3D example, configured with:
- Relative file paths for portability
- Pre-configured Write node for output
- 3D geometry with motion blur effects

## Job submission

### CLI submission

Submit the job with default parameters:

```bash
deadline bundle submit job_bundles/nuke_render
```

Submit with custom parameters:

```bash
deadline bundle submit job_bundles/nuke_render \
  --name "My Nuke Render" \
  -p Frames="1-10" \
  -p NukeScript="/path/to/my/script.nk" \
  -p OutputDir="/path/to/output"
```

### GUI submission

Launch the GUI submitter to interactively configure parameters:

```bash
deadline bundle gui-submit job_bundles/nuke_render
```

## Parameters

### Render Parameters

- **Nuke Script File**: Path to the .nk script file to render
- **Frames**: Frame range (e.g., "1-10", "1,5,10", or "1")
- **Project Directory**: Working directory containing the script and assets
- **Output Directory**: Where rendered frames will be saved

### Software Environment

- **Conda Packages**: Conda packages to install (default: "nuke nuke-openjd")
- **Rez Packages**: Rez packages to install if using Rez environments

## Expected output

When rendered, the sample scene produces:
- Rendered frames in the specified output directory
- 3D composited images with motion blur effects
- Output files named according to the Write node configuration in the Nuke script

## Customizing the job

To use this template with your own Nuke scripts:

1. Replace the sample scene file or point to your own .nk file
2. Adjust the frame range as needed
3. Configure output paths and directories
4. Add any additional assets via job attachments
