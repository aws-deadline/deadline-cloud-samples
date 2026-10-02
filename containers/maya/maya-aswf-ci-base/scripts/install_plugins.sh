#!/usr/bin/env bash
# Install customer-supplied Maya modules, plug-ins and scripts.
#
# Runs as root inside `docker build`, with the plugins build context bind
# mounted read-only at /plugins (see build.sh --plugins-dir). Everything in it
# is copied to /opt/maya-plugins; .zip, .tar.gz, .tgz and other tar archives are
# extracted there instead of copied.
#
# The Dockerfile puts these locations on Maya's search paths, so the layout of
# the plugins directory decides how Maya finds things:
#
#   /opt/maya-plugins/            MAYA_MODULE_PATH      Maya module files (*.mod) at
#                                                       this level, each pointing at
#                                                       its module directory
#   /opt/maya-plugins/plug-ins/   MAYA_PLUG_IN_PATH     loose plug-ins (*.so, *.py)
#   /opt/maya-plugins/scripts/    MAYA_SCRIPT_PATH and  loose MEL and Python scripts,
#                                 PYTHONPATH            userSetup.mel / userSetup.py
#
# Maya does not search subdirectories of a module path for .mod files, so a
# warning is printed when the only .mod files end up below the top level.
#
# The script is a no-op (apart from creating the directories) when the plugins
# directory is missing, empty or only contains the .gitkeep placeholder.
set -euo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

PLUGINS_SRC=${PLUGINS_SRC:-/plugins}
PLUGINS_DST=${PLUGINS_DST:-/opt/maya-plugins}

mkdir -p "$PLUGINS_DST/plug-ins" "$PLUGINS_DST/scripts"

shopt -s nullglob dotglob
entries=()
for entry in "$PLUGINS_SRC"/*; do
    case "$(basename "$entry")" in
        .gitkeep | .DS_Store) continue ;;
    esac
    entries+=("$entry")
done
shopt -u nullglob dotglob

if [[ ${#entries[@]} -eq 0 ]]; then
    log "No plugins supplied in $PLUGINS_SRC; $PLUGINS_DST stays empty"
    chmod -R a+rX "$PLUGINS_DST"
    exit 0
fi

installed=()
for entry in "${entries[@]}"; do
    name=$(basename "$entry")
    if [[ -f "$entry" ]]; then
        case "$name" in
            *.zip)
                log "Extracting $name"
                unzip -q -o "$entry" -d "$PLUGINS_DST"
                installed+=("$name (extracted)")
                continue
                ;;
            *.tar.gz | *.tgz | *.tar.xz | *.tar.bz2 | *.tar)
                log "Extracting $name"
                tar -xf "$entry" -C "$PLUGINS_DST"
                installed+=("$name (extracted)")
                continue
                ;;
        esac
    fi
    log "Copying $name"
    cp -a "$entry" "$PLUGINS_DST/"
    installed+=("$name")
done

chmod -R a+rX "$PLUGINS_DST"

log "Installed into $PLUGINS_DST:"
printf '    %s\n' "${installed[@]}"

log "Contents of $PLUGINS_DST:"
find "$PLUGINS_DST" -mindepth 1 -maxdepth 2 | sort | sed 's/^/    /'

# Module files are only picked up at the top level of a MAYA_MODULE_PATH entry.
shopt -s nullglob
top_level_mods=("$PLUGINS_DST"/*.mod)
shopt -u nullglob
nested_mods=$(find "$PLUGINS_DST" -mindepth 2 -name '*.mod' -type f | sort)
if [[ ${#top_level_mods[@]} -gt 0 ]]; then
    log "Maya module files found: ${top_level_mods[*]##*/}"
fi
if [[ -n "$nested_mods" ]]; then
    warn "Module files were found below the top level of $PLUGINS_DST, where Maya does not look for them:"
    sed 's/^/    /' <<< "$nested_mods" >&2
    warn "Move each .mod file to the top level of the plugins directory and point it at its module" \
        "directory, for example: + myModule 1.0 ./myModule"
fi
