#!/bin/bash
# Host configuration script for GROMACS Molecular Dynamics fleet.
# Runs as root at worker boot — installs GROMACS system-wide via micromamba.
set -euo pipefail

echo "=== Installing GROMACS Molecular Dynamics Toolchain ==="

# Install micromamba
echo "Installing micromamba..."
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local bin/micromamba

# Install GROMACS from conda-forge (includes thread-MPI support)
echo "Installing GROMACS via conda-forge..."
/usr/local/bin/micromamba create -p /opt/gromacs -c conda-forge gromacs -y --quiet

# Make the conda env world-readable/executable
chmod -R a+rX /opt/gromacs

# Create wrapper script that sets the correct library path and GROMACS data dirs
cat > /usr/local/bin/gmx << 'WRAPPER'
#!/bin/bash
export LD_LIBRARY_PATH="/opt/gromacs/lib:${LD_LIBRARY_PATH:-}"
export GMXDATA="/opt/gromacs/share/gromacs"
export GMX_MAXBACKUP=-1
exec /opt/gromacs/bin/gmx "$@"
WRAPPER
chmod 755 /usr/local/bin/gmx

# Ensure the shared libraries are findable system-wide
echo "/opt/gromacs/lib" > /etc/ld.so.conf.d/gromacs.conf
ldconfig

# Verify installation
echo "Verifying installation..."
gmx --version

echo "=== GROMACS Molecular Dynamics Toolchain Installed ==="
