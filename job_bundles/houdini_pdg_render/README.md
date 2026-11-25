# Houdini PDG render

This sample cooks a Houdini PDG (Procedural Dependency Graph) scene on your AWS Deadline Cloud
farm. The scene is a small coral reef, where a predator fish chases a school of small fish. The
TOP network renders the chase in six variations, writes each variation's settings on its frames,
lays the six renders out side by side, and turns those images into a short video.

Use this sample to see how the Deadline Cloud Scheduler for Houdini PDG spreads the work of one
TOP network across many workers. The scheduler is experimental, so try it on test scenes like this
one, not in production.

## The scene

The scene `reef_chase.hip` has one TOP network, `/obj/topnet1`. It makes six variations by
combining two settings:

* the size of the school, 60 or 150 fish, and
* how the predator behaves: cruising, hunting, or lunging. A cruising predator never catches the
  school, a hunting one pushes it aside, and a lunging one cuts through it and splits it.

The network runs these steps, in order:

1. Build the reef once and save it to disk. Every later render reads this one file.
2. Make the six variations.
3. For each variation, simulate the school and save each frame to disk.
4. Render each frame of each variation with Karma.
5. Write the variation's settings on each rendered frame, such as
   `School: 150 fish    Predator: lunging`.
6. Lay the six variations out side by side, one image per frame.
7. Encode those images into an MP4 video.

Every node in the scene is built from stock Houdini nodes, and the scene doesn't read any files from
outside its own folder. Each group of nodes has a note in the network editor that says what it
does.

When you cook the network, the Deadline Cloud Scheduler submits one job to your farm. Each TOP
node that does work becomes a step in that job, and each work item becomes a task. The six
variations simulate and render in parallel on different workers, and each step starts once
the steps it depends on have finished. The scene renders 5 frames, so the job has 97 tasks.

## How it works

A PDG cook with the Deadline Cloud Scheduler always runs in Houdini on your workstation. Houdini
creates the job, then releases each task once the files it needs are ready, and reports progress
back to the TOP network. Because of this, Houdini must keep running until the cook ends.

The sample has no `template.yaml`, unlike most job bundles in this repository. The
scheduler builds the job from the TOP network each time you cook it, so you start the cook from
Houdini, not with `deadline bundle submit`.

You can start the cook in two ways:

* **From the Houdini window.** Open the scene and cook the TOP network, as you would with any
  other scheduler. See [Cook from Houdini](#cook-from-houdini).
* **From the command line.** Run `hython cook.py`. The script opens the scene, cooks it, and waits
  for the cook to end, without opening the Houdini window. See
  [Cook from the command line](#cook-from-the-command-line).

Both ways create the same job.

## Requirements

You need:

* A Deadline Cloud farm and queue, with a Linux fleet. A
  [service-managed fleet](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html)
  is the easiest way to start.
* A conda queue environment on the queue, so workers can install Houdini and the other software
  the scene needs. The conda queue environment that the Deadline Cloud console creates works, once
  its channels are set as described below. For more information, see
  [Provide applications for your jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html).
* Houdini 21.0 on your workstation.
* The Deadline Cloud submitter for Houdini, version 0.7.15 or later. You can install it with the
  [Deadline Cloud submitter installer](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html).

The scheduler node lists these conda packages for the workers: `houdini=21.0.*`, `houdini-openjd=0.7.15`
and `imagemagick`. You can see them on the scheduler node's **Shared Job Settings** tab, in the
"Queue Environment: Conda" section. The scene was tested with `houdini-openjd` 0.7.15, and it
should also work with later versions. To use a later version, change the pin there, such as to
`houdini-openjd>=0.7.15`.

The workers get `houdini-openjd` from the `deadline-cloud-v2` channel and `imagemagick` from the
[conda-forge](https://conda-forge.org/) channel, so your queue's conda channels must include both.
If your queue environment's channels don't list both, set **Conda Channels** in that same section
to `deadline-cloud-v2 deadline-cloud conda-forge`
before you cook.

### Turn on the Deadline Cloud Scheduler

Do this before you open the scene, whichever way you cook it. The scene's TOP network uses a
Deadline Cloud Scheduler node, and the cook only works once the scheduler is turned on. Until
then, the scene still opens, but the cook fails with the message
`Unknown PDG scheduler type: deadlinecloudscheduler`.

The submitter installs the scheduler but leaves it turned off. To turn it on, follow
[Installing](https://github.com/aws-deadline/deadline-cloud-for-houdini/blob/mainline/src/deadline/houdini_pdg/README.md#installing)
in the Houdini PDG scheduler's README. In short, you set `"enable": true` in the scheduler's
`deadline_cloud_pdg_scheduler.json` file and restart Houdini. That README lists where the file is
for each operating system and install type.

Once it's on, **Deadline Cloud Scheduler (Experimental)** appears under Schedulers in a TOP
network's Tab menu.

### Log in and choose your farm and queue

Log in to Deadline Cloud with [Deadline Cloud monitor](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/working-with-deadline-monitor.html),
or run:

```bash
deadline auth login
```

The scene's scheduler node has an empty farm and queue. The cook uses your workstation's default
farm and queue instead. Set them once with Deadline Cloud monitor, or with these commands:

```bash
deadline config set defaults.farm_id <your farm ID>
deadline config set defaults.queue_id <your queue ID>
```

In Houdini, a farm and queue you pick on the scheduler node become your defaults too. For
`cook.py`, set the defaults before you run it. The script reads them to know where to submit.

## Cook from Houdini

1. Copy this folder to a place where you can write files. The cook writes its caches, renders and
   video next to the scene.
2. Make sure the Deadline Cloud Scheduler is turned on. See
   [Turn on the Deadline Cloud Scheduler](#turn-on-the-deadline-cloud-scheduler).
3. Open `reef_chase.hip` in Houdini 21.0.
4. Go to `/obj/topnet1`. The network's default scheduler is already `deadlinecloudscheduler1`.
5. Select `deadlinecloudscheduler1`. Check that the **Farm** and **Queue** menus show the farm and
   queue you want. Pick them there if they don't.
6. Start the cook in one of these ways:
   * Click **Cook Output Node** in the Tasks bar. `make_video`, the last node in the network, has
     the output flag, so this cooks the whole network.
   * Click **Submit** on the scheduler node. It shows the farm, queue and job name before it
     starts the cook.

The work items turn green as their tasks finish on the farm. Keep Houdini open until every node
has cooked.

## Cook from the command line

1. Copy this folder to a place where you can write files.
2. Make sure the Deadline Cloud Scheduler is turned on. See
   [Turn on the Deadline Cloud Scheduler](#turn-on-the-deadline-cloud-scheduler).
3. Make sure your default farm and queue are set, as described in
   [Log in and choose your farm and queue](#log-in-and-choose-your-farm-and-queue).
4. Run `cook.py` with `hython`, which comes with Houdini:

   ```bash
   cd houdini_pdg_render
   hython cook.py
   ```

   On Windows, `hython.exe` is in the `bin` folder of your Houdini install, such as
   `"C:\Program Files\Side Effects Software\Houdini 21.0.440\bin\hython.exe" cook.py`.

The script prints one line when the cook starts and nothing more until the cook ends, which takes
about 20 minutes. Watch the job's progress in Deadline Cloud monitor meanwhile. When the cook ends,
the script prints the result, and it exits with status 1 if the cook didn't finish or any work
item didn't succeed.

## Expected output

Each cook creates one job on your farm, named `reef_chase`. You can watch it in Deadline Cloud
monitor while it runs.

The scheduler doesn't copy the results back to your workstation. When the job has finished,
download them with Deadline Cloud monitor, or with:

```bash
deadline job download-output --job-id <job ID>
```

The download puts the files under the folder you cooked from:

| Folder | What it holds |
|---|---|
| `geo/` | The reef, and the school simulation for each variation |
| `render/` | The Karma frames, one folder per variation |
| `images/overlay/` | The same frames, with the variation's settings written on them |
| `images/mosaic/` | One image per frame, with all six variations side by side |
| `video/reef_chase.mp4` | The mosaic frames as a video |

The download also has `temp/` and `pdgtemp/` folders. These hold working files that PDG writes
during the cook, such as the list of frames for the video, and you can ignore them.

## Cost and cleanup

The cook runs as one job of 97 tasks. On a service-managed fleet that can scale to 30 workers, it
took about 20 minutes and used up to 23 workers at once. You pay for the worker time, and on a
service-managed fleet also for Houdini usage-based licensing. A fleet with fewer workers takes
longer.

The cook leaves its caches and renders in the folder you cooked from, and in your queue's job
attachments bucket. Delete the folder when you're done with it.

## Troubleshooting

* **The cook fails with `Unknown PDG scheduler type: deadlinecloudscheduler`.** The Deadline
  Cloud Scheduler is turned off. See
  [Turn on the Deadline Cloud Scheduler](#turn-on-the-deadline-cloud-scheduler).
* **The `overlay_text` or `mosaic` step fails to set up its environment.** The workers couldn't
  find `houdini-openjd` or `imagemagick`. Set **Conda Channels** as described in
  [Requirements](#requirements).
* **The cook stops at the start with a message about the farm or queue.** Your default farm and
  queue aren't set, or your login has expired. Log in again and set them.
* **The cook refuses to start because of unsaved changes.** The scheduler cooks the saved scene.
  Save the scene, then cook again.
* **The scheduler node shows a yellow warning badge after the cook.** A message such as
  `Local variable 'school_size' not found.` comes from Houdini reading the scene's output paths
  outside a work item. It doesn't affect the cook, and you can ignore it.
* **A task fails.** Open the job in Deadline Cloud monitor and read the task's log. Each cook also
  writes a log and a copy of the job it submitted to `pdg_debug/` next to the scene.

## Related resources

* [Houdini PDG scheduler for Deadline Cloud](https://github.com/aws-deadline/deadline-cloud-for-houdini/blob/mainline/src/deadline/houdini_pdg/README.md)
  explains how a cook maps to a job, the checks it runs before it submits, and how to read a
  failed cook.
* [Houdini Husk USD render](../houdini_husk_usd_render/) renders a USD file with Karma, without
  PDG.
