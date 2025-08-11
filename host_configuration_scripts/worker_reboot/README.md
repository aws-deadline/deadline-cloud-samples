# This directory provides example scripts to reboot a Deadline Cloud Service Managed Worker

Worker reboots may be required for system configuration changes. For example, installing new GPU device drivers, or joining network domains.

## Linux
The [Linux example script](linux.sh) will reboot a Linux Deadline Cloud Worker. When the worker starts, host configuration scripts execute during the `STARTED` state. In the host config script, users can issue standard Linux `reboot` commands. To prevent the worker agent from starting job processing, the script sleeps for 60 seconds while the host shuts down. A `rebooted` file is saved to indicate that a reboot has been issued. Upon the second start, the Deadline Cloud agent can begin processing jobs.
