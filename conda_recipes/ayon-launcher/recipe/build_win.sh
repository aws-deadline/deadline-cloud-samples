#!/bin/sh
set -xeuo pipefail

# Repackage the pre-built Windows launcher release into the conda prefix.
mkdir -p $PREFIX/opt/ayon-launcher
cp -r ayon.exe ayon_console.exe common dependencies lib share shim vendor version.py LICENSE $PREFIX/opt/ayon-launcher/
cp *.dll $PREFIX/opt/ayon-launcher/ || true

# bash wrapper so the launcher is callable from the bash-based activation used on Windows workers.
mkdir -p $PREFIX/Scripts
cat > $PREFIX/Scripts/ayon << 'WRAPPER'
#!/bin/bash
exec "$CONDA_PREFIX/opt/ayon-launcher/ayon_console.exe" "$@"
WRAPPER
chmod +x $PREFIX/Scripts/ayon

# Activation scripts to set the runtime environment variables.
# The Deadline Cloud sample queue environments use bash to activate environments
# on Windows, so we produce both .sh and .bat files.
mkdir -p $PREFIX/etc/conda/activate.d
cat > $PREFIX/etc/conda/activate.d/ayon-launcher.sh << 'ACTIVATE'
#!/bin/bash
export AYON_LAUNCHER_DIR="$CONDA_PREFIX/opt/ayon-launcher"
export AYON_HEADLESS_MODE=1
ACTIVATE
chmod +x $PREFIX/etc/conda/activate.d/ayon-launcher.sh
printf '@echo off\r\nset "AYON_LAUNCHER_DIR=%%CONDA_PREFIX%%\\opt\\ayon-launcher"\r\nset "AYON_HEADLESS_MODE=1"\r\n' > $PREFIX/etc/conda/activate.d/ayon-launcher.bat
