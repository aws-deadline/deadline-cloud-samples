# AWS Deadline Cloud submission hooks

Submission hooks inspect or modify job bundles immediately before the Deadline Cloud CLI submits them. Use them for workstation-side policy that should apply consistently across jobs.

## Sample index

This table covers every immediate sample directory in `submission_hooks/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [License limits](license_limits/) | Injecting fixed-license host requirements into every step before submission | Artists should receive centrally enforced license scheduling without editing job templates |

Read the sample README for workstation deployment, security implications, Deadline Cloud Limit setup, and testing instructions.
