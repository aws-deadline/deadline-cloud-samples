# Maya CLI Render with Contiguous Chunks

This job bundle renders a Maya software renderer scene with the
[Maya CLI `Render` command](https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-EB558BC0-5C2B-439C-9B00-F97BCB9688E4)
using the [Task Chunking](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md)
extension to reduce scheduling overhead by grouping frames into chunks.

## Features

- **Task Chunking**: Uses `CHUNK[INT]` with contiguous frame ranges to reduce scheduling overhead by rendering multiple frames per chunk
- **Adaptive Chunking**: Optional target runtime allows the scheduler to adjust chunk sizes dynamically

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Maya Scene File | Maya scene file (.ma, .mb) to render | `fallinggears.ma` |
| Frames | Frame range (e.g., `1-60`) | `1-60` |
| Chunk Size | Number of frames per chunk | `10` |
| Target Runtime | Target seconds per chunk (0 to use fixed chunk sizes) | `180` |
| Camera Name | Camera to render | `persp` |
| Image Width | Output image width | `960` |
| Image Height | Output image height | `540` |
| Output Directory | Render output directory | `output` |
| Project Path | Maya project directory | `.` |

## Task Chunking

This template uses the `TASK_CHUNKING` extension with `rangeConstraint: CONTIGUOUS`:

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
        rangeConstraint: CONTIGUOUS
```

Each chunk expands to a contiguous range like `"1-10"` or `"11-20"`, which maps directly to Maya's `-s` (start) and `-e` (end) arguments.

Reference: [Maya Common Renderer Flags](https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-0280AB86-8ABE-4F75-B1B9-D5B7DBB7E25A)

## Usage

To run it, you will need a Maya installation available in the PATH in one of the following ways:
* As a conda package when your queue has a conda queue environment set up to
  provide virtual environments for jobs. For more information see the developer guide section
  [Provide applications for your jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html).
* Installed on the worker hosts that run the job. You can customize your Deadline Cloud
  queues, fleets, and this job to fit your own production pipeline.

The core of this job is an embedded template file called `render.sh` that invokes
the Maya CLI `Render` command. The command is a template that substitutes job parameters and the
frame chunk parameter.

The `Render` command is part of an Open Job Description step. It groups frames into contiguous
chunks using the task chunking extension, and each chunk is rendered in a single Maya invocation.
It limits the fleets it will run on by including host requirements for Linux.

The rest of the job template consists of the parameter definitions. This metadata specifies
the names, types, and descriptions of each parameter, along with information on what user
interface controls a GUI should use.
The [Deadline Cloud CLI command `deadline bundle gui-submit`](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/from-a-terminal.html#with-a-submission-window)
uses this metadata to generate its UI.

## The falling gears sample scene

We created this sample Maya scene with a goal for a small scene file that has a touch
of interesting dynamics. The process used Maya with a bit of scripting. You can use the scene
we created for testing, or produce similar scenes with the following steps.

1. We're going to use the Bullet physics plugin, so in Windows -> Settings/Preferences -> Plugin Manager,
   make sure that `bullet.mll` is loaded.
2. Create a ground plane (Create -> Polygon Primitives -> Plane) and then edit the objects Scale X, Y, Z
   to all be 20.
3. Create four gears (Create -> Polygon Primitives -> Gear). Use the Move and Rotate tools to suspend
   them in the air in a way they will fall and collide in an interesting way. NOTE: Don't use the "duplicate"
   feature of Maya, that will turn the Gear primitive into a polygon mesh and make the Maya scene file large.
4. Make a duplicate of each Gear primitive to use for the physics. This will create pGear5 through pGear8.
5. Select pGear5 through pGear8, and with the FX menu set active, choose Bullet -> Active Rigid Body.
6. Open the Attribute Editor, and for each of the active rigid bodies you created, and modify the Collider
   Shape Type from box to hull.
7. Select pPlane1, and choose Bullet -> Passive Rigid Body.
8. Select the bulletSolver1 object, and set Start Time to 0.
9. Now if you play the timeline, you should see the gears fall and collide with the floor and each other.
   Run the following Python code in the Script Editor to bake this animation onto the original Gears.
    ```
    for t in range(60):
        cmds.currentTime(t)
        cmds.refresh()
        for j in range(1, 5):
            src, dst = f"pGear{j + 4}", f"pGear{j}"
            for attr_name in ["translate", "rotate"]:
                at_value = cmds.getAttr(f"{src}.{attr_name}")[0]
                cmds.setKeyframe(dst, at=f"{attr_name}X", v=at_value[0])
                cmds.setKeyframe(dst, at=f"{attr_name}Y", v=at_value[1])
                cmds.setKeyframe(dst, at=f"{attr_name}Z", v=at_value[2])
    ```
10. Delete the duplicates you made for the rigid body simulation, pGear5 through pGear8, along with bulletSolver1.
    You can also delete physics attributes from objects with Python commands like
    `cmds.delete("|pPlane1|bulletRigidBodyShape5")`
11. Choose Windows -> Animation Editors -> Graph Editor. Select the objects pGear1 through pGear4. You should
    see all the physics animation curves. In the Graph Editor, choose Curves -> Key Reducer Filter. This
    will reduce the number of keys, and hence the file size.
