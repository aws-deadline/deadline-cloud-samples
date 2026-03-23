#!/bin/bash
# Grant passwordless sudo to job-user on Deadline Cloud service managed fleet workers.
# Run this as a host configuration script (runs as root).

set -e

echo "[$(date)] Configuring passwordless sudo for job-user..."

if id "job-user" &>/dev/null; then
    echo "job-user ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/job-user
    chmod 440 /etc/sudoers.d/job-user
    echo "Passwordless sudo configured for job-user."
else
    echo "WARNING: job-user does not exist yet. This is expected if the worker agent has not started."
    echo "The worker agent will create job-user on first job. Re-run this script or add it to fleet host config."
fi

echo "[$(date)] Done."
