# Blender Render

This job bundle renders Blender scenes using the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension with non-contiguous frame support for flexible parallel rendering.

## Features

- **Non-Contiguous Chunking**: Uses `CHUNK[INT]` with `rangeConstraint: NONCONTIGUOUS` for arbitrary frame sets
- **Adaptive Chunking**: Optional target runtime allows the scheduler to adjust chunk sizes dynamically
- **Flexible Frame Ranges**: Supports ranges, steps, and individual frames (e.g., `1-10,15,20-100:2`)

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Blender Scene File | Blender scene file (.blend) to render | - |
| Frames | Frame range (e.g., `1-10,15,20-100:2`) | `1-10,15,20-100:2` |
| Chunk Size | Number of frames per chunk | `5` |
| Target Runtime | Target seconds per chunk (0 to disable) | `180` |
| Output Directory | Render output directory | `./output` |
| Output File Pattern | Output filename pattern | `output_####` |
| Output File Format | Image format | `JPEG` |

## Task Chunking

This template uses the `TASK_CHUNKING` extension with `rangeConstraint: NONCONTIGUOUS`:

```yaml
extensions:
  - TASK_CHUNKING

steps:
- name: RenderBlender
  parameterSpace:
    taskParameterDefinitions:
    - name: Frame
      type: CHUNK[INT]
      range: "{{Param.Frames}}"
      chunks:
        defaultTaskCount: "{{Param.ChunkSize}}"
        targetRuntimeSeconds: "{{Param.TargetRuntime}}"
        rangeConstraint: NONCONTIGUOUS
```

Each chunk expands to an arbitrary frame set like `"1-3,5,7-10:2"`. A Python script converts this to Blender's `--render-frame` format (e.g., `1,3,5,9..11,15`).

Reference: [Blender Command Line Arguments](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
