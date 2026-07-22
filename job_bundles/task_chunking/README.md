# Task Chunking Job Bundle Samples

These samples demonstrate the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension for Open Job Description, which improves resource utilization by grouping multiple frames or tasks into chunks instead of processing them individually.

## Why use task chunking?

Render jobs often spend substantial time loading applications and scene files before rendering each frame. Chunking amortizes this overhead by processing multiple frames or tasks per chunk, reducing total job runtime.

## Sample index

This table covers every immediate sample directory in `task_chunking/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Basic contiguous chunks](basic_contiguous_chunks/) | `CHUNK[INT]` with `rangeConstraint: CONTIGUOUS` and start/end parsing | Your command accepts consecutive frame ranges |
| [Basic non-contiguous chunks](basic_non_contiguous_chunks/) | `CHUNK[INT]` with arbitrary sparse frame sets | Your command accepts lists such as `1-3,5,7-20:2` |
| [Blender contiguous chunks](blender_render_with_contiguous_chunks/) | Applying contiguous task chunks to a frame render | Blender should load once for multiple consecutive frames |
| [Blender non-contiguous chunks](blender_render_with_non_contiguous_chunks/) | Applying scheduler-selected non-contiguous chunks to a frame render | Blender can render arbitrary frame lists per task |

The Blender variants add the `TASK_CHUNKING` extension and a `ChunkSize` parameter to the base
[Blender render](../blender_render/) sample. They change the frame task parameter from `INT` to
`CHUNK[INT]` and set a target runtime so the scheduler can adjust chunk size.

## Template structure

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
            targetRuntimeSeconds: 600     # Optional target used to adjust chunk size
            rangeConstraint: CONTIGUOUS   # or NONCONTIGUOUS
```

## Range constraints

| Constraint | `{{Task.Param.Frame}}` expands to | Use when |
|---|---|---|
| `CONTIGUOUS` | `"1-10"`, `"11-20"` | The application supports start/end frame arguments |
| `NONCONTIGUOUS` | `"1-3,5,7-10"` | The application supports arbitrary frame lists |

## References

* [RFC 0001: Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md)
* [Open Job Description specification](https://github.com/OpenJobDescription/openjd-specifications)
