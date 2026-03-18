#!/bin/bash
# Host configuration for Deadline Cloud workers running SSM Managed Node jobs.
# The SSM agent install requires root access, so job-user needs passwordless sudo.
#
# Run this on the worker host (or via fleet host config) before submitting jobs.

set -e

# Allow job-user (Deadline worker user) to run commands as root without a password
if id "job-user" &>/dev/null; then
    echo "job-user ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/job-user
    echo "Passwordless sudo configured for job-user."
else
    echo "WARNING: job-user does not exist yet. Run this after the Deadline worker agent is installed."
fi
