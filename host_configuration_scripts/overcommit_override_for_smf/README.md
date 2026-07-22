# Override Memory Overcommit on Service Managed Fleet Workers

Override the default `vm.overcommit_memory=2` (strict accounting) on Linux service managed fleet workers. Useful for memory-intensive workloads with large job attachments that cause malloc failures despite free physical RAM.

## Why Override Overcommit?

The default SMF worker AMI sets `vm.overcommit_memory=2`, which enforces: `CommitLimit = swap + RAM`. With 0 swap, the CommitLimit equals total RAM. Workloads with large job attachments (e.g. 134 GB of Blender scene files) can inflate committed memory beyond this limit, causing malloc failures even when 75%+ of physical RAM is free.

Setting `vm.overcommit_memory=1` switches to heuristic overcommit, allowing allocations as long as physical RAM is available. The trade-off is that if a workload actually exceeds physical RAM, the OOM killer will terminate a process instead of returning a clean malloc failure.

## Script actions

1. Sets `vm.overcommit_memory=1` immediately via `sysctl`
2. Persists the setting to `/etc/sysctl.d/99-overcommit.conf` for reboots

## Configuration

Edit `linux.sh` to change the overcommit mode:

```
OVERCOMMIT_MODE="1"  # 0=heuristic, 1=always allow, 2=strict (default on SMF)
```

## Usage

1. Open the AWS Deadline Cloud console
2. Navigate to your fleet
3. Go to the "Host configuration" section
4. Copy and paste the contents of `linux.sh` into the script field
5. Save the configuration

New fleet instances will automatically apply the overcommit override on startup.

## Alternative: Swap

If you prefer to keep `vm.overcommit_memory=2`, you can add swap instead to increase the CommitLimit. See [swap_for_smf](../swap_for_smf). Note that the EBS volume must be large enough to hold the swap file alongside job attachments.
