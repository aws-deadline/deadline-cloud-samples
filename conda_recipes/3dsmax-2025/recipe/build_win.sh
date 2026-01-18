#!/bin/sh

set -xeuo pipefail

# The version without the update number
MAX_VERSION=${PKG_VERSION%.*}
AUTODESK_ROOT="Autodesk"
INSTALL_DIR="$PREFIX/$AUTODESK_ROOT/3ds Max $MAX_VERSION"

mkdir -p "$PREFIX/$AUTODESK_ROOT"

# Locate the extracted 3ds Max root (zip contents may include an extra top-level folder).
SRC_ROOT="$SRC_DIR/3dsmax"
if [ ! -f "$SRC_ROOT/3dsmax.exe" ]; then
    FOUND_PATH=$(find "$SRC_DIR" -maxdepth 4 -type f -name "3dsmax.exe" | head -n 1 || true)
    if [ -n "$FOUND_PATH" ]; then
        SRC_ROOT=$(dirname "$FOUND_PATH")
    fi
fi

# Copy the extracted files into the install location (robust against read-only flags and file/dir collisions).
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cmd <<EOF
setlocal
rem Use robocopy without ACL/owner copying to avoid access denied; accept codes 0-7 as success.
robocopy "$(cygpath -w "$SRC_ROOT")" "$(cygpath -w "$INSTALL_DIR")" /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL >nul
set RC=%ERRORLEVEL%
echo Robocopy exit code: %RC%
if %RC% GEQ 8 exit /b %RC%
exit /b 0
EOF

# The conda-build environment sets pip to offline/no-deps by default; allow installs for 3ds Max Python.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

# Ensure 3ds Max's bundled Python has pip and pywin32 available for automation.
"$INSTALL_DIR\\Python\\python.exe" -m ensurepip
"$INSTALL_DIR\\Python\\python.exe" -m pip install pywin32
"$INSTALL_DIR\\Python\\python.exe" -m pip install deadline-cloud-for-3ds-max --upgrade

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so always produce both .bat and .sh files.

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export ADSK_3DSMAX_VERSION=$MAX_VERSION
export ADSK_3DSMAX_LOCATION="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION"
export ADSK_3DSMAX_PYTHON="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python/python.exe"
export ADSK_3DSMAX_BATCH_EXE="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/3dsmaxbatch.exe"
export ADSK_3DSMAX_EXECUTABLE="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/3dsmaxbatch.exe"
export ADSK_3DSMAX_ROOT="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION"
export ADSK_3DSMAX_PLUGINS_ADDON_DIR="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Plugins"
export ADSK_APPLICATION_PLUGINS="\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Plugins"
export PATH="\$(cygpath "\$CONDA_PREFIX/bin"):\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION"):\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python"):\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python/Scripts"):\$PATH"
export PYTHONPATH="\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python"):\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python/Scripts"):\$PYTHONPATH"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "ADSK_3DSMAX_VERSION=$MAX_VERSION"
set "ADSK_3DSMAX_LOCATION=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION"
set "ADSK_3DSMAX_PYTHON=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python\\python.exe"
set "ADSK_3DSMAX_BATCH_EXE=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\3dsmaxbatch.exe"
set "ADSK_3DSMAX_EXECUTABLE=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\3dsmaxbatch.exe"
set "ADSK_3DSMAX_ROOT=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION"
set "ADSK_3DSMAX_PLUGINS_ADDON_DIR=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Plugins"
set "ADSK_APPLICATION_PLUGINS=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Plugins"
set "3DSMAX_EXECUTABLE=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\3dsmaxbatch.exe"
set "PATH=%CONDA_PREFIX%\\bin;%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION;%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python;%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python\\Scripts;%PATH%"
set "PYTHONPATH=%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python;%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python\\Scripts;%PYTHONPATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export PATH="\${PATH/\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python/Scripts"):/}"
export PATH="\${PATH/\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python"):/}"
export PATH="\${PATH/\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION"):/}"
export PYTHONPATH="\${PYTHONPATH/\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python/Scripts"):/}"
export PYTHONPATH="\${PYTHONPATH/\$(cygpath "\$CONDA_PREFIX/Autodesk/3ds Max $MAX_VERSION/Python"):/}"
unset ADSK_3DSMAX_EXECUTABLE
unset ADSK_3DSMAX_BATCH_EXE
unset ADSK_3DSMAX_PYTHON
unset ADSK_3DSMAX_LOCATION
unset ADSK_3DSMAX_VERSION
unset ADSK_3DSMAX_ROOT
unset ADSK_3DSMAX_PLUGINS_ADDON_DIR
unset ADSK_APPLICATION_PLUGINS
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION;=%"
set "PYTHONPATH=%PYTHONPATH:%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python;=%"
set "PYTHONPATH=%PYTHONPATH:%CONDA_PREFIX%\\Autodesk\\3ds Max $MAX_VERSION\\Python\\Scripts;=%"
set 3DSMAX_EXECUTABLE=
set ADSK_3DSMAX_BATCH_EXE=
set ADSK_3DSMAX_EXECUTABLE=
set ADSK_3DSMAX_ROOT=
set ADSK_3DSMAX_PLUGINS_ADDON_DIR=
set ADSK_APPLICATION_PLUGINS=
set ADSK_3DSMAX_PYTHON=
set ADSK_3DSMAX_LOCATION=
set ADSK_3DSMAX_VERSION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"