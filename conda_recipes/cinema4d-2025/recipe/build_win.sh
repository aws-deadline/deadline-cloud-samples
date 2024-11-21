# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
CINEMA_4D_VERSION=${PKG_VERSION%.*}

# The conda-build environment is configured for packaging one pypi package into one conda package.
# We turn off the following defaults for the below pip install.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

# Move all the files into the prefix. Use cmd to move the files as it works
# more reliably with permissions and locking.
cmd <<EOF
move $SRC_DIR\\cinema4d $PREFIX\\
EOF

# Currently, the cinema4d-openjd command from deadline-cloud-for-cinema4d
# requires that pywin32 be installed inside Cinema4D's python.
"$PREFIX\\cinema4d\\resource\\modules\\python\\libs\\win64\\python.exe" -m ensurepip
"$PREFIX\\cinema4d\\resource\\modules\\python\\libs\\win64\\python.exe" -m pip install pywin32

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export C4D_VERSION=$CINEMA_4D_VERSION
export C4D_LOCATION="$PREFIX\\cinema4d"
export CINEMA4D_ADAPTOR_COMMANDLINE_EXE="$PREFIX\\cinema4d\\Commandline.exe"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "C4D_VERSION=$CINEMA_4D_VERSION"
set "C4D_LOCATION=$PREFIX\cinema4d"
set "CINEMA4D_ADAPTOR_COMMANDLINE_EXE=$PREFIX\cinema4d\Commandline.exe"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset C4D_VERSION
unset C4D_LOCATION
unset CINEMA4D_ADAPTOR_COMMANDLINE_EXE
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set C4D_VERSION=
set C4D_LOCATION=
set CINEMA4D_ADAPTOR_COMMANDLINE_EXE=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"