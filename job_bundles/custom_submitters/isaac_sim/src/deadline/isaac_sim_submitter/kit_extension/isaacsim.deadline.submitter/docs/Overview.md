# Overview

Work with AWS Deadline Cloud jobs from Isaac Sim. **Tools > Deadline Cloud > Open Deadline Cloud** opens the AWS Deadline Cloud for Isaac Sim app (`deadline-physical-ai gui`), connected to this Isaac Sim; choosing it again brings the window to the front. The app closes when Isaac Sim quits.

- **Job outputs.** Pick a farm, queue and completed job, tick outputs and choose **Download selected**: only those are downloaded, with progress. **Load in Isaac Sim** also sends a trajectory or USD to the open stage.
  - Trajectories (`.npz`) play under PhysX in the open stage, driving joint targets of the robot at `robotPrim`. **Play** resets the robot to the recorded start; **Stop** ends it.
  - USD files are added as references under `/World/DeadlineCloud`.
  - Videos open in the OS default player. Datasets and checkpoints become the next job's inputs.
- **Submit.** Lists your job bundles and opens the standard `deadline bundle gui-submit` dialog, prefilled with the open (saved) stage, the last job you loaded, and loaded datasets or checkpoint.

The app also runs without Isaac Sim; then it only downloads trajectories and USD files.

The extension imports neither the app nor the Deadline Cloud client, and makes no AWS calls. It starts the app as a child process and talks to it over the app's stdin and stdout only (no sockets), loading a file only when it is inside the app's download folder and has the right extension.

## Requirements

- Isaac Sim 5.1.0 through 6.2 on Windows or Linux.
- The `deadline-cloud-for-isaac-sim[gui]` pip package, which ships the app, this extension and both CLIs. Install it into Isaac Sim's pip environment (or any environment), then run `deadline-physical-ai isaac-sim install-extension --enable`.

## Trajectory files

A trajectory (NumPy `savez`, no pickled objects; `*.trajectory.npz` recommended) holds:

| Array | Shape | Meaning |
|---|---|---|
| `joint_positions` | `(T, J)` | Radians (revolute) or meters (prismatic), one row per frame |
| `joint_names` | `(J,)` | Joint prim names under `robotPrim` |
| `hz` | scalar | Frames per second |
| `object_T_reference` | `(T, 4, 4)`, optional | Object pose in the reference prim's frame, meters |
| `robot_T_reference` | `(T, 4, 4)`, optional | Robot root pose in the reference prim's frame, meters |
| `success` | scalar bool, optional | Recorded outcome |
| `label` | scalar string, optional | Display name |


Any `.npz` output is listed as a trajectory, because listing sees only file names; the
arrays are checked when you load one, and a file that isn't a trajectory says which arrays
it lacks. Name trajectories `*.trajectory.npz` so they are easy to pick out. Older
evaluator output with `roll_*` arrays is read too: `roll_q<N>`, `roll_joint_names`,
`roll_hz`, `roll_cube_T_base` (object pose), `roll_robot_T_base` and `roll_success`.

## Settings

All under `/persistent/exts/isaacsim.deadline.submitter/`:

| Setting | Default | Purpose |
|---|---|---|
| `physicalAiExecutable` | empty | Path to `deadline-physical-ai`, when not found automatically |
| `robotPrim` | `/World/Robot` | Robot whose joints a trajectory drives |
| `objectPrim` | empty | Object placed at a trajectory's recorded start; empty skips placement |
| `referencePrim` | empty | Prim whose frame the recorded poses are in; empty skips placement |

The app keeps its own settings (bundle folders, download folder) in its settings file.

See the repository README for job bundle authoring, install steps and troubleshooting: https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles/custom_submitters/isaac_sim
