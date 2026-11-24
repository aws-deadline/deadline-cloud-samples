# Quest 3 hand tracking to LeRobot

A job bundle that turns Meta Quest 3 head and hand tracking recordings into a
[LeRobot](https://github.com/huggingface/lerobot) v3.0 dataset, with an HTML report of tracking
quality. It runs on CPU workers, one task per recorded session and then one task for the dataset,
so a large capture day imports in parallel.

| Step | What it does |
|---|---|
| Import Sessions | Reads one `session.jsonl` and puts the poses in the task frame. Then it resamples them to a fixed frame rate (bridging short tracking gaps) and measures coverage, confidence and the longest gap. |
| Build Dataset | Writes `dataset/` (one episode per session) and `qc_report/index.html`. Sessions with poor tracking are kept and flagged, not dropped. |

## Try it without a headset

```sh
python3 scripts/make_sample_sessions.py --out "$HOME/quest3-sessions"
deadline bundle gui-submit . -p SessionsDir="$HOME/quest3-sessions" -p NumSessions=4
```

Or pick this folder in the Deadline Cloud for Isaac Sim app's **Submit** tab. The sample
sessions record a pick-and-place: `anchored` and `webxr` are calibrated to the table (the pinch lands
on the cube at x 0.05, y 0.10, z 0.023 m), `lost` loses the right hand for 3 s and is flagged, and
`unanchored` has no calibration and is flagged `world_frame_unanchored`.

## Recording sessions

Each session is a folder holding `session.jsonl`, the `quest-capture` format documented at the top
of [`scripts/quest_capture.py`](scripts/quest_capture.py): a header line, then one line per tracking
frame with the head pose and each hand's joint poses in the XR reference space. Any recorder that
can read OpenXR (`XR_EXT_hand_tracking`, 26 joints) or WebXR Hand Input (25 joints) can write it,
such as a WebXR page served to the Quest browser, or a native OpenXR app.

To express poses relative to your table, record where the table is in either of two ways:

- touch three points with the index fingertip (origin, a point along +X, a point toward +Y) and log
  them as `calib_origin`, `calib_x` and `calib_y` events, or
- put a spatial anchor's pose in the header as `world.T_xr_world`.

Without either, the dataset uses the headset's floor-level space turned Z-up, which is fine for
learning hand motion but not for anything that needs object positions.

## Dataset

`dataset/` follows LeRobot's v3.0 layout (`meta/info.json`, `meta/stats.json`,
`meta/tasks.parquet`, `meta/episodes/`, `data/`) and loads with
`LeRobotDataset(repo_id, root=".../dataset")`. Each frame has:

| Column | Shape | Meaning |
|---|---|---|
| `observation.head.pose` | 7 | Head position (m) and orientation (quaternion x y z w) |
| `observation.hand.<side>.joints` | 75 | 25 joint positions, wrist first, in OpenXR order without the palm |
| `observation.hand.<side>.wrist_pose` | 7 | Wrist position and orientation |
| `observation.hand.<side>.pinch_aperture` | 1 | Thumb tip to index tip distance (m) |
| `observation.hand.<side>.confidence` | 1 | The recorder's tracking confidence, 0 to 1 |
| `observation.*.valid` | 1 | Tracked in this frame, or inside a bridged gap |

`<side>` is `right` or `left`. All poses are in the task frame: +X right, +Y away from you, +Z up,
in meters. Untracked frames hold zeros, so mask them with the `valid` columns. Each episode's row in
`meta/episodes/` also contains the session name, its warnings and its tracked fractions.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `SessionsDir` | | Folder of session folders. An optional `sessions.txt` sets the episode order. |
| `NumSessions` | 4 | How many sessions to import, from the start of that order |
| `Fps` | 30 | Dataset frame rate |
| `MaxGapSeconds` | 0.1 | Longest tracking gap that is bridged |
| `TaskInstruction` | | Task text for every episode; empty uses each session's header |
| `MinTrackedFraction` | 0.7 | The report warns below this tracked fraction |

## Software

The job runs in the Isaac Lab conda package from Deadline Cloud's managed `deadline-cloud-v2`
channel (`CondaPackages=isaaclab=3.0`, `CondaChannels=deadline-cloud-v2`), the same environment as
the Isaac Lab steps that train on the dataset. `isaacsim=6.2` works too. Linux workers only, since
those packages are linux-64. A GPU isn't needed for these steps.

Every command runs `scripts/run.sh`. It uses that environment's Python and numpy, and layers a venv
over it (`--system-site-packages`) in which pip adds only pyarrow and pandas, which the Isaac
packages don't include. The venv is built by the first task of each worker session and reused,
and needs network access to PyPI. With `CondaPackages` empty, `run.sh` builds a plain venv from
`scripts/requirements.txt` with any Python 3.9 or later instead.

Video recorded alongside a session is not imported yet.
