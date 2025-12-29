# 3ds Max V-Ray Denoiser Example

This job bundle demonstrates rendering 3ds Max scenes with V-Ray, including automatic VRIMG to EXR conversion with denoising preservation and intelligent frame chunking.

## Features

- **Smart Frame Chunking**: Automatically handles both contiguous ranges (e.g., `1-100`) and non-contiguous ranges (e.g., `1-5,10,15-20`)
- **VRIMG to EXR Conversion**: Converts V-Ray's native VRIMG format to industry-standard EXR while preserving denoising data
- **Automatic Cleanup**: Removes temporary VRIMG files after successful conversion
- **Error Handling**: Validates output directories and checks for required V-Ray tools
- **Flexible Output**: Supports custom output directories and frame ranges

## Requirements

- **AWS Deadline Cloud CLI** with GUI mode installed on the artists' machines
- **3ds Max 2025** installed on Windows Worker hosts
- **V-Ray for 3ds Max 2025** (tested with V-Ray 7.0) installed on Windows Worker hosts
- You can use 3ds Max and V-Ray (with plugins) host configuration script available [here](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/host_configuration_scripts/3dsmax) on Windows SMF to install them on the Worker

## Parameters

- **Scene File**: 3ds Max scene file (.max) to render
- **Frames**: Frame range specification (supports both `1-100` and `1,5,10-20` formats)
- **Output Directory**: Directory where final EXR files will be saved
- **Frames Per Task**: Number of frames to render per task (automatically adjusted for non-contiguous ranges to 1)

## Frame Chunking Behavior

The template intelligently handles different frame range formats:

- **Contiguous ranges** (e.g., `1-100`): Uses the specified Frames Per Task for efficient chunking
- **Non-contiguous ranges** (e.g., `1-5,10,15-20`): Automatically renders one frame per task regardless of Frames Per Task setting

## Output Format

The job renders to V-Ray's native VRIMG format in a temporary directory, then converts to EXR format in the specified output directory. VRIMG files conserve all denoising elements including noise passes, beauty passes, and denoising data. This workflow preserves:

- All denoising elements and passes
- Multi-channel data
- High dynamic range
- Complete V-Ray render information

## Usage

### Scene Tweaks

**Max > Render Setup > V-Ray > Enable built-in frame buffer > Save raw image output:**
- Give it a local location on the Worker: `C:\Temp\<output>.vrimg` 
- You can use any name instead of the `<output>` placeholder

**Render Elements Configuration:**
- Make sure you have all the render elements you need under render elements tab and the Denoiser too
- Select each render element including the Denoiser and remove the absolute output path

### Submitting the Job

**Setup:**
- Download the template to a directory and open a terminal
- Run `deadline bundle gui-submit .`
- You'll need Deadline Cloud CLI and GUI components installed for this
- If you run into issues like modules not found or command not found, install Python 3.8+ and follow here: https://github.com/aws-deadline/deadline-cloud?tab=readme-ov-file#getting-started

**Submission Steps:**
1. **Fill in job details** - You will see a GUI submission window
2. **Configure scene parameters:**
   - Fill in the scene file location
   - Set start and end frame
   - Specify the output directory
3. **Select job attachments:**
   - Select all the assets in the job attachments which scene needs to render
   - Include tyFlow cache files if applicable
4. **Submit** the job

The job will handle the rest automatically, including format conversion and cleanup.