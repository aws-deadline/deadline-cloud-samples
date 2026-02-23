# KeyShot Standalone with Non-Contiguous Chunks

This is a Windows KeyShot job bundle that renders scenes using the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md) extension for efficient parallel rendering.

## Task Chunking

This template uses `rangeConstraint: NONCONTIGUOUS` to support arbitrary frame sets:

```yaml
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
        defaultTaskCount: "{{Param.ChunkSize}}"
        targetRuntimeSeconds: "{{Param.TargetRuntime}}"
        rangeConstraint: NONCONTIGUOUS
```

Each chunk expands to an arbitrary frame set like `"1-3,5,7-10:2"`. The Python script parses this and renders each frame using `lux.setAnimationFrame()`.

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| KeyShotFile | KeyShot scene file (.bip) | - |
| Frames | Frame range (e.g., `1-3,8,11-100:2`) | `1-3,8,11-100:2` |
| ChunkSize | Number of frames per chunk | `5` |
| TargetRuntime | Target seconds per chunk (0 to disable) | `180` |
| OutputName | Output file name prefix | `KeyShotOutput` |
| OutputDirectoryPath | Render output directory | - |
| OutputFormat | Output format (PNG, JPEG, EXR, etc.) | `PNG` |

## Output

Output file paths are constructed as:
```
<OutputDirectoryPath>/<OutputName>.<Frame#>.<OutputFormatExtension>
```

All other render settings are taken from the scene file.

## Input Files

This job bundle expects **one** of the following:

1. **Job Attachments**: Specify an input directory containing all referenced files.
  With KeyShot the easiest way to get the input directory is to save
  the entire scene and all external files out as a KeyShot package(ksp).
  Saving a scene to a ksp bundles all of the external files referenced
  into a single directory and changes the paths to be relative to the new
  saved scene. You can then open the ksp up and submit the entire unpacked
  directory as the input directory and use the modified scene within as the
  input KeyShot file.

2. **Network Storage**: All referenced files available via network storage or other method accessible to workers.
