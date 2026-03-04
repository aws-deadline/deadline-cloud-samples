# After Effects Render with Contiguous Chunks

This job bundle renders After Effects compositions using aerender with the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension.

## Task Chunking

This job bundle uses the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension with `rangeConstraint: CONTIGUOUS` for efficient rendering. Chunking reduces scheduling overhead by grouping frames together, and the single `Frames` parameter accepts ranges (`1-50`), individual frames (`5,7,32`), stepped ranges (`1-100:2`), or combinations (`1-10,15,20-30:2`).

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Project file | After Effects project file (.aep, .aepx) | - |
| Comp name | Composition to render | - |
| Input directory | Directory containing input files | - |
| Output directory | Render output directory | - |
| Frames | Frame range (e.g., `0-100`) | `0-50` |
| Chunk Size | Number of frames per chunk | `10` |
| Target Runtime | Target seconds per chunk (0 to disable) | `300` |

## Task Chunking

This template uses the `TASK_CHUNKING` extension:

```yaml
extensions:
  - TASK_CHUNKING

steps:
- name: RenderComp
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

Each chunk expands to a contiguous range like `"0-9"` or `"10-19"`, which maps directly to aerender's `-s` (start) and `-e` (end) arguments.

Reference: [After Effects Automated Rendering](https://helpx.adobe.com/after-effects/using/automated-rendering-network-rendering.html)

## Usage

This job bundle expects a user to specify an input directory that contains all the file references required to render. Generally, the project file should be within this directory to ensure relative paths are preserved.
