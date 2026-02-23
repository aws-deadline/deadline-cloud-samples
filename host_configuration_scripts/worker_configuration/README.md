# This directory provides example scripts for custom configurations on Deadline Cloud Service Managed Workers

These scripts demonstrate common configuration tasks that may be required for your workloads. For example, adjusting system settings, configuring memory management, or setting up environment-specific parameters.

For setup instructions and troubleshooting guidance, refer to the [host_configuration_scripts README](../README.md).

## Windows

### Page File Configuration
The [configure_page_file.ps1](windows/configure_page_file.ps1) script configures the Windows page file size and placement. It prefers local NVMe instance storage when available for optimal performance.

Page file sizing logic:
- For NVMe drives: By default, uses the smaller of 2x RAM or 75% of NVMe space
- If NVMe is not available: By default, uses the largest non-boot drive with 2x RAM
- If no non-boot drives are available: Falls back to the boot drive (C:)

The script automatically detects Amazon EC2 NVMe instance storage, disables automatic page file management, formats the drive and assigns a drive letter if needed, and reboots the worker to apply changes. A marker file (`C:\deadline-pagefile-configured`) prevents reconfiguration on subsequent starts.

#### Configuration Options
Adjust these variables at the top of the script to fit your workload requirements:

| Variable | Default | Description |
|----------|---------|-------------|
| `$RAM_MULTIPLIER` | 2 | Page file size as a multiple of RAM (e.g., 2 = 2x RAM) |
| `$NVME_SPACE_PERCENTAGE` | 0.75 | Max percentage of NVMe space to use for the page file (e.g., 0.75 = 75%) |
| `$MIN_DISK_SIZE_GB` | 1 | Minimum disk size in GB to consider for storing page file |
| `$MARKER_FILE_PATH` | `C:\deadline-pagefile-configured` | Path to the marker file that prevents reconfiguration |
