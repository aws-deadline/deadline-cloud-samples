#!/bin/bash
set -euo pipefail

# VINA is distributed as a single static binary — just install it
install -Dm755 "${SRC_DIR}/vina/vina_1.2.5_linux_x86_64" "${PREFIX}/bin/vina"
