#!/bin/sh

# Echo all the commands so debugging from log output is simpler
set -x
# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
MAYA_VERSION=${PKG_VERSION%.*}
# The location within $PREFIX where the RPM file extracts Maya
AUTODESK_ROOT="usr/autodesk"
MAYA_ROOT="$AUTODESK_ROOT/maya$MAYA_VERSION"
INSTALL_DIR="$PREFIX/$MAYA_ROOT"

cd $PREFIX

# Extract the Maya RPM
rpm2cpio "$SRC_DIR/installer/Packages"/Maya${MAYA_VERSION}_64-$PKG_VERSION-*.x86_64.rpm | cpio -idm

# Remove examples, they're not needed on the farm
rm -r "$MAYA_ROOT"/Examples

# Maya needs this symlink that rpm2cpio did not create
ln -r -s "$INSTALL_DIR/bin/maya$MAYA_VERSION" "$INSTALL_DIR/bin/maya"

# Install the Autodesk Desktop Analytics (ADP) SDK.
#
# Maya 2027 dlopen()s AdpSDKCore.so during startup and exits with status 255, printing
# nothing, if it is missing. Earlier Maya releases tolerated its absence. The SDK is not
# part of the Maya RPM; the installer ships it as a separate package that Autodesk's own
# setup program installs. $MAYA_LOCATION/lib is one of the paths Maya probes for it.
#
# The MAYA_DISABLE_ADP / MAYA_DISABLE_CIP / MAYA_DISABLE_CER environment variables do NOT
# avoid this: they suppress reporting after the library loads, so the library must be
# present regardless. They are still set in env_vars.d below so nothing is transmitted.
unzip -q -o "$SRC_DIR/installer/Packages/AdpSdk/adp-desktop-sdk.zip" -d "$INSTALL_DIR/lib"

# Give the ADP libraries an rpath so they can find each other. The generic rpath pass
# further down only sets an RPATH on files that have none, so set these explicitly here
# to guarantee $ORIGIN regardless of what the SDK ships with. Matched by pattern rather
# than by name so that a renamed or added library in a future SDK drop does not fail the
# build.
find "$INSTALL_DIR/lib" -maxdepth 1 -type f \( -name '*Adp*.so' -o -name '*Adsk*.so' \) \
    -exec patchelf --set-rpath '$ORIGIN' {} +

# Install dependencies not available on Deadline Cloud service-managed fleets
# from the system package manager, dnf.
mkdir -p "$SRC_DIR/download"
cd "$SRC_DIR/download"
dnf download --resolve -y freetype alsa-lib fontconfig harfbuzz libbrotli graphite2 \
    libxkbfile xcb-util-wm xcb-util-keysyms libxkbcommon-x11 \
    libva libvdpau pciutils-libs \
    openjpeg2 libatomic

for RPM_FILE in *.rpm; do
    rpm2cpio "$RPM_FILE" | cpio -idm
done

# Use patchelf to add relative RPATHs to the .so files where necessary.
# This is to follow the recommendation of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.

# The Maya RPM has libraries in both $MAYA_ROOT/lib and $MAYA_ROOT/lib/el9
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/site-packages/*.so
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/site-packages/*/*.so
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/lib-dynload/*.so
patchelf --add-rpath '$ORIGIN/../../el9' "$INSTALL_DIR"/lib/python*/lib-dynload/*.so

# Copy the .so libraries to the Maya lib directory, adding to their RPATHs so they see each other
find . -type f,l -iname "*.so.*" -exec patchelf --add-rpath '$ORIGIN/.' {} \;
find . -type f,l -iname "*.so.*" -exec cp -P {} "$INSTALL_DIR/lib/" \;

# Add RPATH for libraries in $MAYA_ROOT/lib that lack one, allowing them to
# find dependencies in their own directory
for file in "$INSTALL_DIR/lib"/*; do
    if file "$file" | grep -q "ELF"; then
        if [[ -z "$(patchelf --print-rpath "$file")" ]]; then
            patchelf --set-rpath "\$ORIGIN" "$file"
        fi
    fi
done

# Create symlinks
mkdir -p $PREFIX/bin
ln -r -s $PREFIX/$MAYA_ROOT/bin/maya$MAYA_VERSION $PREFIX/bin/maya$MAYA_VERSION
ln -r -s $PREFIX/$MAYA_ROOT/bin/maya$MAYA_VERSION $PREFIX/bin/maya
ln -r -s $PREFIX/$MAYA_ROOT/bin/mayapy.bin $PREFIX/bin/mayapy.bin
ln -r -s $PREFIX/$MAYA_ROOT/bin/Render $PREFIX/bin/Render

# Expose mayapy through a wrapper script instead of a symlink.
#
# Autodesk's bin/mayapy looks for Maya's libraries in ../lib relative to the directory it
# was invoked from, so exec'ing a symlink in $PREFIX/bin sends the lookup to $PREFIX/lib,
# where mayapy can silently load another package's libpython3.13 (the maya-openjd adaptor
# stack installs one) and crash. Exec'ing the real path keeps the lookup inside the
# installation.
cat > $PREFIX/bin/mayapy <<EOF
#!/bin/sh
exec "$PREFIX/$MAYA_ROOT/bin/mayapy" "\$@"
EOF
chmod +x $PREFIX/bin/mayapy

# Use thin client licensing configuration to use the ProductInformation.pit from the Arnold installation.
#
# To learn more, see the Autodesk article "Thin Client Licensing for Maya and MotionBuilder"
# at https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/2zqRBCuGDrcPZDzULJQ27p.html
# and the Arnold support tip "error: (44) Product key not found"
# at https://arnoldsupport.com/2022/02/02/error-44-product-key-not-found/.

# In Maya 2027 the Arnold payload ships as Packages/package.tgz, where earlier
# releases used Packages/package.zip.
tar -xzf "$SRC_DIR/installer/Packages/package.tgz" -C "$INSTALL_DIR/lib" \
    --strip-components=1 bin/ProductInformation.pit

cat <<EOF > "$INSTALL_DIR"/AdlmThinClientCustomEnv.xml
<?xml version="1.0" encoding="utf-8"?>
<ADLMCUSTOMENV VERSION="1.0.0.0">
   <PLATFORM OS="Linux">
       <KEY ID="ADLM_PIT_FILE_LOCATION">
       <!--Path to the ProductInformation.pit file-->
       <!--Default: /var/opt/Autodesk/Adlm/.config-->
       <STRING>$INSTALL_DIR/lib</STRING>
       </KEY>
   </PLATFORM>
</ADLMCUSTOMENV>
EOF

# Set environment variables using the JSON env_vars.d mechanism.
# See https://rattler-build.prefix.dev/latest/special_files/ for details.
# This is more portable than activation scripts and works with pixi trampolines.
mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json" << EOF
{
  "MAYA_LOCATION": "$PREFIX/$MAYA_ROOT",
  "MAYA_VERSION": "$MAYA_VERSION",
  "MAYA_NO_HOME": "1",
  "MAYA_MODULE_PATH": "$PREFIX/usr/autodesk/maya$MAYA_VERSION/modules:$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION:$PREFIX/usr/autodesk/modules/maya",
  "AUTODESK_ADLM_THINCLIENT_ENV": "$INSTALL_DIR/AdlmThinClientCustomEnv.xml",
  "MAYA_LEGACY_THINCLIENT": "1",
  "MAYA_DISABLE_ADP": "1",
  "MAYA_DISABLE_CIP": "1",
  "MAYA_DISABLE_CER": "1"
}
EOF

# --- Plugin Sync ---
# Copies the plugin delivery scripts into the conda activate.d/deactivate.d
# directories. These run AFTER the main Maya env vars are set via env_vars.d.
#
# See zzz-maya-plugin-sync-activate.sh for the full implementation.
mkdir -p "$PREFIX/etc/conda/activate.d"
cp $RECIPE_DIR/zzz-maya-plugin-sync-activate.sh \
    $PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cp $RECIPE_DIR/zzz-maya-plugin-sync-deactivate.sh \
    $PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh
