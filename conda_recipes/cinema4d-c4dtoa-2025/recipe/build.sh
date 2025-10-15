#!/bin/bash
# To install the plugin we copy it into the Cinema 4D plugins dir
set -ex

C4D_PLUGINS_DIRECTORY="$PREFIX/cinema4d/bin/plugins"
mkdir -p "$C4D_PLUGINS_DIRECTORY"

cp -a "$SRC_DIR"/. "$C4D_PLUGINS_DIRECTORY"/
