# 3ds Max V-Ray Denoiser Example

This job bundle demonstrates rendering 3ds Max scenes with V-Ray, including automatic VRIMG to EXR conversion with denoising preservation, using the Open Job Description task chunking extension to reduce scheduling overhead for multi-frame rendering.

## Task Chunking

This job bundle uses the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension with `rangeConstraint: CONTIGUOUS` to reduce scheduling overhead by grouping frames together into chunks.

```yaml
extensions:
  - TASK_CHUNKING

steps:
- name: Render EXRs
  parameterSpace:
    taskParameterDefinitions:
    - name: Frame
      type: CHUNK[INT]
      range: "{{Param.Frames}}"
      chunks:
        defaultTaskCount: "{{Param.ChunkSize}}"
        targetRuntimeSeconds: "{{Param.TargetRuntime}}"
        rangeConstraint: CONTIGUOUS
```

Each chunk expands to a contiguous range like `"0-4"` or `"5-9"`, which maps directly to `3dsmaxcmd.exe -start:N -end:N`.

## Job summary

This job bundle renders 3ds Max scenes with V-Ray, including automatic VRIMG to EXR conversion with denoising preservation. Task chunking amortizes 3ds Max's startup and scene loading time by rendering multiple frames per invocation.

## Features

- **Task Chunking**: Uses `CHUNK[INT]` with contiguous frame ranges to reduce scheduling overhead by rendering multiple frames per task
- **Adaptive Chunking**: Optional target runtime allows the scheduler to adjust chunk sizes dynamically
- **VRIMG to EXR Conversion**: Converts V-Ray's native VRIMG format to industry-standard EXR while preserving denoising data
- **Automatic Cleanup**: Removes temporary VRIMG files after successful conversion
- **Error Handling**: Validates output directories and checks for required V-Ray tools

## Requirements

- **AWS Deadline Cloud CLI** with GUI mode installed on the artists' machines
- **3ds Max 2025** installed on Windows Worker hosts
- **V-Ray for 3ds Max 2025** (tested with V-Ray 7.0) installed on Windows Worker hosts
- You can use 3ds Max and V-Ray (with plugins) host configuration script available [here](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/host_configuration_scripts/3dsmax) on Windows SMF to install them on the Worker

## Parameters

- **Scene File**: 3ds Max scene file (.max) to render
- **Frames**: Frame range specification (supports both `1-100` and `1,5,10-20` formats)
- **Output Directory**: Directory where final EXR files will be saved
- **Chunk Size**: Number of frames to render per chunk (default: 5)
- **Target Runtime (Seconds)**: Target runtime per chunk (default: 180, set to 0 to use fixed chunk sizes)

## Output Format

The job renders to V-Ray's native VRIMG format in a temporary directory, then converts to EXR format in the specified output directory. This workflow preserves:

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
   - Set the frame range
   - Specify the output directory
3. **Select job attachments:**
   - Select all the assets in the job attachments which scene needs to render
   - Include tyFlow cache files if applicable
4. **Submit** the job

The job will handle the rest automatically, including format conversion and cleanup.
