# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). The version is the package version, stamped into `extension.toml` when the wheel is built.

## [Unreleased]

### Added

- **Tools > Deadline Cloud > Open Deadline Cloud** opens the AWS Deadline Cloud for Isaac Sim app (`deadline-physical-ai gui --bridge`) connected to Isaac Sim, or brings it to the front. The app exits when Isaac Sim quits.
- The app (also runs without Isaac Sim, on Windows, Linux and macOS) has farm and queue pickers by name with **Set as default** and a completed-jobs table. Its outputs table has kind filters and shows the job's eval summary. It downloads selected items through `deadline-physical-ai outputs fetch` with progress, reusing downloaded files. Its Submit tab scans job bundle folders and opens the stock `deadline bundle gui-submit` dialog, prefilled with the open stage, the last loaded job, and loaded datasets or checkpoint. It warns when a required dataset or checkpoint input is empty.
- Replay of `*.trajectory.npz` trajectories under PhysX in the open stage, with **Play** and **Stop**, and optional object and robot placement at the recorded start (`objectPrim`, `referencePrim`).
- USD outputs are added as references under `/World/DeadlineCloud`. Videos open with the OS.
- **Submit pipeline job with dataset**: loaded datasets and checkpoints become the next job's inputs.
- A stdin and stdout bridge between the extension and the app: newline-delimited JSON, no sockets, and loads accepted only for files inside the app's download folder with the expected extension.
- Finds `deadline-physical-ai` next to Isaac Sim's Python. With a same-environment install, `PATH` setup isn't needed.
- Plain-language errors for missing, expired or insufficient credentials, and a timeout for CLI calls that wait on a sign-in.
- Windows and Linux support.
