# Host Configuration for After Effects and Plugins (Persistent Volumes)

A variant of [`aftereffects_redgiant`](../aftereffects_redgiant/) that supports **persistent volumes**. Software is installed once to a persistent EBS volume; subsequent worker boots restore via NTFS directory junctions in seconds instead of reinstalling.

Use this when your fleet scales up and down frequently. If you don't need persistence, use the simpler [`aftereffects_redgiant`](../aftereffects_redgiant/) script.

## How It Works

1. **First boot**: Creates junctions redirecting install paths (e.g., `C:\Program Files\Adobe`) to the persistent volume, installs software, exports Windows service state, writes `.install-complete` marker.
2. **Subsequent boots**: Detects marker, re-creates junctions, re-registers services. Takes seconds.
3. **No volume configured**: Falls back to normal install (same as base script).

## Setting Up Persistent Volumes

Configure `persistentVolumeConfiguration` on your SMF fleet. See the [Deadline Cloud persistent storage developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-persistent-storage-dev.html) and [user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/volumes.html) for full details.

Example:
```bash
aws deadline create-fleet \
    --farm-id farm-xxxxxxxxxxxxxxxxxxxxxxxxxxxx \
    --display-name "AE Persistent Fleet" \
    --role-arn arn:aws:iam::<account-id>:role/<fleet-role> \
    --max-worker-count 10 \
    --configuration '{
        "serviceManagedEc2": {
            "instanceCapabilities": {
                "vCpuCount": { "min": 4 },
                "memoryMiB": { "min": 16384 },
                "osFamily": "WINDOWS",
                "cpuArchitectureType": "x86_64",
                "acceleratorCapabilities": {
                    "selections": [{ "name": "l4" }],
                    "count": { "min": 1 }
                }
            },
            "instanceMarketOptions": { "type": "on-demand" },
            "persistentVolumeConfiguration": {
                "mountPath": "D:\\",
                "sizeGiB": 100,
                "iops": 3000,
                "throughputMiB": 125,
                "lastUsedTtlHours": 72
            }
        }
    }'
```

> **Sizing Tip**: After Effects + Red Giant + Maxon App total ~10-15 GiB. 100 GiB is more than sufficient. The console default is 200 GiB.

## Prerequisites

Same as [`aftereffects_redgiant`](../aftereffects_redgiant/README.md#prerequisites), plus:
- A fleet configured with `persistentVolumeConfiguration`

## Usage

1. Follow the [installer download and S3 upload instructions](../aftereffects_redgiant/README.md#required-installers) from the base variant.
2. Configure the script variables at the top of `install-software-with-persistent-volumes.ps1`.
3. Paste the script into your fleet's **Worker configuration script** and set timeout to **3600 seconds**.

For full configuration details (plugin toggles, CMF setup, licensing), see the [base variant README](../aftereffects_redgiant/README.md#usage).

## Troubleshooting

- If restore fails, delete the persistent volume to force a fresh install on next boot. You can manage volumes from the **Storage Capabilities** tab on your fleet in the Deadline Cloud console, or via CLI: `aws deadline list-volumes --farm-id <farm-id> --fleet-id <fleet-id>` then `aws deadline delete-volume --farm-id <farm-id> --fleet-id <fleet-id> --volume-id <volume-id>`. See [DeleteVolume API](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_DeleteVolume.html).
- If `DEADLINE_PERSISTENT_MOUNT` is not set, the script logs a warning and installs without persistence
- For general issues, see the [base variant troubleshooting](../aftereffects_redgiant/README.md#troubleshooting)
