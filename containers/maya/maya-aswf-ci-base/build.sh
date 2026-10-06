#!/usr/bin/env bash
# Build (and optionally push) the Maya container image.
#
# The Dockerfile reads the installers from a named build context that is bind
# mounted during the build, so this script checks that the installers for the
# requested components exist BEFORE starting docker, and prints which file will
# be used for each component. See README.md for where to download them.
set -euo pipefail

SAMPLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=scripts/common.sh
source "$SAMPLE_DIR/scripts/common.sh"

MAYA_VERSION=2027
VFX_PLATFORM_YEAR=2026
ADAPTOR_VERSION=0.15.13
INSTALLERS_DIR=""
PLUGINS_DIR="$SAMPLE_DIR/plugins"
WITH_ARNOLD=0
WITH_VRAY=0
WITH_REDSHIFT=0
TAG=""
PUSH_URI=""
NO_CACHE=0
DRY_RUN=0

usage() {
    cat <<EOF
Usage: $(basename "$0") --installers-dir DIR [options]

Builds the Maya ${MAYA_VERSION} image for AWS Deadline Cloud from installers you
downloaded yourself (Autodesk Account, Chaos, Maxon). Nothing from DIR is copied
into the image layers; it is bind mounted only while each component installs.

Options:
  --installers-dir DIR     Directory with the installers (required unless --dry-run).
                           Files are found directly in DIR or one subdirectory deep.
  --plugins-dir DIR        Maya modules / plug-ins / scripts to bake in
                           (default: ./plugins, which only holds .gitkeep).
  --arnold                 Install Arnold for Maya (MtoA).
  --vray                   Install V-Ray for Maya.
  --redshift               Install Redshift and its Maya plug-in.
  --all-renderers          Same as --arnold --vray --redshift.
  --maya-version VER       Maya version (default: ${MAYA_VERSION}).
  --vfx-platform-year YEAR aswf/ci-base tag to build on (default: ${VFX_PLATFORM_YEAR}).
  --adaptor-version VER    deadline-cloud-for-maya version (default: ${ADAPTOR_VERSION}).
  --tag NAME:TAG           Image tag (default: maya-aswf:<maya version><-arnold><-vray><-redshift>).
  --push ECR_REPO_URI      After building, log in to ECR, tag the image as
                           ECR_REPO_URI:<tag> and push it.
  --no-cache               Pass --no-cache to docker build.
  --dry-run                Print the docker command and exit without building.
  -h, --help               Show this help.

Expected installer file names (any Maya version is substituted for ${MAYA_VERSION}):
  Maya      $(maya_installer_glob "$MAYA_VERSION")      from Autodesk Account; required
  MtoA      $(mtoa_installer_glob "$MAYA_VERSION")                from Autodesk Account; optional,
            otherwise the MtoA bundled inside the Maya archive is installed
  V-Ray     $(vray_installer_glob "$MAYA_VERSION")                       from Chaos; Linux build, no extension
  Redshift  $(redshift_installer_glob)                from Maxon

Examples:
  $(basename "$0") --installers-dir ~/installers
  $(basename "$0") --installers-dir ~/installers --arnold
  $(basename "$0") --installers-dir ~/installers --all-renderers --plugins-dir ~/maya-plugins
  $(basename "$0") --installers-dir ~/installers --all-renderers \\
      --push 123456789012.dkr.ecr.us-west-2.amazonaws.com/maya-aswf-ci-base
EOF
}

need_value() {
    [[ $# -ge 2 && -n "$2" ]] || die "$1 requires a value (see --help)"
}

while [[ $# -gt 0 ]]; do
    # Accept both --option VALUE and --option=VALUE.
    case "$1" in
        --*=*)
            set -- "${1%%=*}" "${1#*=}" "${@:2}"
            ;;
    esac
    case "$1" in
        --installers-dir)   need_value "$@"; INSTALLERS_DIR=$2; shift 2 ;;
        --plugins-dir)      need_value "$@"; PLUGINS_DIR=$2; shift 2 ;;
        --arnold)           WITH_ARNOLD=1; shift ;;
        --vray)             WITH_VRAY=1; shift ;;
        --redshift)         WITH_REDSHIFT=1; shift ;;
        --all-renderers)    WITH_ARNOLD=1; WITH_VRAY=1; WITH_REDSHIFT=1; shift ;;
        --maya-version)     need_value "$@"; MAYA_VERSION=$2; shift 2 ;;
        --vfx-platform-year) need_value "$@"; VFX_PLATFORM_YEAR=$2; shift 2 ;;
        --adaptor-version)  need_value "$@"; ADAPTOR_VERSION=$2; shift 2 ;;
        --tag)              need_value "$@"; TAG=$2; shift 2 ;;
        --push)             need_value "$@"; PUSH_URI=$2; shift 2 ;;
        --no-cache)         NO_CACHE=1; shift ;;
        --dry-run)          DRY_RUN=1; shift ;;
        -h | --help)        usage; exit 0 ;;
        *)                  usage >&2; die "Unknown option: $1" ;;
    esac
done

[[ "$MAYA_VERSION" =~ ^[0-9]{4}$ ]] || die "--maya-version must be a four digit year, got '$MAYA_VERSION'"

# --- Image tag -------------------------------------------------------------------
suffix=""
[[ $WITH_ARNOLD == 1 ]] && suffix+="-arnold"
[[ $WITH_VRAY == 1 ]] && suffix+="-vray"
[[ $WITH_REDSHIFT == 1 ]] && suffix+="-redshift"
TAG=${TAG:-maya-aswf:${MAYA_VERSION}${suffix}}
[[ "$TAG" == *:* ]] || die "--tag must look like NAME:TAG, got '$TAG'"
TAG_PART=${TAG##*:}

# --- ECR push target ---------------------------------------------------------------
ECR_REGISTRY=""
ECR_REGION=""
if [[ -n "$PUSH_URI" ]]; then
    if [[ "$PUSH_URI" =~ ^([0-9]{12}\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com(\.cn)?)/([a-z0-9._/-]+)$ ]]; then
        ECR_REGISTRY=${BASH_REMATCH[1]}
        ECR_REGION=${BASH_REMATCH[2]}
    else
        die "--push expects an ECR repository URI without a tag, for example" \
            "123456789012.dkr.ecr.us-west-2.amazonaws.com/maya-aswf-ci-base (got '$PUSH_URI')"
    fi
fi

# --- Pre-flight checks -----------------------------------------------------------
errors=0
problem() {
    printf '[%s] ERROR: %s\n' "$(basename "$0")" "$*" >&2
    errors=$((errors + 1))
}

if [[ $DRY_RUN == 0 ]]; then
    command -v docker > /dev/null 2>&1 || problem "docker is not installed or not on PATH"
    if command -v docker > /dev/null 2>&1 && ! docker buildx version > /dev/null 2>&1; then
        problem "docker buildx is not available; this build needs BuildKit (Docker 23+ or the buildx plugin)"
    fi
    if [[ -n "$PUSH_URI" ]] && ! command -v aws > /dev/null 2>&1; then
        problem "--push needs the AWS CLI on PATH for the ECR login"
    fi
    [[ -n "$INSTALLERS_DIR" ]] || problem "--installers-dir is required (see --help)"
fi

if [[ -n "$INSTALLERS_DIR" && ! -d "$INSTALLERS_DIR" ]]; then
    problem "installers directory does not exist: $INSTALLERS_DIR"
fi
[[ -d "$PLUGINS_DIR" ]] || problem "plugins directory does not exist: $PLUGINS_DIR"

# Installer checks run whenever an installers directory was given, including
# with --dry-run, so a dry run reports exactly which files a real build would use.
maya_file="" mtoa_file="" vray_file="" redshift_file=""
if [[ -n "$INSTALLERS_DIR" && -d "$INSTALLERS_DIR" ]]; then
    maya_file=$(find_installer "$INSTALLERS_DIR" "$(maya_installer_glob "$MAYA_VERSION")") \
        || problem "Maya installer not found: no file matching '$(maya_installer_glob "$MAYA_VERSION")' in $INSTALLERS_DIR or one subdirectory deep"
    if [[ $WITH_ARNOLD == 1 ]]; then
        mtoa_file=$(find_installer "$INSTALLERS_DIR" "$(mtoa_installer_glob "$MAYA_VERSION")") || mtoa_file=""
    fi
    if [[ $WITH_VRAY == 1 ]]; then
        if vray_file=$(find_installer "$INSTALLERS_DIR" "$(vray_installer_glob "$MAYA_VERSION")"); then
            is_elf_file "$vray_file" \
                || problem "V-Ray installer $vray_file is not a Linux executable; download the Linux (rhel8) build"
        else
            problem "V-Ray installer not found: no file matching '$(vray_installer_glob "$MAYA_VERSION")' in $INSTALLERS_DIR or one subdirectory deep"
        fi
    fi
    if [[ $WITH_REDSHIFT == 1 ]]; then
        redshift_file=$(find_installer "$INSTALLERS_DIR" "$(redshift_installer_glob)") \
            || problem "Redshift installer not found: no file matching '$(redshift_installer_glob)' in $INSTALLERS_DIR or one subdirectory deep"
    fi
fi

if [[ $errors -gt 0 ]]; then
    die "$errors problem(s) found; nothing was built. Run with --help for the expected layout."
fi

# --dry-run works on a machine without docker or installers; fall back to the
# sample's own installers/ directory so the printed command is complete.
if [[ $DRY_RUN == 1 && -z "$INSTALLERS_DIR" ]]; then
    INSTALLERS_DIR="$SAMPLE_DIR/installers"
fi

# --- Summary -----------------------------------------------------------------------
describe() {
    # describe LABEL FILE: prints the file with its size, or the fallback text.
    if [[ -n "$2" && -f "$2" ]]; then
        printf '  %-10s %s (%s)\n' "$1" "$2" "$(du -h "$2" | cut -f1)"
    else
        printf '  %-10s %s\n' "$1" "$3"
    fi
}
echo "Maya container build"
echo "  base       aswf/ci-base:${VFX_PLATFORM_YEAR}"
echo "  tag        ${TAG}"
echo "  adaptor    deadline-cloud-for-maya ${ADAPTOR_VERSION}"
describe "Maya" "$maya_file" "(not checked in --dry-run without --installers-dir)"
if [[ $WITH_ARNOLD == 1 ]]; then
    describe "Arnold" "$mtoa_file" "MtoA bundled inside the Maya archive (no $(mtoa_installer_glob "$MAYA_VERSION") supplied)"
fi
[[ $WITH_VRAY == 1 ]] && describe "V-Ray" "$vray_file" "(not checked)"
[[ $WITH_REDSHIFT == 1 ]] && describe "Redshift" "$redshift_file" "(not checked)"
if [[ $WITH_ARNOLD$WITH_VRAY$WITH_REDSHIFT == 000 ]]; then
    echo "  renderers  none (Maya software renderer only; add --arnold, --vray, --redshift or --all-renderers)"
fi
echo "  plugins    ${PLUGINS_DIR}"
[[ -n "$PUSH_URI" ]] && echo "  push       ${PUSH_URI}:${TAG_PART} (region ${ECR_REGION})"
echo

# --- docker build --------------------------------------------------------------------
build_cmd=(docker build --progress=plain)
[[ $NO_CACHE == 1 ]] && build_cmd+=(--no-cache)
build_cmd+=(
    --build-context "installers=${INSTALLERS_DIR}"
    --build-context "plugins=${PLUGINS_DIR}"
    --build-arg "VFX_PLATFORM_YEAR=${VFX_PLATFORM_YEAR}"
    --build-arg "MAYA_VERSION=${MAYA_VERSION}"
    --build-arg "ADAPTOR_VERSION=${ADAPTOR_VERSION}"
    --build-arg "WITH_ARNOLD=${WITH_ARNOLD}"
    --build-arg "WITH_VRAY=${WITH_VRAY}"
    --build-arg "WITH_REDSHIFT=${WITH_REDSHIFT}"
    -t "${TAG}"
    "${SAMPLE_DIR}"
)

print_cmd() {
    printf '%q ' "$@"
    printf '\n'
}

if [[ $DRY_RUN == 1 ]]; then
    echo "Dry run; the build command would be:"
    print_cmd "${build_cmd[@]}"
    if [[ -n "$PUSH_URI" ]]; then
        echo "followed by:"
        echo "aws ecr get-login-password --region ${ECR_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
        print_cmd docker tag "${TAG}" "${PUSH_URI}:${TAG_PART}"
        print_cmd docker push "${PUSH_URI}:${TAG_PART}"
    fi
    exit 0
fi

echo "Running:"
print_cmd "${build_cmd[@]}"
echo
"${build_cmd[@]}"
echo
log "Built ${TAG}: $(docker image inspect --format '{{.Size}}' "${TAG}" | awk '{ printf "%.1f GB", $1 / 1000000000 }') on disk"

# --- Push ------------------------------------------------------------------------------
if [[ -n "$PUSH_URI" ]]; then
    log "Logging in to ${ECR_REGISTRY}"
    aws ecr get-login-password --region "${ECR_REGION}" \
        | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    docker tag "${TAG}" "${PUSH_URI}:${TAG_PART}"
    log "Pushing ${PUSH_URI}:${TAG_PART}"
    docker push "${PUSH_URI}:${TAG_PART}"
    log "Pushed ${PUSH_URI}:${TAG_PART}"
fi
