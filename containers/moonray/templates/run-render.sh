#!/usr/bin/env bash
#
# Render a MoonRay example scene through Open Job Description, once with the
# Python openjd-cli and once with the Rust openjd CLI.
#
# The job template carries no docker knowledge; local-docker-wrap-env.yaml supplies
# WRAP_ACTIONS hooks that re-run each action inside the openmoonray-rocky9
# image with ./sessions bind mounted, so the scenes are visible inside the
# container and the .exr comes back out on the host.
#
# Which implementation runs is the first argument:
#   ./run-render.sh                # both, python first then rust
#   ./run-render.sh python         # openjd-cli   (Python) from $VENV/bin
#   ./run-render.sh rust           # openjd       (Rust)   from $RUST_BIN
#   ./run-render.sh path           # whichever openjd is already on PATH
#   ./run-render.sh --fetch-only   # download and unpack scenes, render nothing
#
# python and rust look in the checkout locations below, which suit a machine
# with both built from source. Use `path` if you installed one of them normally.
# Each run records the openjd it resolved, and its version, at the top of its
# log — so which implementation produced a given .exr is never a guess.
#
# Environment overrides:
#   IMAGE=openmoonray-rocky9   container image to run
#   SCENE=veach-mis            example scene to render
#   EXEC_MODE=scalar           scalar | vectorized
#   DOCKER_USER=<uid>:<gid>    defaults to the invoking user
#   KEEP_SESSIONS=1            pass --preserve so session dirs survive (default 1)
#   VENV=...  RUST_BIN=...     where to find the python / rust openjd

set -u -o pipefail

TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

JOB_TEMPLATE="$TEMPLATE_DIR/moonray-render-job.yaml"
WRAP_ENV="$TEMPLATE_DIR/local-docker-wrap-env.yaml"

# Session root. Everything mutable lives under here, and this whole directory
# is what gets bind mounted into the container. Not checked into git.
SESSIONS_DIR="$TEMPLATE_DIR/sessions"
SCENES_DIR="$SESSIONS_DIR/scenes"
OUTPUT_DIR="$SESSIONS_DIR/output"
LOG_DIR="$SESSIONS_DIR/logs"

# The zip is downloaded beside the templates; it unpacks into the session dir.
SCENES_URL="https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip"
SCENES_ZIP="$TEMPLATE_DIR/example_scenes.zip"

IMAGE="${IMAGE:-openmoonray-rocky9}"
CONTAINER_MOUNT="${CONTAINER_MOUNT:-/mnt/session}"
SCENE="${SCENE:-veach-mis}"
EXEC_MODE="${EXEC_MODE:-scalar}"
DOCKER_USER="${DOCKER_USER:-$(id -u):$(id -g)}"
KEEP_SESSIONS="${KEEP_SESSIONS:-1}"

VENV="${VENV:-$HOME/work/openjd/.venv}"
RUST_BIN="${RUST_BIN:-$HOME/work/openjd/openjd-rs/target/release}"

die() { echo "error: $*" >&2; exit 1; }
note() { echo "==> $*"; }

# ------------------------------------------------------- implementation pick --
# Resolve the openjd executable for one implementation, failing early and
# specifically rather than letting `openjd: command not found` surface from
# inside a session. Sets OPENJD_DIR (empty means "leave PATH alone"),
# OPENJD_EXE and OPENJD_VERSION.
resolve_openjd() {
    local impl="$1" dir="" hint=""

    case "$impl" in
        python) dir="$VENV/bin"  ; hint="set VENV=<path to the venv with openjd-cli installed>" ;;
        rust)   dir="$RUST_BIN"  ; hint="set RUST_BIN=<openjd-rs>/target/release, or build it with: cargo build --release" ;;
        path)   dir=""           ; hint="install openjd-cli, or put the openjd-rs binary on PATH" ;;
        *)      die "resolve_openjd: unknown implementation '$impl'" ;;
    esac

    if [ -n "$dir" ]; then
        OPENJD_EXE="$dir/openjd"
        [ -x "$OPENJD_EXE" ] || die "no openjd executable at $OPENJD_EXE
    $hint
    or run ./run-render.sh path to use whichever openjd is on PATH"
    else
        OPENJD_EXE="$(command -v openjd 2>/dev/null || true)"
        [ -n "$OPENJD_EXE" ] || die "no openjd found on PATH
    $hint"
    fi

    OPENJD_DIR="$dir"

    # openjd-cli implements --version; the Rust CLI currently does not, so fall
    # back to naming the binary rather than reporting nothing.
    OPENJD_VERSION="$("$OPENJD_EXE" --version 2>/dev/null | head -1)"
    [ -n "$OPENJD_VERSION" ] || OPENJD_VERSION="(no --version flag; openjd-rs does not implement one)"
}

# ---------------------------------------------------------------- preflight --
preflight() {
    command -v docker >/dev/null 2>&1 || die "docker not found on PATH"
    docker info >/dev/null 2>&1 || die "the docker daemon is not reachable"
    command -v curl  >/dev/null 2>&1 || die "curl not found on PATH"
    command -v unzip >/dev/null 2>&1 || die "unzip not found on PATH"

    docker image inspect "$IMAGE" >/dev/null 2>&1 \
        || die "image '$IMAGE' not found. Build it first, from the sibling sample:
    cd $(cd "$TEMPLATE_DIR/.." && pwd)/rocky9-cpu
    docker build --platform linux/amd64 -t $IMAGE ."

    [ -f "$JOB_TEMPLATE" ] || die "missing job template: $JOB_TEMPLATE"
    [ -f "$WRAP_ENV" ]     || die "missing wrap environment: $WRAP_ENV"
}

# ------------------------------------------------------------------- scenes --
# Download the official example scenes and unpack them into the session dir,
# which is the directory the container sees. Both steps are skipped if already
# done, so re-running the script is cheap.
fetch_scenes() {
    mkdir -p "$SCENES_DIR" "$OUTPUT_DIR" "$LOG_DIR"

    local scene_root="$SCENES_DIR/example_scenes/pbrt_scenes"

    if [ -d "$scene_root/$SCENE" ]; then
        note "scenes already unpacked at $scene_root"
        return 0
    fi

    if [ ! -f "$SCENES_ZIP" ]; then
        note "downloading example scenes (~700 MB) to $SCENES_ZIP"
        curl -fL --retry 3 -o "$SCENES_ZIP.part" "$SCENES_URL" \
            || die "download failed: $SCENES_URL"
        mv "$SCENES_ZIP.part" "$SCENES_ZIP"
    else
        note "reusing existing $SCENES_ZIP"
    fi

    note "unpacking into $SCENES_DIR"
    unzip -q -o "$SCENES_ZIP" -d "$SCENES_DIR" || die "unzip failed"

    [ -d "$scene_root/$SCENE" ] \
        || die "scene '$SCENE' not found under $scene_root after unpacking"
}

# -------------------------------------------------------------------- render --
# $1 = impl label (python|rust|path)
render_with() {
    local impl="$1"
    local log="$LOG_DIR/render-$impl.log"
    local expected="$OUTPUT_DIR/$impl-$SCENE.exr"

    resolve_openjd "$impl"
    local bindir="$OPENJD_DIR"

    # Note: bash 4.2 (this host) treats "${arr[@]}" on an empty array as an
    # unbound variable under `set -u`, hence the ${arr[@]+...} guards below.
    local preserve=()
    [ "$KEEP_SESSIONS" = "1" ] && preserve=(--preserve)

    rm -f "$expected"

    note "$impl: using $OPENJD_EXE"
    note "$impl: version $OPENJD_VERSION"
    note "$impl: rendering $SCENE -> $(basename "$expected")  (log: $log)"

    # Record the resolved implementation at the top of the log, so a log or an
    # .exr can always be traced back to the CLI that produced it.
    {
        echo "implementation: $impl"
        echo "openjd:         $OPENJD_EXE"
        echo "version:        $OPENJD_VERSION"
        echo "scene:          $SCENE   exec_mode: $EXEC_MODE   image: $IMAGE"
        echo "started:        $(date -Is)"
        echo "----------------------------------------------------------------"
    } > "$log"

    # Neither CLI exposes a session-directory flag; both derive the session
    # root from the system temp dir on POSIX, so TMPDIR is what puts the
    # session working directories under ./sessions (as ./sessions/OpenJD/...).
    #
    # The venv's bin stays on PATH for the Rust run too, so a bare `python`
    # resolves identically in both.
    local start end rc
    start=$(date +%s)
    (
        export TMPDIR="$SESSIONS_DIR"
        # Put the chosen implementation first. For `path` there is nothing to
        # prepend. The venv's bin follows when it exists, so the bare `python`
        # some job fixtures spawn resolves the same way for every choice.
        [ -n "$bindir" ] && PATH="$bindir:$PATH"
        [ -d "$VENV/bin" ] && PATH="$PATH:$VENV/bin"
        export PATH
        openjd run "$JOB_TEMPLATE" \
            --environment "$WRAP_ENV" \
            --step Render \
            -p "SessionsDir=$SESSIONS_DIR" \
            -p "ContainerMount=$CONTAINER_MOUNT" \
            -p "Image=$IMAGE" \
            -p "DockerUser=$DOCKER_USER" \
            -p "ExecMode=$EXEC_MODE" \
            -p "OutputPrefix=$impl" \
            ${preserve[@]+"${preserve[@]}"} \
            --verbose
    ) >> "$log" 2>&1
    rc=$?
    end=$(date +%s)

    echo "EXIT:$rc SECONDS:$((end - start))" >> "$log"

    # A zero exit code is not proof the render happened — check the artifact.
    local size=0
    [ -f "$expected" ] && size=$(stat -c %s "$expected" 2>/dev/null || echo 0)

    if [ "$rc" -eq 0 ] && [ "$size" -gt 0 ]; then
        note "$impl: OK  $((end - start))s  $(numfmt --to=iec "$size" 2>/dev/null || echo "$size B")  $expected"
        RESULTS+=("$impl|PASS|$((end - start))|$size|$log")
    else
        note "$impl: FAILED  rc=$rc  $((end - start))s  exr_bytes=$size  see $log"
        RESULTS+=("$impl|FAIL|$((end - start))|$size|$log")
    fi
}

# ---------------------------------------------------------------------- main --
TARGET="${1:-both}"

case "$TARGET" in
    --fetch-only)
        fetch_scenes
        note "fetch complete; nothing rendered"
        exit 0
        ;;
    python|rust|path|both) ;;
    -h|--help)
        sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    *)
        die "unknown target '$TARGET' (expected python, rust, path, both, or --fetch-only)"
        ;;
esac

preflight
fetch_scenes

RESULTS=()

case "$TARGET" in
    python) render_with python ;;
    rust)   render_with rust ;;
    path)   render_with path ;;
    both)
        render_with python
        render_with rust
        ;;
esac

echo
printf '%-8s %-6s %8s %14s  %s\n' IMPL RESULT SECONDS EXR_BYTES LOG
failures=0
for row in ${RESULTS[@]+"${RESULTS[@]}"}; do
    IFS='|' read -r impl status secs bytes log <<< "$row"
    printf '%-8s %-6s %8s %14s  %s\n' "$impl" "$status" "$secs" "$bytes" "$log"
    [ "$status" = PASS ] || failures=$((failures + 1))
done

exit $((failures > 0))
