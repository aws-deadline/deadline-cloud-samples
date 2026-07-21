# AWS Deadline Cloud submission hooks

Submission hooks inspect or modify job bundles immediately before the Deadline Cloud CLI submits them. Use them for workstation-side policy that should apply consistently across jobs.

## Sample index

This table covers every immediate sample directory in `submission_hooks/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [License limits](license_limits/) | Injecting fixed-license host requirements into every step before submission | Artists should receive centrally enforced license scheduling without editing job templates |

Read the sample README for workstation deployment, security implications, Deadline Cloud Limit setup, and testing instructions.

Hooks can also live inside a job bundle (`hooks.yaml` alongside `template.yaml`) instead of a
workstation-wide directory. The [Blender wedge render from CSV](../job_bundles/blender_wedge_from_csv/)
job bundle uses a bundle-local pre-submission hook to expand a CSV file into the job's task parameters,
and the [Blender turntable to Flow](../job_bundles/blender_turntable_to_flow/) bundle uses one to fill
job parameters from studio environment variables.
