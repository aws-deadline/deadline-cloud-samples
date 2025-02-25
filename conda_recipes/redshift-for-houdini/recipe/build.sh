# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
REDSHIFT_VERSION=$PKG_VERSION
REDSHIFT_LOCATION=${PREFIX}/redshift

# The conda-build environment is configured for packaging one pypi package into one conda package.
# We turn off the following defaults for the below pip install.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

mv $SRC_DIR/redshift $PREFIX/

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

# need to set all the environment variables needed for a custom install: https://help.maxon.net/r3d/cinema/en-us/index.html#html/Custom+Install+Locations.html#title-text
cat > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh" <<EOL
export RED_VERSION=$REDSHIFT_VERSION
export RED_LOCATION="$REDSHIFT_LOCATION"

export REDSHIFT_COREDATAPATH=$REDSHIFT_LOCATION
export REDSHIFT_LOCALDATAPATH=$REDSHIFT_LOCATION
export REDSHIFT_PROCEDURALSPATH=$REDSHIFT_LOCATION/Procedurals
export REDSHIFT_PREFSPATH=$REDSHIFT_LOCATION/preferences.xml
export REDSHIFT_LICENSEPATH=$REDSHIFT_LOCATION

export HOUDINI_DSO_ERROR=2

export EXACT_HOUDINI_VERSION="20.5.487"
if [[ -z "\${HOUDINI_VERSION-}" ]]; then
echo "Not empty???"
	if [[ ! \$HOUDINI_VERSION =~ [0-9]+\.[0-9]+\.[0-9]+ ]]; then
		EXACT_HOUDINI_VERSION=\$HOUDINI_VERSION
	else
		MAX=$(find ${REDSHIFT_LOCATION} -maxdepth 1 -name '\$HOUDINI_VERSION\.[1-9]*' |
			sed 's/\$HOUDINI_VERSION\.\([0-9]*\)/\1/' |
			sort -n |
			tail -n 1)
		EXACT_HOUDINI_VERSION="\$HOUDINI_VERSION.\$MAX"
	fi
fi
echo Configuring Redshift for Houdini \$EXACT_HOUDINI_VERSION

export HOUDINI_PATH="$REDSHIFT_LOCATION/redshift4houdini/\${EXACT_HOUDINI_VERSION};\${HOUDINI_PATH-&}"
EOL
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh" <<EOL
unset RED_VERSION
unset RED_LOCATION

unset REDSHIFT_COREDATAPATH
unset REDSHIFT_LOCALDATAPATH
unset REDSHIFT_PROCEDURALSPATH
unset REDSHIFT_PREFSPATH
unset REDSHIFT_LICENSEPATH

unset HOUDINI_DSO_ERROR
export HOUDINI_PATH="\${HOUDINI_PATH/$REDSHIFT_LOCATION/redshift4houdini/\${EXACT_HOUDINI_VERSION};/}"
unset EXACT_HOUDINI_VERSION
EOL
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

