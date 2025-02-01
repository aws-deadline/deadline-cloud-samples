#!/bin/sh
set -xeuo pipefail

# The location within $PREFIX where rsmb will be installed
mkdir -p $PREFIX/opt
cp -r $SRC_DIR/rsmb $PREFIX/opt/


# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
robocopy "$PREFIX/opt/rsmb" "$PREFIX/opt/aftereffects/Support Files/Plug-Ins" *.aex
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
del "$PREFIX\opt\aftereffects\Support Files\Plug-ins\RSMB_64.aex"
del "$PREFIX\opt\aftereffects\Support Files\Plug-ins\RSMBPro_64.aex"
del "$PREFIX\opt\aftereffects\Support Files\Plug-ins\RSMBProVectorInput_64.aex"
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
