# Task Chunking Job Bundle Samples

These samples demonstrate the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension for Open Job Description, which improves resource utilization by grouping multiple frames or tasks into chunks instead of processing them individually.

## Why Use Task Chunking?

Render jobs often spend significant time loading applications and scene files before rendering each frame. Chunking amortizes this overhead by processing multiple frames or tasks per chunk, reducing total job runtime.

## Samples

### 1. Basic Contiguous Chunks (`basic_contiguous_chunks/`)

A minimal example using `rangeConstraint: CONTIGUOUS`. Each chunk expands to a range like `"1-10"` or `"11-20"`. The script parses and prints the start and end frame numbers.

### 2. Basic Non-Contiguous Chunks (`basic_non_contiguous_chunks/`)

A minimal example using `rangeConstraint: NONCONTIGUOUS`. Chunks can be arbitrary frame sets like `"1-3,5,7-20:2"`. The script prints the frames assigned by the scheduler.

### 3. Blender Render with Contiguous Chunks (`blender_render_with_contiguous_chunks/`)

A real-world example converted from the existing [blender_render](../blender_render/template.yaml) job bundle to render job with contiguous chunks.

### 4. Blender Render with Non-Contiguous Chunks (`blender_render_with_non_contiguous_chunks/`)

A real-world example converted from the existing [blender_render](../blender_render/template.yaml) job bundle to render job with non-contiguous chunks.

Changes from the original:
1. Added `extensions: [TASK_CHUNKING]`
2. Added `ChunkSize` parameter (default: 5)
3. Changed `Frame` from `type: INT` to `type: CHUNK[INT]` with `rangeConstraint: CONTIGUOUS` and `targetRuntimeSeconds: 600`

## Template Structure

```yaml
specificationVersion: 'jobtemplate-2023-09'
extensions:
  - TASK_CHUNKING

steps:
  - name: Render
    parameterSpace:
      taskParameterDefinitions:
        - name: Frame
          type: CHUNK[INT]
          range: "{{Param.Frames}}"
          chunks:
            defaultTaskCount: 10          # Default frames per chunk
            targetRuntimeSeconds: 600     # Optional: allows the scheduler to adjust the task count for chunks to match this runtime
            rangeConstraint: CONTIGUOUS   # or NONCONTIGUOUS
```

## Range Constraints

| Constraint | `{{Task.Param.Frame}}` expands to | Use when |
|------------|-----------------------------------|----------|
| `CONTIGUOUS` | `"1-10"`, `"11-20"` | App supports start/end frame arguments |
| `NONCONTIGUOUS` | `"1-3,5,7-10"` | App supports arbitrary frame lists |

## References

- [RFC 0001: Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md)
- [Open Job Description Specification](https://github.com/OpenJobDescription/openjd-specifications)
