#!/bin/bash
# Host configuration script for the LIBERO GPU fleet. Runs as root on each new worker.
#
# The fleet's Docker software add-on installs rootless Docker and GPU support, so this
# script only changes one kernel setting. Service-managed fleet workers default to
# vm.overcommit_memory=2. PyTorch plus many simulator processes reserve far more virtual
# memory than they use, so strict accounting fails them with MemoryError while memory is
# still free.
set -euo pipefail

sysctl -w vm.overcommit_memory=1
echo "vm.overcommit_memory=1" > /etc/sysctl.d/99-overcommit.conf
