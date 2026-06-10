#!/bin/bash
# Host configuration script for Virtual Screening fleet.
# Runs as root at worker boot — installs AutoDock VINA and Open Babel system-wide.
set -euo pipefail

echo "=== Installing Virtual Screening Toolchain ==="

# Install AutoDock VINA 1.2.5 (static binary)
echo "Installing AutoDock VINA..."
VINA_URL="https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64"
curl -sL "${VINA_URL}" -o /usr/local/bin/vina
chmod 755 /usr/local/bin/vina

# Install Open Babel via micromamba (not in AL2023 repos)
echo "Installing micromamba and Open Babel..."
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local bin/micromamba
/usr/local/bin/micromamba create -p /opt/openbabel -c conda-forge openbabel -y --quiet

# Make the conda env world-readable/executable
chmod -R a+rX /opt/openbabel

# Create wrapper scripts that set the correct library path
cat > /usr/local/bin/obabel << 'WRAPPER'
#!/bin/bash
export LD_LIBRARY_PATH="/opt/openbabel/lib:${LD_LIBRARY_PATH}"
export BABEL_DATADIR="/opt/openbabel/share/openbabel/3.1.0"
exec /opt/openbabel/bin/obabel "$@"
WRAPPER
chmod 755 /usr/local/bin/obabel

# Ensure the shared libraries are findable system-wide too
echo "/opt/openbabel/lib" > /etc/ld.so.conf.d/openbabel.conf
ldconfig

# Verify installations
echo "Verifying installations..."
vina --version
obabel -V
python3 --version

echo "=== Virtual Screening Toolchain Installed ==="
