#!/usr/bin/env bash
# Build-time stand-in for SimFoundry's scripts/installation/faiss_gpu.sh. The installers
# source this file by that name. It keeps upstream's install_faiss_gpu and replaces only
# validate_faiss_gpu, whose GPU search cannot pass in a build with no GPU. The Dockerfile
# restores the upstream file afterwards, and verify-simfoundry runs its check on a GPU.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/faiss_gpu.upstream.sh"

validate_faiss_gpu() {
  local env_name="${1:?env name is required}"
  mamba run -n "${env_name}" python -c '
import faiss
missing = [n for n in ("StandardGpuResources", "GpuIndexFlatL2", "get_num_gpus") if not hasattr(faiss, n)]
if missing:
    raise SystemExit(f"FAISS is not GPU-capable; missing {missing} in {faiss.__file__}")
print(f"FAISS {faiss.__version__} has its GPU symbols; the GPU search runs in verify-simfoundry")
'
}
