#!/usr/bin/env bash
set -xeuo pipefail

## Install the two packages that are not on conda-forge.
#
# Both wheels are recipe sources, downloaded and SHA256-checked by rattler-build,
# so pip installs them from $SRC_DIR without reaching an index. --no-deps keeps
# every other dependency coming from conda-forge through the recipe's run
# requirements.
python -m pip install --no-deps --no-index --no-build-isolation \
    "$SRC_DIR"/strands_robots-*.whl \
    "$SRC_DIR"/mink-*.whl

## Bundle the so100 robot model.
#
# Loading a robot imports robot_descriptions.<name>_mj_description, which clones
# MuJoCo Menagerie into ROBOT_DESCRIPTIONS_CACHE on first use. Cloning it here,
# at the commit robot_descriptions pins, means a job finds the clone already in
# place and never reaches GitHub. A partial, sparse clone fetches only the so100
# directory instead of the whole Menagerie, which is several hundred megabytes.
CACHE_DIR="$PREFIX/share/robot_descriptions"
MENAGERIE_DIR="$CACHE_DIR/mujoco_menagerie"
mkdir -p "$CACHE_DIR"
git clone --filter=blob:none --no-checkout \
    https://github.com/google-deepmind/mujoco_menagerie.git "$MENAGERIE_DIR"
git -C "$MENAGERIE_DIR" sparse-checkout set trs_so_arm100
git -C "$MENAGERIE_DIR" checkout "$MENAGERIE_GIT_REV"

## Bundle the ResNet18 ImageNet weights.
#
# The ACT policy's default vision backbone is a torchvision resnet18 built with
# pretrained weights, which torch.hub otherwise downloads from
# download.pytorch.org the first time training starts. TORCH_HOME points at the
# bundled copy, so training needs no network either.
TORCH_HOME_DIR="$PREFIX/share/torch"
mkdir -p "$TORCH_HOME_DIR/hub/checkpoints"
cp "$SRC_DIR/$RESNET18_WEIGHTS" "$TORCH_HOME_DIR/hub/checkpoints/$RESNET18_WEIGHTS"

## Point robot_descriptions and torch.hub at the bundled copies when the
## environment activates.
#
# See https://rattler-build.prefix.dev/latest/special_files/ for env_vars.d.
mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/$PKG_NAME.json" << VAREOF
{
  "ROBOT_DESCRIPTIONS_CACHE": "$CACHE_DIR",
  "TORCH_HOME": "$TORCH_HOME_DIR"
}
VAREOF
