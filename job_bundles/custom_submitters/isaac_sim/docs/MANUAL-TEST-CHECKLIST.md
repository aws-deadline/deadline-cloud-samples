# Manual test checklist

Run before a release. Standalone: once each on Windows, Linux and macOS, with a display and no Isaac Sim. With Isaac Sim: once on Windows and once on Linux, on the oldest and newest supported Isaac Sim (5.1.0 and 6.2). Record the OS, Isaac Sim version, `deadline --version`, and the package and extension version.

Placeholders: `<farm>`, `<queue>`, `<job-id>` (a completed job whose outputs include a `*.trajectory.npz`, a USD file, an `.mp4`, a LeRobot dataset, a checkpoint folder and an `eval_summary.json`), `<bundle>` (your own job bundle with a USD parameter, a dataset parameter and a `FromJobId` parameter; the README's example bundle covers the first and last).

## Setup

- [ ] `pip install ".[gui]"` from this sample folder (or `pip install -e ".[gui]"`). `deadline --version`, `deadline-physical-ai --help` and `deadline-physical-ai gui --help` run.
- [ ] In an environment without the `gui` extra (no PySide6), `deadline-physical-ai gui` says to install the extra and exits 1; `--json` prints one error object.
- [ ] `deadline config gui` shows a working profile, or you are signed in to Deadline Cloud Monitor.
- [ ] Linux: the Qt6 xcb libraries from the README are installed.

## Standalone app

- [ ] `deadline-physical-ai gui` opens the window. The status bar says it is standalone. No Isaac Sim buttons (Load in Isaac Sim, Play, Stop) are shown.
- [ ] `settings.json` is created under `%APPDATA%\deadline-cloud-for-isaac-sim\` (Windows) or `~/.config/deadline-cloud-for-isaac-sim/` (Linux, macOS) after Rescan or a load.
- [ ] Run the Job outputs, Submit and Submit with dataset sections below. Trajectories and USD files download, and the notes say replay needs Isaac Sim. In Submit, no stage path is prefilled and no unsaved-stage note appears.
- [ ] The submitted job's submitter info has `submitter_package_name=deadline-cloud-for-isaac-sim` and no host application.
- [ ] Close the window with a download running. No `deadline-physical-ai` child is left behind.

## Isaac Sim setup

- [ ] Install into Isaac Sim's pip environment. `deadline-physical-ai isaac-sim extension-path` prints a folder containing `isaacsim.deadline.submitter/config/extension.toml`. For a wheel install, its `version` equals the package version (Kit form).
- [ ] `deadline-physical-ai isaac-sim install-extension --enable` with Isaac Sim closed reports `link_status: created` under `<isaacsim>/extsUser` and the enabled entry `added`. Running it again reports `exists` and `present`.
- [ ] Repeat in a separate virtual environment with no `isaacsim` package: it links into `~/Documents/Kit/shared/exts` (Windows: `%USERPROFILE%\Documents\Kit\shared\exts`), and `--enable` asks for `--isaac-sim-version`.
- [ ] Windows: the link is a directory junction (`dir` shows `<JUNCTION>`), created without administrator rights.
- [ ] Start Isaac Sim normally. The extension is enabled, and the console shows no errors from it.
- [ ] **Tools > Deadline Cloud** has one item, **Open Deadline Cloud**.
- [ ] Alternative: with the link removed (`install-extension --uninstall`), start Isaac Sim with `--ext-folder "$(deadline-physical-ai isaac-sim extension-path)" --enable isaacsim.deadline.submitter`. The menu appears.

## Isaac Sim bridge

- [ ] **Open Deadline Cloud** opens the app. The status bar says "Connected to Isaac Sim" with the Isaac Sim and extension versions. No console window appears on Windows.
- [ ] Choose it again with the app behind Isaac Sim or minimized. The same window comes to the front; no second app starts (one `deadline-physical-ai gui --bridge` process).
- [ ] Close the app window, then choose the menu item again. A new app opens.
- [ ] Kill the app process. The Isaac Sim console reports that it exited; the next menu choice starts a new one.
- [ ] Set `physicalAiExecutable` to a path that does not exist. The menu item reports `deadline-physical-ai not found` naming the setting. Clear it.
- [ ] Remove `deadline-physical-ai` from `PATH` with the package installed in Isaac Sim's environment. It is still found next to Isaac Sim's Python.
- [ ] Quit Isaac Sim with the app open. The app closes within a few seconds and no `deadline-physical-ai` process is left behind.
- [ ] Disable and re-enable the extension in **Window > Extensions** with the app open. The app closes; the menu item disappears and comes back once, with no duplicates and no console errors.

## Job outputs

- [ ] Farm and queue pickers show names, starting at your Deadline Cloud defaults.
- [ ] Farm and Queue sit above the tabs and stay visible on every tab. Tables and the bundle list never change height: while loading or empty they show a dimmed message inside. Switch to `<farm>` and `<queue>`. **Jobs** lists succeeded jobs by default, newest finished first. Switch the status filter to **Failed**, **Canceled** and **Any finished**: each lists only those jobs, the Status column matches, and a failed job's outputs show the partial-outputs note. In a queue with more than 50, **Load more** appends the next page and its label counts loaded of total.
- [ ] Select a job: **Parameters** lists its parameters. Cmd/Ctrl-click a second job: the heading reads **Parameters that differ**, the columns are named after both jobs, a parameter only one job has shows **(not set)**, and long paths are shortened in the middle (full value on hover). Two jobs with the same parameters show "Both jobs have the same parameters".
- [ ] Select a finished job whose bundle is in your bundle folders and press **Resubmit with changes**: Submit opens with that bundle selected, the details list the job's values as prefilled, and the status counts them. Open the dialog: the values are there and no "parameters are not recognized" warning appears. Pick another bundle: only the parameters it defines stay prefilled. **Don't reuse its values** returns to the usual prefill.
- [ ] Open **Evaluations**: nothing is read until **Read eval results from queue**. Then it reads the queue chosen above the tabs and lists only jobs with an `eval_summary.json`, sorted by success rate. Click headers to sort numerically (Success, Episodes, parameter columns). Only parameters that differ between the listed jobs have columns (never `OutputDir`). Double-click a job: Job outputs shows its outputs. **Export CSV...** writes one row per listed job with every parameter. Switch the queue: the old rows disappear until **Read eval results from queue** is pressed again. A job that ran `lerobot eval` (its `eval_info.json`) appears with its success rate and interval.
- [ ] **Set as default**. `deadline config get defaults.farm_id` and `defaults.queue_id` return the new ids. The button disables for the current pair.
- [ ] Select `<job-id>`. The outputs table lists items, the kind filter shows counts per kind, and the eval summary (successes / episodes) is shown.
- [ ] Each kind filter (Trajectories, USD, Eval summaries, Videos, Datasets, Checkpoints, HDF5) shows only that kind. **All** restores the list.
- [ ] Tick one USD item and **Download selected**. The status line shows download progress (MB, %, files), then "Loaded 1 item(s) to <folder>". Connected, nothing is sent to Isaac Sim.
- [ ] Connected: tick it and **Load in Isaac Sim**. The USD appears as a reference under `/World/DeadlineCloud`, with no new download.
- [ ] Download the same item again. It reports "already downloaded" with no new download.
- [ ] Download a video, then double-click its row. It opens in the OS default player.
- [ ] With `downloadDir` empty, files land in `~/.deadline/physical-ai/job_outputs/<job-id>`. Set `downloadDir` in the app's settings file, restart the app, load again, and files land in `<downloadDir>/<job-id>`; connected, the USD still loads into the stage.
- [ ] Download a large dataset (over 1 GB). Progress updates during the download, and the app stays responsive; connected, Isaac Sim does too (viewport orbits, timeline plays).

## Replay (connected)

- [ ] Open a stage authored for the test with a robot at `robotPrim` whose joint prim names match the trajectory's `joint_names`. Leave `objectPrim` and `referencePrim` empty.
- [ ] Tick one trajectory and **Load in Isaac Sim**. It plays. The note shows frames and seconds and, if the file has `object_T_reference`, says object placement was skipped. Play and Stop enable.
- [ ] Set `objectPrim` and `referencePrim` to an object and a frame in the stage, then load the trajectory again. The note says the object was placed at the recorded start.
- [ ] **Play**. The robot resets to the recorded start and the trajectory plays under PhysX. **Stop** ends it. Pressing Play on the timeline also plays the loaded trajectory.
- [ ] Tick another trajectory and **Load in Isaac Sim**. It downloads if needed, then loads and plays.
- [ ] Set `robotPrim` to a prim with no matching joints. Loading a trajectory shows a clear "no joints" error in the app; Isaac Sim keeps running.
- [ ] A `.npz` missing `hz` shows an error naming the missing array, and a non-trajectory `.npz` says it is not a trajectory.
- [ ] An older evaluator rollout (`diag_ep_*.npz` with `roll_*` arrays) loads and plays.

## Submit

- [ ] Put `<bundle>` under a folder in `bundleDirs`. Open the Submit tab; it lists `<bundle>`. Edit the folder field and **Rescan** to pick up another folder.
- [ ] Connected, with a saved stage open, selecting `<bundle>` shows "Prefilled <param> = <stage path>". Save the stage under a new name and select it again: the new path is shown.
- [ ] Connected, with an unsaved stage, the tab says no scene path is prefilled.
- [ ] The `FromJobId` parameter is prefilled with the last loaded `<job-id>`.
- [ ] With no dataset loaded, a red warning names the empty dataset parameter.
- [ ] **Open submit dialog**. The stock Deadline Cloud dialog opens with the prefilled values. The app (and Isaac Sim) stay responsive while it is open.
- [ ] Close the dialog without submitting. The tab reports it closed without submitting.
- [ ] Submit. The dialog closes and the tab shows "Submitted <job-id>". The job appears in Deadline Cloud Monitor, with the submitter package `deadline-cloud-for-isaac-sim` and its version and, connected, the Isaac Sim version.

## Submit with dataset

- [ ] In Job outputs, tick a dataset. The button reads **Submit pipeline job with dataset**.
- [ ] Press it. The dataset downloads, the Submit tab opens with a bundle that takes a dataset selected, and its dataset parameter is prefilled with the local path.
- [ ] Tick two datasets and repeat. The dataset parameter points at one folder holding both.
- [ ] Tick a checkpoint and repeat. The checkpoint parameter is prefilled.
- [ ] With no bundle that takes a dataset, the tab says so instead of submitting.

## Credentials and configuration errors

- [ ] Expired credentials: let the Deadline Cloud Monitor session expire (or sign out), then **Refresh**. The app says the credentials have expired. Sign in, **Refresh**, and it recovers without restarting.
- [ ] No credentials: point `deadline config gui` at a profile with no credentials. The app says there are no AWS credentials.
- [ ] No farm: use credentials that see no farms. The app says no farms are visible; nothing crashes.
- [ ] Set `AWS_PROFILE` to another profile before starting the app. It still uses the profile from `deadline config`, or fails with a readable error.
- [ ] Set `deadlineExecutable` to a path that does not exist. The app names the setting. Clear it and **Refresh**.
- [ ] A CLI call that hangs (for example, waiting on a sign-in) times out after about 90 seconds with a message, and the app stays usable.

## Lifecycle

- [ ] Change `bundleDirs` with **Rescan** and restart the app. The value persists.
- [ ] `install-extension --uninstall` with Isaac Sim closed removes the link and the enabled entry; the next start has no Deadline Cloud menu.

- [ ] Pick a farm and queue that are not your defaults and open the submit dialog from Submit: it shows "Submits to <farm> / <queue> (chosen above; your defaults are unchanged)", the dialog's job settings show that farm and queue, the job lands there, and `deadline config get defaults.queue_id` still prints your default afterwards.
