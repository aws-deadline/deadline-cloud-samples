"""Pull finished renders back to the studio drive with Deadline Cloud's official
auto-downloader.

Deadline Cloud ships an incremental output downloader as the CLI command
``deadline queue sync-output``. It walks a queue, finds the job-session-actions
that have completed since its last run (tracked in a checkpoint file), and
downloads their outputs to the paths they were submitted from. See the
"automatic downloads" page in the Deadline Cloud user guide:
https://docs.aws.amazon.com/deadline-cloud/latest/userguide/auto-downloads.html

Because ``sync-output`` restores to the *submission-side* output path and has no
"download somewhere else" flag, this sample submits each shot with its
``OutputDir`` set to ``studio/renders/<shot_id>`` (see submit.py). The downloader
then lands the frames, movie, and thumbnail straight on the shared drive with no
copy step of our own.

``studio-pipe autodownload`` is a thin wrapper over that command:

  * with ``--job-id`` it first blocks on ``deadline job wait`` so "submit, then
    fetch my shot's frames" works as a single call; then it runs sync-output.
  * without ``--job-id`` it just runs sync-output, pulling every newly finished
    output in the queue to its submission path (its intended continuous use).

The sample submits and downloads on one machine, so it passes
``--ignore-storage-profiles``: outputs download to their original (unmapped)
paths and no storage profile needs to be configured. A studio whose artists
download on different machines or operating systems would instead configure a
storage profile and drop that flag, so paths map correctly; the command is
otherwise identical. In production the same command is run continuously (from
cron or a queue event); the checkpoint makes each run resume where the last one
left off.
"""
from __future__ import annotations

import subprocess

# The Deadline Cloud CLI entrypoint. Installed as a console script by the
# `deadline` package (a dependency of studio-pipe).
DEADLINE = "deadline"

# Bootstrap window used the first time sync-output runs for a queue (before a
# checkpoint exists). It must comfortably cover the render we just waited on, so
# a job whose early frames finished a while before the final publish is still
# picked up. The sample's shots render in minutes; raise --lookback-minutes for
# longer jobs. On later runs the checkpoint is used and this value is ignored.
DEFAULT_LOOKBACK_MINUTES = 60.0


def _common_args(farm_id: str | None, queue_id: str | None) -> list[str]:
    args = []
    if farm_id:
        args += ["--farm-id", farm_id]
    if queue_id:
        args += ["--queue-id", queue_id]
    return args


def wait_for_job(job_id: str, farm_id: str | None = None, queue_id: str | None = None) -> int:
    """Block until the job reaches a terminal state. Returns the CLI exit code.

    ``deadline job wait`` exits 0 on success and non-zero for failed/canceled/
    suspended/timeout (see its --help for the code table), which we pass through.
    """
    cmd = [DEADLINE, "job", "wait", "--job-id", job_id] + _common_args(farm_id, queue_id)
    print(f"Waiting for {job_id} to finish...")
    return subprocess.run(cmd).returncode


def sync_outputs(
    farm_id: str | None = None,
    queue_id: str | None = None,
    lookback_minutes: float = DEFAULT_LOOKBACK_MINUTES,
    checkpoint_dir: str | None = None,
    ignore_storage_profiles: bool = True,
) -> int:
    """Run ``deadline queue sync-output`` to download newly finished outputs.

    Downloads every output produced in the queue since the last checkpoint (or,
    on the first run, within ``lookback_minutes``) to its submission-side path.
    Returns the CLI exit code.
    """
    cmd = [DEADLINE, "queue", "sync-output",
           "--bootstrap-lookback-minutes", str(lookback_minutes)]
    if ignore_storage_profiles:
        cmd.append("--ignore-storage-profiles")
    if checkpoint_dir:
        cmd += ["--checkpoint-dir", checkpoint_dir]
    cmd += _common_args(farm_id, queue_id)
    print("Syncing completed outputs from the queue to their submission paths...")
    return subprocess.run(cmd).returncode


def autodownload(
    job_id: str | None = None,
    farm_id: str | None = None,
    queue_id: str | None = None,
    lookback_minutes: float = DEFAULT_LOOKBACK_MINUTES,
    checkpoint_dir: str | None = None,
    ignore_storage_profiles: bool = True,
) -> int:
    """Optionally wait for a job, then run the official queue auto-downloader.

    Returns a process exit code. If a waited-on job did not succeed we still run
    the download (a partially successful job may have produced some frames) but
    report the wait's exit code so the caller learns the job's real outcome.
    """
    wait_rc = 0
    if job_id:
        wait_rc = wait_for_job(job_id, farm_id, queue_id)
        if wait_rc != 0:
            print(f"Job {job_id} did not succeed (deadline job wait exit {wait_rc}); "
                  f"downloading any available outputs anyway.")
    sync_rc = sync_outputs(
        farm_id=farm_id,
        queue_id=queue_id,
        lookback_minutes=lookback_minutes,
        checkpoint_dir=checkpoint_dir,
        ignore_storage_profiles=ignore_storage_profiles,
    )
    return wait_rc or sync_rc
