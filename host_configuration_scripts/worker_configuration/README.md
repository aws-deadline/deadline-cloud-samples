# This directory provides example scripts for custom configurations on Deadline Cloud Service Managed Workers

These scripts demonstrate common configuration tasks that may be required for your workloads. For example, adjusting system settings, configuring memory management, or setting up environment-specific parameters.

For setup instructions and troubleshooting guidance, refer to the [host_configuration_scripts README](../README.md).

## Windows

### Page File Configuration
The [configure_page_file.ps1](windows/configure_page_file.ps1) script configures the Windows page file size based on available RAM. It automatically selects the drive with the most free space, sets the page file to 2x the system RAM, and reboots the worker to apply changes. A marker file (`C:\deadline-pagefile-configured`) prevents reconfiguration on subsequent starts.
