#!/bin/bash

# Submits a variety of Gaussian Splatting jobs to verify the job bundle is working as expected.
# You'll need to download and manually verify the outputs are as expected.

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_video_file>"
    exit 1
else
    INPUT_VIDEO=$1
fi

JOB_BUNDLES_DIR="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$JOB_BUNDLES_DIR"

SHARED_OPTIONS="--max-retries-per-task 0
    -p MaxNumIterations=10000
    -p InputVideoFile=$INPUT_VIDEO"

# # If you're debugging the nerfstudio package build, this option will force
# # re-creation of the environment to ensure you always get your latest build.
# SHARED_OPTIONS="$SHARED_OPTIONS -p NamedCondaEnvAction=REMOVE_AND_CREATE"

for  NS_OPTION in "splatfacto" "splatfacto-w-light" "splatfacto-big"
do
    echo y | deadline bundle submit gsplat_pipeline \
        --name "GSplat Test: nerfstudio $NS_OPTION" \
        -p OutputPlyFile="gsplat_pipeline/output/vw_test_nerfstudio_$NS_OPTION.ply" \
        -p GaussianSplattingTrainer=NERFSTUDIO \
        -p NerfStudioOptions="$NS_OPTION" \
        $SHARED_OPTIONS
done

for  GSPLAT_OPTION in "mcmc" "default"
do
    echo y | deadline bundle submit gsplat_pipeline \
        --name "GSplat Test: simpletrainer $GSPLAT_OPTION" \
        -p OutputPlyFile="gsplat_pipeline/output/vw_test_simpletrainer_$GSPLAT_OPTION.ply" \
        -p GaussianSplattingTrainer=GSPLAT_SIMPLE_TRAINER \
        -p GSplatSimpleTrainerOptions="$GSPLAT_OPTION" \
        $SHARED_OPTIONS
done
