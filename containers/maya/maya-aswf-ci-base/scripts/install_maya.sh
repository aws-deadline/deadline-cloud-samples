#!/usr/bin/env bash
# Install Autodesk Maya from the customer-supplied Linux installer archive.
#
# Runs as root inside `docker build`, with the installers build context bind
# mounted read-only at /installers. Everything temporary is created under a
# mktemp directory and removed before the layer is committed.
#
# What this does, and why (see conda_recipes/maya-2027/recipe/build.sh for the
# proven Deadline Cloud recipe this is derived from):
#   1. Extracts only the pieces needed from the multi-GB archive: the Maya RPM
#      and the Autodesk Desktop Analytics (ADP) SDK; later streams one file
#      (ProductInformation.pit) out of the bundled MtoA payload.
#   2. Installs the Maya RPM with rpm, excluding the Examples and docs (falls
#      back to dnf if the RPM ever declares dependencies), then strips the
#      debug information Maya's libraries ship with (about 4.5 GB) - except
#      from the Autodesk licensing libraries, which are integrity-checked by
#      their loaders - and replaces Maya's bundled FreeType, which embeds a
#      copy of libpng that breaks PNG output under mayapy, with the system one.
#   3. Installs the ADP SDK into $MAYA_LOCATION/lib. Maya 2027 dlopen()s
#      AdpSDKCore.so during startup and exits with status 255, printing nothing,
#      when it is missing. MAYA_DISABLE_ADP / CIP / CER do not avoid this.
#   4. Configures legacy thin-client licensing, which is what Deadline Cloud
#      usage-based licensing and customer license servers expect. The Autodesk
#      Licensing / Identity Manager / FlexNet RPMs are deliberately NOT installed.
#   5. Creates /usr/local/bin launchers for maya, mayapy and Render.
set -euo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

MAYA_VERSION=${MAYA_VERSION:?MAYA_VERSION must be set}
INSTALLERS_DIR=${INSTALLERS_DIR:-/installers}
MAYA_LOCATION=${MAYA_LOCATION:-/usr/autodesk/maya${MAYA_VERSION}}

archive=$(find_installer "$INSTALLERS_DIR" "$(maya_installer_glob "$MAYA_VERSION")") || die \
    "No Maya installer found. Expected a file matching '$(maya_installer_glob "$MAYA_VERSION")'" \
    "directly in the installers directory or one subdirectory deep (for example" \
    "Maya${MAYA_VERSION}/Autodesk_Maya_${MAYA_VERSION}_Linux_64bit.tgz). Download it from" \
    "https://manage.autodesk.com and pass its directory with: build.sh --installers-dir DIR"

log "Installing Maya ${MAYA_VERSION} from $archive"

work=$(mktemp -d /tmp/maya-install.XXXXXX)
trap 'rm -rf "$work"' EXIT

# --- 1. Extract only what is needed -------------------------------------------
# Member names in the archive start with ./ so the patterns are matched with a
# leading wildcard. Each pass over the 4.6 GB archive takes about a minute. The
# MtoA payload (Packages/package.tgz, 600 MB) is only needed for one small file
# and is streamed in step 4, after the RPM has been installed and deleted, so
# that it never adds to the peak disk usage of this layer.
log "Extracting the Maya RPM and the ADP SDK from the archive"
tar -xzf "$archive" -C "$work" --wildcards \
    "*Packages/Maya${MAYA_VERSION}_64-*.x86_64.rpm" \
    "*Packages/AdpSdk/adp-desktop-sdk.zip"

rpm_file=$(find "$work" -name "Maya${MAYA_VERSION}_64-*.x86_64.rpm" -type f | head -n 1)
adp_zip=$(find "$work" -path "*AdpSdk/adp-desktop-sdk.zip" -type f | head -n 1)

[[ -n "$rpm_file" ]] || die "The archive does not contain Packages/Maya${MAYA_VERSION}_64-*.x86_64.rpm"
[[ -n "$adp_zip" ]] || die "The archive does not contain Packages/AdpSdk/adp-desktop-sdk.zip"

# --- 2. Install the RPM -------------------------------------------------------
# The Maya RPM declares no package dependencies (only /bin/sh), so it is
# installed with rpm directly, the way Autodesk's own setup program does
# (`rpm -Uh --force`). The system libraries Maya needs are installed by the
# Dockerfile and checked by scripts/verify.sh with ldd. --excludepath keeps the
# Examples (1.6 GB) and docs out of the layer instead of deleting them
# afterwards, which also lowers the peak disk usage of the build. Should a
# future Maya RPM declare dependencies, rpm fails and dnf is used to resolve
# them. The RPM's %post scriptlet calls the Autodesk licensing helper and edits
# a Synergy config file, both intentionally absent here, so rpm prints scriptlet
# warnings; they are harmless, and the result is checked afterwards rather than
# trusting the exit code.
pkg_name="Maya${MAYA_VERSION}_64"
log "Installing $(basename "$rpm_file") with rpm"
if ! rpm -Uvh --force \
        --excludepath "$MAYA_LOCATION/Examples" \
        --excludepath "$MAYA_LOCATION/docs" \
        "$rpm_file"; then
    warn "rpm reported errors (usually %post scriptlet warnings)"
fi
if ! rpm -q "$pkg_name" > /dev/null 2>&1; then
    log "Falling back to dnf install to resolve dependencies"
    dnf install -y "$rpm_file" || warn "dnf install did not succeed cleanly"
    dnf clean all
fi
rpm -q "$pkg_name" > /dev/null 2>&1 || die "$pkg_name is not installed after the RPM install attempt"
[[ -x "$MAYA_LOCATION/bin/maya.bin" ]] || die "$MAYA_LOCATION/bin/maya.bin is missing after installing the RPM"
rm -f "$rpm_file"

# The RPM's %post scriptlet normally creates this symlink; make sure it exists.
[[ -e "$MAYA_LOCATION/bin/maya" ]] || ln -s "maya${MAYA_VERSION}" "$MAYA_LOCATION/bin/maya"

# Content that is not needed on a render node (already excluded above unless
# the dnf fallback installed the package).
rm -rf "$MAYA_LOCATION/Examples" "$MAYA_LOCATION/docs"

# Several Maya libraries ship with full debug information (about 4.5 GB in
# total); see strip_debug_info in common.sh. The Autodesk licensing libraries
# are left untouched by it.
strip_debug_info "$MAYA_LOCATION"

# --- 2b. Replace Maya's bundled FreeType with the distribution's -----------------
# Maya's lib/libfreetype.so.6.20.1 has libpng compiled into it and EXPORTS the
# png_* symbols (372 of them). Maya's PNG image plug-in, bin/plug-ins/image/
# IMFPNG.so, links the system libpng16. Under `mayapy` the libraries end up in
# a load order where some png_* calls bind to FreeType's embedded copy and some
# to the system libpng16, so writing a PNG fails with "libpng error: Invalid
# IHDR data" followed by "double free or corruption" and a hung process. This
# breaks the maya-openjd adaptor, which renders through mayapy (the `Render`
# command happens to load in a benign order). The distribution's FreeType links
# libpng16 as a shared library and exports no png_* symbols, so Maya's copy is
# replaced by symlinks to it (the proven conda recipe, conda_recipes/maya-2027,
# ends up with the distribution's FreeType in lib/ as well). Every FT_* symbol
# the Maya, Qt and plug-in libraries import is checked to exist in the
# replacement, so an incompatible system FreeType fails the build instead of
# crashing a render.
log "Replacing the bundled FreeType in $MAYA_LOCATION/lib with the system library"
system_freetype=$(readlink -f /usr/lib64/libfreetype.so.6 2> /dev/null || true)
[[ -n "$system_freetype" && -f "$system_freetype" ]] \
    || die "/usr/lib64/libfreetype.so.6 is missing; the freetype package must be installed before Maya"
rm -f "$MAYA_LOCATION"/lib/libfreetype.so "$MAYA_LOCATION"/lib/libfreetype.so.6 "$MAYA_LOCATION"/lib/libfreetype.so.6.*
ln -s "$system_freetype" "$MAYA_LOCATION/lib/libfreetype.so.6"
ln -s libfreetype.so.6 "$MAYA_LOCATION/lib/libfreetype.so"
[[ -f "$MAYA_LOCATION/lib/libfreetype.so.6" && -f "$MAYA_LOCATION/lib/libfreetype.so" ]] \
    || die "$MAYA_LOCATION/lib/libfreetype.so.6 does not resolve to a file after relinking"
png_exports=$(nm -D --defined-only "$MAYA_LOCATION/lib/libfreetype.so.6" | grep -c ' png_' || true)
[[ "$png_exports" == 0 ]] \
    || die "$MAYA_LOCATION/lib/libfreetype.so.6 -> $system_freetype exports $png_exports png_* symbols; it would interpose libpng like Maya's own copy"
nm -D --defined-only "$system_freetype" | awk '$NF ~ /^FT_/ { print $NF }' | sort -u > "$work/ft_available"
missing_ft=""
while IFS= read -r -d '' lib; do
    is_elf_file "$lib" || continue
    readelf -d "$lib" 2> /dev/null | grep -q 'libfreetype' || continue
    needed=$({ nm -D --undefined-only "$lib" 2> /dev/null || true; } | awk '$NF ~ /^FT_/ { print $NF }' | sort -u \
        | comm -23 - "$work/ft_available" | tr '\n' ' ')
    [[ -n "$needed" ]] && missing_ft+="    $lib: $needed"$'\n'
done < <(find "$MAYA_LOCATION" -type f ! -name 'libfreetype.so*' \( -name '*.so*' -o -perm -u+x \) -print0)
if [[ -n "$missing_ft" ]]; then
    printf '%s' "$missing_ft" >&2
    die "$system_freetype lacks FreeType symbols that Maya libraries import; a newer freetype package is needed"
fi
log "libfreetype.so.6 -> $system_freetype ($(basename "$system_freetype")); no png_* exports, all imported FT_* symbols present"

# --- 3. Autodesk Desktop Analytics SDK ----------------------------------------
# The SDK drop also contains a newer libAdskIdentitySDK.so and its config,
# which replace the copies the RPM installed (Autodesk's own setup does the
# same). The list of files it installed is kept for scripts/verify.sh, whose
# `rpm -V` integrity check of the licensing libraries must not report them.
log "Installing the ADP SDK into $MAYA_LOCATION/lib"
unzip -q -o "$adp_zip" -d "$MAYA_LOCATION/lib"
mkdir -p "$(dirname "$ADP_SDK_MANIFEST")"
unzip -Z1 "$adp_zip" | grep -v '/$' | sed "s#^#$MAYA_LOCATION/lib/#" > "$ADP_SDK_MANIFEST"
# The SDK libraries find each other through an $ORIGIN rpath. Most of them ship
# with one already; add_rpath only rewrites a file that lacks it (libAdpIPC.so
# carries a build-machine path) and never touches anything else in lib/, so the
# RPM's licensing libraries stay exactly as shipped.
while IFS= read -r lib; do
    is_elf_file "$lib" && add_rpath "$lib" '$ORIGIN'
done < "$ADP_SDK_MANIFEST"
find "$MAYA_LOCATION/lib" -maxdepth 1 -name 'AdpSDK*.so*' | grep -q . \
    || die "AdpSDKCore.so not found in $MAYA_LOCATION/lib after unzipping the ADP SDK"

# --- 4. Thin-client licensing ---------------------------------------------------
# Maya needs a ProductInformation.pit file. The Maya RPM does not ship one (the
# Autodesk Licensing component normally installs it), but the MtoA payload
# bundled in the archive does. The payload is streamed through tar so that only
# the .pit file touches the disk. See the Autodesk article "Thin Client
# Licensing for Maya and MotionBuilder" and the Arnold support tip
# "error: (44) Product key not found".
log "Configuring thin-client licensing"
mkdir -p "$work/pit"
tar -xzf "$archive" -O --wildcards "*Packages/package.tgz" \
    | tar -xzf - -C "$work/pit" --wildcards '*bin/ProductInformation.pit'
pit_file=$(find "$work/pit" -name ProductInformation.pit -type f | head -n 1)
[[ -n "$pit_file" ]] || die "bin/ProductInformation.pit not found inside Packages/package.tgz of the Maya archive"
cp "$pit_file" "$MAYA_LOCATION/lib/ProductInformation.pit"

cat > "$MAYA_LOCATION/AdlmThinClientCustomEnv.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<ADLMCUSTOMENV VERSION="1.0.0.0">
   <PLATFORM OS="Linux">
       <KEY ID="ADLM_PIT_FILE_LOCATION">
       <!--Path to the ProductInformation.pit file-->
       <!--Default: /var/opt/Autodesk/Adlm/.config-->
       <STRING>$MAYA_LOCATION/lib</STRING>
       </KEY>
   </PLATFORM>
</ADLMCUSTOMENV>
EOF

# FlexNet writes lock files here; the RPM creates it world-writable, keep it so
# for containers that run as an arbitrary UID.
mkdir -p /var/flexlm && chmod 1777 /var/flexlm

# --- 5. Launchers ---------------------------------------------------------------
# The RPM scriptlet symlinks /usr/local/bin/maya and Render; replace them (and
# add mayapy) with exec wrappers, see install_launcher in common.sh.
install_launcher maya "$MAYA_LOCATION/bin/maya"
install_launcher mayapy "$MAYA_LOCATION/bin/mayapy"
install_launcher Render "$MAYA_LOCATION/bin/Render"

log "Maya ${MAYA_VERSION} installed in $MAYA_LOCATION ($(du -sh "$MAYA_LOCATION" | cut -f1))"
