#!/bin/sh
set -xeuo pipefail

MAYA_VERSION=2026
INSTALLER_NAME="OctaneRender_Studio+_2026.4_for_Maya_v25.20.run"
INSTALLER_SOURCE="$SRC_DIR/installer/$INSTALLER_NAME"
EXTRACT_DIR="$SRC_DIR/octane-extracted"
INSTALLER_COPY="$EXTRACT_DIR/$INSTALLER_NAME"
OCTANE_ROOT="$PREFIX/usr/otoy/ofm_vr"

mkdir -p "$EXTRACT_DIR"
cp "$INSTALLER_SOURCE" "$INSTALLER_COPY"
cd "$EXTRACT_DIR"
chmod u+x "$INSTALLER_COPY"
"./$INSTALLER_NAME" --extract

PAYLOAD="$EXTRACT_DIR/OctaneForMaya/install"
mkdir -p "$OCTANE_ROOT"
cp -a "$PAYLOAD/lib" "$OCTANE_ROOT/"
cp -a "$PAYLOAD/rendererDesc" "$OCTANE_ROOT/"
cp -a "$PAYLOAD/NETemplates" "$OCTANE_ROOT/"
cp -a "$PAYLOAD/presets" "$OCTANE_ROOT/"
cp -a "$PAYLOAD/$MAYA_VERSION" "$OCTANE_ROOT/"

PLUGIN_DIR="$OCTANE_ROOT/$MAYA_VERSION/plug-ins"
patchelf --add-rpath '$ORIGIN/../../lib' "$PLUGIN_DIR/OctanePlugin.so"

# Reproduce the library links that the OTOY installer creates.
MAYA_LIB_DIR="$PREFIX/usr/autodesk/maya$MAYA_VERSION/lib"
mkdir -p "$MAYA_LIB_DIR"
for library in "$OCTANE_ROOT"/lib/*; do
    library_name="$(basename "$library")"
    ln -sf "../../lib/$library_name" "$PLUGIN_DIR/$library_name"
    ln -sf "../../../otoy/ofm_vr/lib/$library_name" "$MAYA_LIB_DIR/$library_name"
done

MODULE_DIR="$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
mkdir -p "$MODULE_DIR"
cat <<EOF > "$MODULE_DIR/octane.mod"
+ MAYAVERSION:$MAYA_VERSION OctaneRender - $OCTANE_ROOT/$MAYA_VERSION
OCTANERENDER_LOCATION:=
OCTANE_LIB_PATH:=../lib
PATH+:=../lib
MAYA_CUSTOM_TEMPLATE_PATH+:=../NETemplates
MAYA_PRESET_PATH+:=../presets
MAYA_RENDER_DESC_PATH+:=../rendererDesc
EOF

MAYA_RENDERER_DESC_DIR="$PREFIX/usr/autodesk/maya$MAYA_VERSION/bin/rendererDesc"
mkdir -p "$MAYA_RENDERER_DESC_DIR"
cp "$OCTANE_ROOT/rendererDesc/octaneRenderer.xml" "$MAYA_RENDERER_DESC_DIR/"
