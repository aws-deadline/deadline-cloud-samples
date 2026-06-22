#!/bin/sh
set -xeuo pipefail

# Repackage the pre-built cx_Freeze Linux launcher release into the conda prefix.
mkdir -p $PREFIX/opt/ayon-launcher
cp -r ayon app_launcher common dependencies lib share shim vendor version.py LICENSE $PREFIX/opt/ayon-launcher/

# Expose the launcher on PATH.
mkdir -p $PREFIX/bin
ln -sf ../opt/ayon-launcher/ayon $PREFIX/bin/ayon

# Activation script to set the runtime environment variables.
mkdir -p $PREFIX/etc/conda/activate.d
cat > $PREFIX/etc/conda/activate.d/ayon-launcher.sh << 'ACTIVATE'
#!/bin/bash
export AYON_LAUNCHER_DIR="$CONDA_PREFIX/opt/ayon-launcher"
export AYON_HEADLESS_MODE=1
ACTIVATE
chmod +x $PREFIX/etc/conda/activate.d/ayon-launcher.sh
