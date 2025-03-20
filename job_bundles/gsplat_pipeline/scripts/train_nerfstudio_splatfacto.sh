#!/bin/env bash
set -xeuo pipefail

# Uses NeRF Studio to train Gaussian splats with the splatfacto model, outputting a .ply Gaussian Splatting point cloud.

SCRIPT_DIR="$(dirname "$0")"
INPUT_MODEL_DIR="$1"
INPUT_IMAGES_DIR="$2"
MAX_NUM_ITERATIONS="$3"
OUTPUT_PLY_FILE="$4"
shift 4

echo "openjd_status: NeRF Studio: Processing input"
ns-process-data images \
    --data "$INPUT_IMAGES_DIR" \
    --skip-colmap \
    --colmap-model-path "$INPUT_MODEL_DIR" \
    --output-dir .

## The following can help to root cause jit compile issues.
# export TORCH_LOGS="+inductor"
# export TORCH_COMPILE_DEBUG=1
# export TRITON_DEBUG=1
# export TORCHINDUCTOR_COMPILE_THREADS=1

echo "openjd_status: NeRF Studio: Training model"
ns-train "$@" \
    --max-num-iterations "$MAX_NUM_ITERATIONS" \
    --data . \
    --output-dir ./nerfstudio_workspace \
    --logging.steps-per-log 1000 \
    --viewer.quit-on-train-completion True

python "$SCRIPT_DIR/print_workspace_dir_summary.py" .

echo "openjd_status: NeRF Studio: Exporting .ply file"
mkdir -p "$(dirname "$OUTPUT_PLY_FILE")"
if [[ "$1" == splatfacto-w* ]]; then
    # The splatfacto-w models have a special output script
    splatfactow_export \
        --load_config ./nerfstudio_workspace/$1/*/config.yml \
        --output_dir ./nerfstudio_workspace \
        --camera_idx 0
    mv ./nerfstudio_workspace/splat.ply "$OUTPUT_PLY_FILE"
else
    ns-export gaussian-splat \
        --load-config ./nerfstudio_workspace/splatfacto/*/config.yml \
        --output-dir "$(dirname "$OUTPUT_PLY_FILE")" \
        --output-filename "$(basename "$OUTPUT_PLY_FILE")"
fi
