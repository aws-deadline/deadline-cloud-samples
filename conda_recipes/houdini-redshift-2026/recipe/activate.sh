#!/bin/sh

# Script to set environment variables during activation
# Environment variables are based on what is needed for portable Redshift installations
# https://help.maxon.net/r3d/houdini/en-us/Content/html/Custom+Install+Locations.html

export REDSHIFT_COREDATAPATH="$CONDA_PREFIX/opt/redshift"
export REDSHIFT_LOCALDATAPATH="$REDSHIFT_COREDATAPATH/redshift_local_data"
export REDSHIFT_PROCEDURALSPATH="$REDSHIFT_COREDATAPATH/procedurals"
export REDSHIFT_PREFSPATH="$REDSHIFT_LOCALDATAPATH/preferences.xml"
export HOUDINI_DSO_ERROR=2

# Redshift plugins for Houdini are versioned to match the exact patch release
# of the Houdini version. If there is no exact match this package will point
# to the latest plugin version for either the matching MAJOR.MINOR Houdini version.
# Using a plugin version that doesn't match the Houdini version could cause
# instability and failures.

HOU_VERSION_OUTPUT=$(houdini --version 2>/dev/null)
if [ $? -eq 0 ] && [[ "$HOU_VERSION_OUTPUT" =~ Houdini\ FX\ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
  HOU_VERSION="${BASH_REMATCH[1]}"

  # Get all available plugin versions
  AVAILABLE_VERSIONS=$(find "$REDSHIFT_COREDATAPATH/redshift4houdini/" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")

  # Check for exact match first
  if echo "$AVAILABLE_VERSIONS" | grep -q "^$HOU_VERSION$"; then
    export RS_PLUGIN_VERSION="$HOU_VERSION"
  else
    # Extract major.minor from HOU_VERSION (e.g. 21.0 from 21.0.440)
    HOU_MAJOR_MINOR=${HOU_VERSION%.*}
    
    # Find the latest patch release for a matching major.minor version
    MATCHING_VERSION=$(echo "$AVAILABLE_VERSIONS" | grep "^$HOU_MAJOR_MINOR" | sort -V | tail -1)

    if [ -n "$MATCHING_VERSION" ]; then
      export RS_PLUGIN_VERSION="$MATCHING_VERSION"
      echo "Warning: No exact match Redshift plugin found for Houdini $HOU_VERSION, using $RS_PLUGIN_VERSION instead"
    else
      # If no matching major.minor version is found fail to load the package
      echo "Error: No matching Redshift plugin found for Houdini $HOU_MAJOR_MINOR in $AVAILABLE_VERSIONS"
      exit 1
    fi
  fi
else
  echo "Error: Could not determine Houdini version using 'houdini --version'"
  exit 1
fi

# PXR_PLUGINPATH_NAME should be able to be set for the Solaris plugin in the Redshift package file.
# https://help.maxon.net/r3d/houdini/en-us/Content/html/Houdini+Plugin+Configuration.html
# However, there's a known issue where that doesn't work on Linux.
# Instead we can set it outside the package file as part of the environment as the suggested workaround.

internal_package_add_to_search_path () {
    # Add a path to a new or existing environment variable.
    # Usage: internal_package_add_to_search_path VAR_NAME /search/path/value
    eval "CURRENT_VALUE=\${$1:-}"
    if [ "$CURRENT_VALUE" = "" ]; then
        eval "export \"$1=\$2\""
    else
        NEW_VALUE="$CURRENT_VALUE:$2"
        eval "export \"$1=\$NEW_VALUE\""
    fi
}

internal_package_add_to_search_path PXR_PLUGINPATH_NAME "$REDSHIFT_COREDATAPATH/redshift4solaris/$RS_PLUGIN_VERSION"

unset -f internal_package_add_to_search_path
