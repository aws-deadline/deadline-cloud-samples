#!/bin/env bash
set -xeuo pipefail

## Turn off "pip install" customizations from the conda build environment.
#
# This package incorporates Infinigen together with dependencies that conda-forge
# doesn't provide as of writing (notably bpy, the Blender Python module, and
# infinigen itself). To do this, pip install must work like normal, so this
# code turns off the conda build defaults for pip.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

## Set include/lib paths so the terrain C++ extension picks up conda-forge
## system deps (mesalib, glew, glm, zlib) at compile and link time.
export C_INCLUDE_PATH=$PREFIX/include:${C_INCLUDE_PATH:-}
export CPLUS_INCLUDE_PATH=$PREFIX/include:${CPLUS_INCLUDE_PATH:-}
export LIBRARY_PATH=$PREFIX/lib:${LIBRARY_PATH:-}
export LD_LIBRARY_PATH=$PREFIX/lib:${LD_LIBRARY_PATH:-}

## Limit parallel compilation to avoid OOM. Use one process per 3GB of free RAM.
free -g
export MAX_JOBS=$(free -g | awk '/^Mem:/{max_jobs=int($7/3); if (max_jobs == 0) {print 1} else {print max_jobs}}')

cd "$SRC_DIR/infinigen"

# Relax problematic upstream version pins so they resolve against conda-forge.
sed -i 's/"scikit-image<0.20.0"/"scikit-image"/' pyproject.toml
sed -i 's/"scikit-learn<1.4.0"/"scikit-learn"/' pyproject.toml
sed -i 's/"imageio<2.32.0"/"imageio"/' pyproject.toml
sed -i 's/"trimesh<3.23.0"/"trimesh"/' pyproject.toml

# Init git submodules needed for terrain compilation.
echo "openjd_status: Initializing git submodules"
git submodule update --init --recursive || echo "WARNING: submodule init failed, terrain may not compile"

# Compile terrain C++ libraries (CPU + optional CUDA when nvcc is available).
echo "openjd_status: Compiling terrain C++ libraries"
make terrain || echo "WARNING: terrain compilation failed, falling back to minimal"

# Install infinigen with terrain + visualization extras.
echo "openjd_status: Installing Infinigen with terrain"
pip install ".[terrain,vis]" --log "$SRC_DIR/pip_install_result.log" || {
    echo "Terrain install failed, trying minimal..."
    tail -50 "$SRC_DIR/pip_install_result.log"
    echo "openjd_status: Retrying with minimal install"
    INFINIGEN_MINIMAL_INSTALL=True pip install ".[vis]" --log "$SRC_DIR/pip_install_minimal.log" || {
        tail -50 "$SRC_DIR/pip_install_minimal.log"
        echo "openjd_status: Failed to install Infinigen"
        exit 1
    }
}

# Ensure setuptools/pkg_resources is available at runtime (landlab needs it).
# setuptools>=70 removed pkg_resources, so pin to <70.
pip install "setuptools<70"

# Patch gin_config's resource_reader: spec.origin is None for namespace
# packages in non-editable installs, which causes gin to fail to read its
# config files at runtime.
SITE_PKGS="$PREFIX/lib/python3.11/site-packages"
GIN_RR="$SITE_PKGS/gin/resource_reader.py"
if [ -f "$GIN_RR" ]; then
    echo "openjd_status: Patching gin resource_reader"
    python -c "
with open('$GIN_RR', 'r') as f:
    content = f.read()
patched = content.replace(
    'file_sys_path = spec.origin',
    '''file_sys_path = spec.origin
  if file_sys_path is None and spec.submodule_search_locations:
    file_sys_path = os.path.join(list(spec.submodule_search_locations)[0], '__init__.py')'''
)
with open('$GIN_RR', 'w') as f:
    f.write(patched)
print('Patched gin resource_reader.py')
"
fi

# Set environment variables for runtime.
mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/${PKG_NAME}-${PKG_VERSION}.json" << EOF
{
  "INFINIGEN_VERSION": "$PKG_VERSION"
}
EOF

echo "openjd_status: Finished infinigen package build"
