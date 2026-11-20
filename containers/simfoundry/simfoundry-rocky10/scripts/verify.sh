#!/usr/bin/env bash
# Checks the image on a GPU host, which docker build cannot do.
#
# Usage: verify-simfoundry [--isaac]
#   --isaac   Also boot Isaac Sim headless and render one frame. It takes about a minute.
set -euo pipefail

root="${SIMFOUNDRY_ROOT:-/opt/SimFoundry}"
boot_isaac=false
[[ "${1:-}" == "--isaac" ]] && boot_isaac=true

echo "== GPU"
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv

# The CUDA extensions were compiled for a fixed arch list. A GPU outside it fails on its
# first kernel launch, so say so up front.
built_archs="$(sed -n 's/^cuda_arch_list=//p' /simfoundry-refs.txt)"
while read -r cap; do
  if [[ ";${built_archs};" != *";${cap};"* ]]; then
    echo "ERROR: GPU compute capability ${cap} is not in the image's CUDA_ARCH_LIST (${built_archs})." >&2
    echo "Rebuild with --build-arg CUDA_ARCH_LIST=\"${built_archs};${cap}\"." >&2
    exit 1
  fi
done < <(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | sort -u)

echo "== CUDA in each env"
for env in simfoundry hunyuan any6d da3; do
  mamba run -n "${env}" python -c '
import sys, torch
assert torch.cuda.is_available(), "torch cannot see a GPU"
x = torch.ones(1024, device="cuda")
print(sys.argv[1], torch.__version__, torch.cuda.get_device_name(0), float(x.sum()))
' "${env}"
done

echo "== FAISS GPU search"
# shellcheck source=/dev/null
source "${root}/scripts/installation/faiss_gpu.sh"
for env in simfoundry any6d da3; do
  validate_faiss_gpu "${env}"
done

if [[ "${boot_isaac}" == true ]]; then
  # Isaac Sim 5.1 segfaults in librtx.scenedb at startup with 595-series drivers. On a
  # Deadline Cloud fleet, pin the accelerator runtime to grid:r580.
  driver_major="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1 | cut -d. -f1)"
  if (( driver_major >= 590 )); then
    echo "WARNING: driver ${driver_major}.x. Isaac Sim 5.1 is known to crash at startup on 595-series drivers." >&2
  fi

  echo "== Isaac Sim headless render"
  mamba run -n simfoundry python -c '
import os
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
import numpy as np
import omni.replicator.core as rep
rep.create.light(light_type="dome", intensity=1000)
rep.create.cube(position=(0, 0, 0), scale=0.5)
camera = rep.create.camera(position=(2, 2, 2), look_at=(0, 0, 0))
rgb = rep.AnnotatorRegistry.get_annotator("rgb")
rgb.attach([rep.create.render_product(camera, (320, 240))])
for _ in range(20):
    rep.orchestrator.step()
pixels = np.asarray(rgb.get_data())[..., :3]
lit = int((pixels.sum(-1) > 0).sum())
print(f"Isaac Sim rendered {pixels.shape[1]}x{pixels.shape[0]}, {lit} lit pixels, mean {pixels.mean():.1f}", flush=True)
# app.close() ends the process with status 0, so the check has to come first.
if not lit:
    print("ERROR: Isaac Sim rendered an all-black frame", flush=True)
    os._exit(1)
app.close()
'
fi

echo "verify-simfoundry passed"
