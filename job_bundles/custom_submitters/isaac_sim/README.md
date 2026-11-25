# AWS Deadline Cloud for Isaac Sim (preview)

> **Preview: we want your feedback**
>
> This submitter is an early preview published as a sample so you can try it and tell us what
> works and what doesn't. It is not ready for production use, it is not published as a package,
> and its features, interfaces and setup may change. Share feedback, bugs and feature requests in
> a [GitHub issue](https://github.com/aws-deadline/deadline-cloud-samples/issues) whose title
> starts with `[Isaac Sim submitter]`.

An app and an NVIDIA Isaac Sim extension for working with
[AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) jobs:

- **Job outputs**: pick a finished job (succeeded by default; failed or canceled on request) and download the outputs you choose: robot
  trajectories, USD files, videos, datasets and checkpoints. From Isaac Sim, trajectories
  replay under PhysX in the open stage and USD files are added to it.
- **Submit**: submit your own
  [Open Job Description](https://github.com/OpenJobDescription/openjd-specifications) job
  bundles through the standard Deadline Cloud submit dialog, prefilled from what you
  downloaded and, from Isaac Sim, the open stage.

The app (`deadline-physical-ai gui`) runs on its own on Windows, Linux and macOS, with no
Isaac Sim. The Isaac Sim extension, `isaacsim.deadline.submitter`, adds
**Tools > Deadline Cloud > Open Deadline Cloud**, which opens the same app connected to Isaac
Sim. The pip package `deadline-cloud-for-isaac-sim` contains both, and the
`deadline-physical-ai` CLI. This sample includes one example job
bundle but not scenes, models or NVIDIA software. For other jobs you bring your own bundles (see
[Authoring job bundles for the submitter](#authoring-job-bundles-for-the-submitter)).

## Requirements

- Python 3.10 or later, on Windows, Linux or macOS.
- Deadline Cloud credentials: a Deadline Cloud Monitor login, a profile set with
  `deadline config gui`, or an instance role. Jobs must use job attachments for their
  outputs to be listed.
- Linux only: the Qt6 xcb libraries the app and the submit dialog need (Ubuntu:
  `libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxkbcommon-x11-0`).
- For the Isaac Sim actions: Isaac Sim 5.1.0 through 6.2, on Windows or Linux. Isaac Sim
  5.1.0 needs an NVIDIA driver from the 580 series, per Isaac Sim's own requirements.
  Installing into the same environment as a pip-installed Isaac Sim is the simplest setup.

## Install

The package is not published to PyPI. Install it from a checkout of this repository, into
the Python environment you run Isaac Sim from (or any Python 3.10+ environment to use the app
without Isaac Sim):

```bash
git clone https://github.com/aws-deadline/deadline-cloud-samples.git
pip install "./deadline-cloud-samples/job_bundles/custom_submitters/isaac_sim[gui]"
```

Use `pip install -e ".[gui]"` from this folder instead to edit the code in place.

This installs `deadline` (the Deadline Cloud client), `deadline-physical-ai`, the app, and
the extension. The `gui` extra adds PySide6, which the app needs; without it,
`deadline-physical-ai gui` says to install the extra.

### Without Isaac Sim

```bash
deadline-physical-ai gui
```

### With Isaac Sim

Make the extension visible to Isaac Sim, either way:

- **Link it** (recommended; nothing is copied):
  ```bash
  deadline-physical-ai isaac-sim install-extension --enable
  ```
  If the `isaacsim` pip package is installed in the same environment, this links the
  extension into `<isaacsim package>/extsUser/`, which Isaac Sim scans on start. Otherwise it
  links into the per-user Kit folder (`~/Documents/Kit/shared/exts`; on Windows
  `%USERPROFILE%\Documents\Kit\shared\exts`). The link is a symlink on Linux and a
  directory junction on Windows (no administrator rights needed).
  `--enable` turns the extension on in the Isaac Sim GUI app's settings
  (`user.config.json`, backed up first). Run it with Isaac Sim closed. Options:
  - `--isaac-sim-python PATH`: the Python of a pip-installed Isaac Sim in another environment.
  - `--kit-user-folder PATH`: link into this Kit extension folder instead.
  - `--isaac-sim-version 5.1`: needed with `--enable` when no `isaacsim` pip package is found.
  - `--uninstall`: remove the link and the enabled entry. `--json`: one JSON object.

  It refuses to replace an existing folder that is not a link.
- **Or pass the folder** on each start:
  ```bash
  isaacsim isaacsim.exp.full --ext-folder "$(deadline-physical-ai isaac-sim extension-path)" \
    --enable isaacsim.deadline.submitter
  ```
  (`isaac-sim.sh` and `isaac-sim.bat` take the same flags.) Or, in **Window > Extensions**,
  add the printed folder as a search path and enable **AWS Deadline Cloud**.

Then choose **Tools > Deadline Cloud > Open Deadline Cloud**. The app opens, connected to
Isaac Sim. Choosing it again brings the window to the front. The app closes when Isaac Sim
quits.

## Usage

The app has two tabs. The status bar says whether it is connected to Isaac Sim.

### Job outputs

1. Pick a farm and queue by name, above the tabs: every tab uses them. They start at your
   Deadline Cloud defaults; **Set as default** saves the current pair.
2. Pick a job. Finished jobs are listed newest finished first, 50 at a time; the status
   filter next to **Jobs** switches between Succeeded (the default), Failed, Canceled and
   Any finished, and **Load more** fetches the next page. A failed or canceled job lists
   the outputs its finished tasks wrote. The selected job's parameters show below the
   list. Cmd/Ctrl-click a second job to show only the parameters that differ. The outputs table lists the items a job's outputs
   contain, filterable by kind, with the job's eval summary when it has one.
3. Tick items and choose **Download selected**. Only those items are downloaded, with
   progress. Items already downloaded this session are reused. Double-click a downloaded
   row to open it with the OS (videos play in the default player).
4. Connected to Isaac Sim, **Load in Isaac Sim** downloads the ticked trajectory or USD
   (once) and sends it to Isaac Sim:
   - **Trajectories** load into the robot at `robotPrim` and play under PhysX (with more than one
     ticked, the last in the list). **Play** resets the robot to the recorded start and
     plays it again; **Stop** ends it. Pressing Play on the timeline also plays it.
   - **USD** files are added as references under `/World/DeadlineCloud`. A USD item
     downloads the folder that holds it. Its references, payloads and textures come
     with it (a `.usd` file at the top of `OutputDir` is downloaded on its own).
   - **Datasets** and **checkpoints** are kept as inputs for the next job. With them ticked,
     the button reads **Submit pipeline job with dataset** (or checkpoint): it downloads them
     and opens Submit with them prefilled.
   - **HDF5** files and eval summaries are downloaded only. Without Isaac Sim, so are
     trajectories and USD files. The Isaac Sim buttons are hidden.

### Evaluations

Press **Read eval results from queue** for a table of the completed jobs in the queue chosen
above the tabs that wrote an `eval_summary.json` or a LeRobot `eval_info.json` (written by
`lerobot eval`): success rate, 95% confidence interval, episodes, checkpoint, finish
time, every parameter whose value differs between those jobs, and any `metrics`. Only the
summary files are downloaded, and nothing is read until you press the button (it lists
each job's outputs). Click a header to sort. Double-click a job to view its outputs.
**Load more** reads the next 50 jobs, and **Export CSV...** writes every row with all of
its parameters and per-condition success rates.

### Submit

Lists the job bundles in your bundle folders and opens the standard
`deadline bundle gui-submit` dialog for the one you pick, with some parameters prefilled (see
[Prefilled parameters](#prefilled-parameters)). The tab warns when a required dataset or
checkpoint input is empty. It reports the submitted job id, or that the dialog closed without
submitting. Connected to Isaac Sim, it asks Isaac Sim for the open stage's file each time you
pick a bundle or submit.

**Resubmit with changes** (under the job list in Job outputs) opens Submit for a finished
job with its parameter values prefilled, so you only change what differs in the dialog.
Deadline Cloud doesn't record which bundle a job came from. The tab selects the bundle
that defines all of the job's parameters, from your bundle folders and deadline-cloud's
default job bundle folder, or else from deadline-cloud's job history. Every submit dialog
saves a copy of its bundle there, which means jobs submitted from this machine always match. Among
history matches, the tab prefers a template name equal to the job's name, then the most shared
parameter names, then the fewest extra ones. Pick another bundle to submit the
job's values to it instead. Only the parameters that bundle defines are passed.
**Don't reuse its values** goes back to the usual prefill.

To run a sweep (many learning rates, seeds or checkpoints), prefer one job with an OpenJD
task parameter range over many resubmitted jobs: the tasks share one submission, one set of
uploaded inputs and one job's outputs. See
[task parameters](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#341-taskparameterdefinition).

The dialog submits to the farm and queue chosen above the tabs. `gui-submit` has no farm or
queue options and opens on the configured defaults, so for any other pair the app runs it
on a temporary copy of your `deadline config` (through `DEADLINE_CONFIG_FILE_PATH`) with that
farm and queue as its defaults. Your own defaults are never changed, and settings changed in
that dialog's settings window are not kept.

## Settings

The app's settings are one JSON file: `%APPDATA%\deadline-cloud-for-isaac-sim\settings.json`
on Windows, `~/.config/deadline-cloud-for-isaac-sim/settings.json` on Linux and macOS
(`$XDG_CONFIG_HOME` is honored). Edit it with the app closed.

| Setting | Default | Purpose |
|---|---|---|
| `bundleDirs` | `~/DeadlineCloud/JobBundles` | Folders searched for job bundles, separated by `;` (also set in the Submit tab) |
| `downloadDir` | empty: `~/.deadline/physical-ai/job_outputs/<job-id>` | Where loaded items go (`<downloadDir>/<job-id>`) |
| `outputDir` | `~/DeadlineCloud/JobOutputs` | Where Submit creates a new folder for each required output folder parameter that `parameter_values.yaml` doesn't set. See [Prefilled parameters](#prefilled-parameters). |
| `deadlineExecutable` | empty | Path to `deadline`, when it is not found automatically |
| `physicalAiExecutable` | empty | Path to `deadline-physical-ai`, when it is not found automatically |
| `lastLoadedJob` | empty | Last job loaded; prefills previous-job parameters |

The app looks for the CLIs from the settings above, then next to its own Python, then on
`PATH`, then in common install locations.

The extension's settings are under `/persistent/exts/isaacsim.deadline.submitter/`, and
Isaac Sim saves them across sessions:

| Setting | Default | Purpose |
|---|---|---|
| `physicalAiExecutable` | empty | Path to `deadline-physical-ai`, when it is not found automatically |
| `robotPrim` | `/World/Robot` | Robot whose joints a trajectory drives |
| `objectPrim` | empty | Prim placed at a trajectory's recorded object pose; empty skips placement |
| `referencePrim` | empty | Prim whose frame the recorded poses are in; empty skips placement |

The extension looks for `deadline-physical-ai` from its setting, then `PATH`, then next to
the Python running Isaac Sim (`Scripts\` on Windows, `bin/` on Linux), then common install
locations.

## Authoring job bundles for the submitter

A job bundle is a folder with an Open Job Description template (`template.yaml`,
`template.yml` or `template.json`), plus anything the
[Deadline Cloud job bundle format](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle.html)
allows (`parameter_values.yaml`, `asset_references.yaml`, scripts). The submit dialog is the
stock one, so any bundle that `deadline bundle gui-submit` accepts works.

Ready-made bundles live in [`examples/`](examples/); add that folder to Submit's bundle
folders to use them:

| Bundle | What it does |
|---|---|
| [`quest3_hand_ingest`](examples/quest3_hand_ingest/) | Meta Quest 3 head and hand tracking recordings into a LeRobot v3.0 dataset with a tracking-quality report. CPU only. Includes sample sessions for a run without a headset. |

### Where bundles are found

Submit scans each folder in `bundleDirs` (default `~/DeadlineCloud/JobBundles`;
edit the folder field and press **Rescan**, use **Choose bundle folder...**, or set the
setting), plus deadline-cloud's default job bundle folder
(`settings.job_bundle_default_directory` in `deadline config`). A folder is a bundle when
it holds a template with `specificationVersion`. Each listed folder is checked itself and up
to two levels below it, so both of these layouts work:

```text
~/DeadlineCloud/JobBundles/
  my_bundle/template.yaml
  team/another_bundle/template.yaml
```

Folders starting with `.` or `__` are skipped, and folders inside a bundle are not scanned
for more bundles. The list shows the template's `name` and `description`.

### Prefilled parameters

Values are matched to parameters by type and name (case-insensitive). Everything else keeps
the bundle's own defaults and `parameter_values.yaml`.

| Value | Parameter that receives it |
|---|---|
| The open stage's file (a saved stage, connected to Isaac Sim) | `type: PATH`, `objectType: FILE` (the default), `dataFlow: IN` or `INOUT`, and either `userInterface.fileFilters` patterns ending in `.usd`, `.usda`, `.usdc` or `.usdz` (or `*.usd*`), or, with no file filters, a name containing `usd` or `stage` (`StageFile`, `SceneUsd`). A name with only `scene` does not count. |
| The last job loaded in Job outputs | `type: STRING` named `FromJob`, `FromJobId`, `PreviousJob`, `PreviousJobId`, `SourceJobId` or `InputJobId` (`_` characters ignored) |
| A loaded dataset | `type: PATH`, `objectType: DIRECTORY`, `dataFlow: IN`, named for a dataset: the name after the last `_` is, or ends with, `dataset` or `datasets`, optionally followed by `dir`, `path` or `folder` (`Dataset`, `Datasets`, `train_Datasets`, `TrainDatasets`, `DatasetDir`). A name that merely contains the word does not count (`DatasetCacheDir`, `DatasetCount`). With more than one dataset loaded, they are gathered into one folder of hard links beside them (a hidden `.gathered-*` folder in their download folder, so nothing is copied) and only parameters ending in `datasets` receive it. |
| A loaded checkpoint | The same rule with `checkpoint` (`Checkpoint`, `CheckpointDir`, `eval_Checkpoint`; not `CheckpointOutputRoot`) |
| A resubmitted job's parameter values (**Resubmit with changes**) | Every parameter of the same name; these win over the rows above |
| A new, empty output folder at `<outputDir>/<bundle folder>/<date-time>`, created when the dialog opens. With more than one such parameter, each gets a subfolder. | `type: PATH`, `objectType: DIRECTORY`, `dataFlow: OUT` or `INOUT`, with no `default` and no value in the bundle's `parameter_values.yaml`. An empty `default` marks the parameter optional, and Submit leaves it alone. It replaces a resubmitted job's value, so a new job doesn't write into an earlier job's folder or upload its files. Give the parameter a `default` or a `parameter_values.yaml` value to keep your own folder. |

### Outputs that Job outputs recognizes

Job outputs lists only jobs that succeeded, and reads the output manifests that job attachments
wrote for them (nothing is downloaded to list them). Item paths are relative to the job's
`OutputDir` parameter, so declare one:

```yaml
- name: OutputDir
  type: PATH
  objectType: DIRECTORY
  dataFlow: OUT
```

Without `OutputDir`, the outputs must all be under one folder, which is used instead. Then
write outputs that match these rules:

| Kind | Rule |
|---|---|
| Eval summary | A file named `eval_summary.json` (schema below), or `eval_info.json` from `lerobot eval` (its `aggregated` or `overall` block, with `per_group` as conditions). Its success rate is shown with the job and in Evaluations. `eval_summary.json` wins when a job has both. |
| Trajectory | Any `.npz` file, checked when loaded (see the schema below). |
| USD | `.usd`, `.usda`, `.usdc` or `.usdz`. Loading one downloads the whole folder that holds it, so write each USD output into its own folder together with its references, payloads and textures. A `.usd` file written directly into `OutputDir` is downloaded on its own, without them. |
| LeRobot dataset | A folder with `meta/info.json` and at least one `.parquet` file under its `meta/`, `data/` or `videos/`. The folder is one item. |
| Checkpoint | A folder holding a file named `checkpoint.json` (any content, a JSON object recommended). The folder is one item. |
| HDF5 | `.hdf5` or `.h5`. |
| Video | `.mp4` (H.264 plays everywhere). |

Files inside a dataset's or checkpoint's folder belong to that item. Other files are
ignored. A checkpoint written directly into `OutputDir` claims only its own files and still
leaves the job's other outputs listed on their own.

### Eval summary schema

`eval_summary.json` is a JSON object. Every field is optional. Unknown fields are ignored.

| Field | Meaning |
|---|---|
| `episodes` | Number of evaluated episodes (integer) |
| `successes` | Number of successful episodes (integer) |
| `success_rate` | `successes / episodes`, 0 to 1. Computed when missing. |
| `ci95` | `[low, high]`, a 95% confidence interval for the rate (0 to 1). When missing, the Wilson score interval is computed from `successes` and `episodes`. |
| `checkpoint` | Which checkpoint was evaluated, as text (`checkpoint-20000`) |
| `by_condition` | `{"<condition>": {"episodes": n, "successes": k}}`: results per test condition (start pose set, lighting, object), exported as `condition.<name>.success_rate` |
| `metrics` | `{"<name>": number}`: other numbers to compare, shown as columns |

```json
{"episodes": 50, "successes": 41, "checkpoint": "checkpoint-20000",
 "by_condition": {"seen_poses": {"episodes": 25, "successes": 24}},
 "metrics": {"mean_episode_len": 204.2}}
```

### Trajectory file schema

A trajectory is a NumPy archive (`numpy.savez`, no pickled objects; `*.trajectory.npz` is
the recommended name) with:

| Array | Shape | Meaning |
|---|---|---|
| `joint_positions` | `(T, J)` float | One row per frame: radians for revolute joints, meters for prismatic joints |
| `joint_names` | `(J,)` string | Matched to joint prim names under `robotPrim` |
| `hz` | scalar | Frames per second |
| `object_T_reference` | `(T, 4, 4)` float, optional | The tracked object's pose in the reference prim's frame, meters, column-vector convention (translation in the last column) |
| `robot_T_reference` | `(T, 4, 4)` float, optional | The robot root's pose in the reference prim's frame, same convention |
| `success` | scalar bool, optional | The episode's recorded outcome, shown after loading |
| `label` | scalar string, optional | Shown instead of the file name |


Any `.npz` output is listed as a trajectory, because listing sees only file names; the
arrays are checked when you load one, and a file that isn't a trajectory says which arrays
it lacks. Name trajectories `*.trajectory.npz` so they are easy to pick out. Older
evaluator output with `roll_*` arrays is read too: `roll_q<N>`, `roll_joint_names`,
`roll_hz`, `roll_cube_T_base` (object pose), `roll_robot_T_base` and `roll_success`.

Replay sets each matched joint's drive target every frame (degrees for revolute joints,
stage units for prismatic ones) and lets PhysX move the scene. Only joints that already
have a position drive with nonzero stiffness are replayed: a joint with no drive ignores
targets. Your stage is left as is: the extension doesn't write a drive or a joint state schema into it.
The load message counts the skipped joints: those missing from the stage or without a drive,
plus any without a `state:*:physics:position` attribute to hold the start pose. On load, the joints are set to frame 0, `objectPrim` is placed at the first
`object_T_reference` relative to `referencePrim`, and `robotPrim` is placed at the first
`robot_T_reference` unless `referencePrim` is inside the robot.

```python
import numpy as np

hz = 30.0
t = np.arange(120) / hz
np.savez(
    "ep_000.trajectory.npz",
    joint_positions=np.stack([0.5 * np.sin(t), 0.02 * t], axis=1),
    joint_names=np.array(["shoulder_joint", "lift_joint"]),
    hz=np.float64(hz),
    success=np.bool_(True),
    label=np.array("Example episode"),
)
```

### Example bundle

A minimal bundle that uses the prefills and writes outputs Job outputs recognizes. It
needs `python` with NumPy on the worker's `PATH`. Save it as
`~/DeadlineCloud/JobBundles/trajectory_example/template.yaml`:

```yaml
specificationVersion: jobtemplate-2023-09
name: Trajectory example
description: Copies the scene and writes a one-joint sine trajectory.
parameterDefinitions:
- name: SceneFile
  type: PATH
  objectType: FILE
  dataFlow: IN
  userInterface:
    control: CHOOSE_INPUT_FILE
    label: Scene (USD)
    fileFilters:
    - label: USD files
      patterns: ["*.usd", "*.usda", "*.usdc", "*.usdz"]
- name: FromJobId
  type: STRING
  default: ""
  description: The job this one follows (recorded only).
- name: JointName
  type: STRING
  default: joint1
- name: OutputDir
  type: PATH
  objectType: DIRECTORY
  dataFlow: OUT
  userInterface:
    control: CHOOSE_DIRECTORY
    label: Output folder
steps:
- name: Write
  script:
    actions:
      onRun:
        command: python
        args: ["{{Task.File.Run}}"]
    embeddedFiles:
    - name: Run
      type: TEXT
      data: |
        import json, os, shutil
        import numpy as np

        out = r"{{Param.OutputDir}}"
        os.makedirs(os.path.join(out, "scene"), exist_ok=True)
        shutil.copy(r"{{Param.SceneFile}}", os.path.join(out, "scene"))
        os.makedirs(os.path.join(out, "rollouts"), exist_ok=True)
        hz = 30.0
        t = np.arange(120) / hz
        np.savez(
            os.path.join(out, "rollouts", "ep_000.trajectory.npz"),
            joint_positions=(0.5 * np.sin(np.pi * t))[:, None],
            joint_names=np.array(["{{Param.JointName}}"]),
            hz=np.float64(hz),
            success=np.bool_(True),
        )
        with open(os.path.join(out, "eval_summary.json"), "w") as fh:
            json.dump({"episodes": 1, "successes": 1, "success_rate": 1.0, "from": "{{Param.FromJobId}}"}, fh)
```

Connected to Isaac Sim with a saved stage open, `SceneFile` is prefilled with it, and
`FromJobId` with the last job you loaded. When the job finishes, Job outputs lists the
copied USD, the trajectory and the eval summary. Set `JointName` to a joint under
`robotPrim` to replay it.

## How it works

- The app never imports `boto3` or `deadline`. The app makes AWS calls only from a child process:
  the `deadline` CLI (default farm and queue, farm, queue and job lists, the submit dialog)
  or `deadline-physical-ai` (`jobs list --status`: finished jobs filtered by status and
  sorted by the service, page by page; `jobs params`: jobs' names and parameters; `jobs evals`: each completed job's parameters and eval summary; `outputs list|fetch`: list a job's outputs without downloading
  them, and download chosen items into a chosen folder, which the stock CLI cannot do yet).
  The window never waits on the network: children are polled from a 30 Hz timer.
- The extension imports neither the app nor PySide6, and doesn't make AWS calls. It starts the
  app as its child (`deadline-physical-ai gui --bridge`) with Kit's Python and Qt variables
  (`PYTHONHOME`, `PYTHONPATH`, `QT_*`, `LD_LIBRARY_PATH`) removed from its environment, and
  answers the app's requests on Kit's main thread. The app's children and the OS video
  player get the same cleaned environment. Commands are argument lists, never a shell.
- **The bridge** is the app's stdin and stdout: one line of UTF-8 JSON per message, at most
  64 KB, each with `"v": 1` and a `type`. Isaac Sim sends `hello` (its version, the
  extension's version, and what it can do: `replay`, `add_usd`, `stage_path`) and `focus`;
  the app sends `hello_ack` (its version and download folder), `get_stage`, `load`
  (`trajectory` or `usd`, a path) and `replay_control` (`play`, `stop`). Each request gets
  one `result` with `ok` and a message. Unknown types are ignored; malformed or oversize
  lines are logged and skipped. When Isaac Sim quits or the extension shuts down, the app's
  stdin closes and the app exits; the extension kills it if it has not exited within
  2 seconds. If the app exits, the next menu choice starts a new one.
- Downloads skip files already present with the same content hash, run in parallel, and
  report progress to the window. That record is written as files finish, so a download that
  is interrupted or times out resumes where it stopped instead of starting over.
- The extension's version comes from its `extension.toml`, which a wheel build stamps with
  the package version (Kit's semantic-version form; the source keeps the placeholder
  `0.0.0`, and then the installed package version is used). Jobs are reported to Deadline
  Cloud with `submitter_package_name=deadline-cloud-for-isaac-sim` and, from Isaac Sim, the
  Isaac Sim version.

## Troubleshooting

- **"No AWS credentials" or "credentials have expired".** Sign in again with Deadline Cloud
  Monitor, or fix the profile in `deadline config gui`, then **Refresh**.
- **The wrong account, or no farms.** The `deadline` CLI uses the profile in its own
  configuration (`deadline config get defaults.aws_profile_name`) and ignores `AWS_PROFILE`.
  Change it with `deadline config gui`.
- **"Timed out waiting for the Deadline Cloud CLI".** CLI calls stop after 90 seconds.
  The common cause is a CLI waiting for a sign-in. Downloads may run for up to 1 hour. The
  submit dialog has no limit.
- **"deadline CLI not found" or "deadline-physical-ai not found".** Set `deadlineExecutable`
  or `physicalAiExecutable` (the app's settings file, or the extension's setting) to the full
  path.
- **Open Deadline Cloud does nothing.** The Isaac Sim console has the reason, prefixed
  `[isaacsim.deadline.submitter]`. Common causes are `deadline-physical-ai` not found or the app
  exiting at start. If the app exits because the `gui` extra is missing, the console shows its message.
- **The extension is not listed.** Run `deadline-physical-ai isaac-sim install-extension`
  again and read where it linked. If your Documents folder is redirected, pass
  `--kit-user-folder`, or use `--ext-folder`.
- **The app or the submit dialog never appears (Linux).** Install the Qt6 xcb libraries
  listed in [Requirements](#requirements).
- **Where did my download go?** The status line shows the folder. By default it is
  `~/.deadline/physical-ai/job_outputs/<job-id>`. See `downloadDir`.
- **A job's outputs are not listed.** Only succeeded jobs are shown, outputs must go through
  job attachments, and file names must match the rules in
  [Outputs that Job outputs recognizes](#outputs-that-job-outputs-recognizes).
- **Replay says no joints were found.** Set `robotPrim` to the robot's root prim, and use
  joint prim names in `joint_names`.
- **Replay says joints have no position drive.** Those joints don't have a `PhysicsDriveAPI`
  with stiffness, so drive targets do nothing. Add a position drive to them in the stage
  (an articulation authored for PhysX has one). Replay skips the rest.
- **Isaac Sim refuses a load as "not inside the download folder".** Isaac Sim loads only
  files under the app's download folder. Load the item from Job outputs rather than moving
  it elsewhere.

## Security

- The app, the extension and the CLI don't listen on a network or open sockets or
  ports. The bridge is the stdin and stdout pipes between the extension and the app it
  started; no other process can write to them, and no files are used for messages. The app
  runs only the local `deadline` and `deadline-physical-ai` CLIs; AWS calls are made by those
  CLIs with your Deadline Cloud credentials, which this project never reads, stores or logs.
- Isaac Sim acts on a `load` only for an absolute path to an existing file whose name fits
  the kind (`.npz`, or `.usd`, `.usda`, `.usdc`, `.usdz`) and which, with
  symlinks and `..` resolved, is inside the download folder the app announced. Trajectories
  are read with `allow_pickle=False`.
- `deadline-physical-ai` is read-only on AWS (`GetQueue`, `GetJob`, S3 `ListObjectsV2` and
  `GetObject`).
- Downloads go only to the chosen folder: a manifest path that is absolute, has a drive
  letter, or would leave the folder through `..` is refused before anything is downloaded.
- Downloaded videos are opened with the OS default application.
- `install-extension` creates one link and edits one settings file (after backing it up). It
  never deletes a folder that is not a link.

To report a security issue, use the AWS [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/).
Do not create a public GitHub issue.

## Development

```bash
pip install hatch
hatch run lint      # ruff, black --check, mypy
hatch run test      # pytest test/unit, no Isaac Sim, GPU, display, network or AWS needed
hatch build         # sdist and wheel; the wheel's extension.toml gets the package version
```

Run these from this folder. The repository's own `python3 scripts/validate_repository.py` does
not run this sample's tests.

Layout:

- `src/deadline/isaac_sim_submitter/app/`: the app. `controllers.py`, `cli_backend.py`,
  `bundles.py` and `settings.py` hold the state and CLI work without Qt; `qt_app.py` is the
  window; `bridge.py` is the app's end of the Isaac Sim bridge.
- `src/deadline/isaac_sim_submitter/kit_extension/isaacsim.deadline.submitter/`: the Kit
  extension (`config/extension.toml`, `docs/`, Python package `isaacsim.deadline.submitter`:
  the menu, the bridge host, replay and USD references). It is installed as package data; its
  folder name keeps it from being importable as a top-level `isaacsim` package.
  `protocol.py` and `procenv.py` are copies of the app's (the extension cannot import the
  app in every Isaac Sim install). A unit test keeps them identical.
- `src/deadline/isaac_sim_submitter/`: locates the extension and installs the link.
- `src/deadline/physical_ai/`: the `deadline-physical-ai` CLI (`gui`, `jobs list|params`, `outputs list|fetch`,
  `isaac-sim extension-path|install-extension`).
- `src/deadline/isaac_sim_adaptor/`: placeholder for a future adaptor.
- `test/unit/`: unit tests. The extension's tests stub Kit modules and use `usd-core` for
  USD; they skip USD tests where `usd-core` has no wheel. The app's Qt tests run offscreen
  and skip where PySide6 cannot import. Bridge tests run real child processes over pipes.
- [docs/MANUAL-TEST-CHECKLIST.md](docs/MANUAL-TEST-CHECKLIST.md): the checks to run, with
  and without Isaac Sim, before a release.

## Future work

- Split `deadline.physical_ai` (job output listing and download) into its own package, and
  have this one depend on it.
- An Open Job Description adaptor for running Isaac Sim on workers
  (`deadline.isaac_sim_adaptor`).

## License

This sample is licensed under the [MIT-0 License](../../../LICENSE), like the rest of this
repository.

### External Dependencies

This project integrates with [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim),
which is distributed by NVIDIA under its own license terms. Isaac Sim is not
bundled with or distributed by this project. Install Isaac Sim separately from
NVIDIA.
