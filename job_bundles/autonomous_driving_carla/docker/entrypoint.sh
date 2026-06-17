#!/bin/bash
# Container entrypoint:
#   1. Start CARLA server (off-screen, background)
#   2. Wait for it to accept connections on port 2000
#   3. Run scenario_runner against the input OpenSCENARIO 2.0 scenario
#   4. Capture outputs (recording + log + console output)
#   5. Cleanly stop CARLA
#
# Args:
#   $1 - path to .osc scenario inside container (typically /inputs/scenario.osc)
#   $2 - output directory inside container (typically /outputs)

set -euo pipefail

SCENARIO_FILE="${1:-/inputs/scenario.osc}"
OUTPUT_DIR="${2:-/outputs}"
CARLA_TIMEOUT_S="${CARLA_TIMEOUT_S:-120}"

if [[ ! -f "$SCENARIO_FILE" ]]; then
    echo "ERROR: Scenario file not found: $SCENARIO_FILE"
    exit 2
fi

mkdir -p "$OUTPUT_DIR"
chmod 755 "$OUTPUT_DIR" 2>/dev/null || true

echo "[$(date -u +%FT%TZ)] === CARLA OpenSCENARIO Simulation ==="
echo "Scenario file: $SCENARIO_FILE"
echo "Output dir:    $OUTPUT_DIR"
echo "CARLA timeout: ${CARLA_TIMEOUT_S}s"
echo ""

# --- Start CARLA server -----------------------------------------------------
echo "[$(date -u +%FT%TZ)] Starting CARLA server (RenderOffScreen + Xvfb)..."
cd /workspace
# -vulkan: force UE4 Vulkan RHI. Default on Linux can be OpenGL, which is
# fragile on NVIDIA + container without X. Vulkan is the recommended path
# for UE4 4.26 in headless mode.
#
# xvfb-run wraps the launch with a virtual X server. Even with
# -RenderOffScreen, UE4 4.26 client libraries (libX11, libxcb) sometimes
# touch the X server during initialization. Without one, calls return
# null and UE4 segfaults. xvfb-run -a auto-picks an unused DISPLAY.
#
# CARLA_BOOT_TOWN: pass a town name as the first positional arg to
# CarlaUE4.sh so CARLA boots directly into that map (no client.load_world call).
CARLA_BOOT_TOWN="${CARLA_BOOT_TOWN:-Town04}"
echo "[$(date -u +%FT%TZ)] CARLA boot town: $CARLA_BOOT_TOWN"
xvfb-run -a --server-args="-screen 0 1280x720x24" \
    -- ./CarlaUE4.sh "/Game/Carla/Maps/$CARLA_BOOT_TOWN" \
       -RenderOffScreen -nosound -vulkan -quality-level=Epic \
    > "$OUTPUT_DIR/carla_server.log" 2>&1 &
CARLA_PID=$!

# --- Wait for CARLA to accept connections ----------------------------------
# Two-stage readiness check: TCP port open is necessary but not sufficient.
# CARLA's UE4 server binds the port early, before the simulator is RPC-ready.
echo "[$(date -u +%FT%TZ)] Waiting for CARLA TCP on port 2000 (max ${CARLA_TIMEOUT_S}s)..."
WAITED=0
while ! nc -z localhost 2000; do
    if [[ $WAITED -ge $CARLA_TIMEOUT_S ]]; then
        echo "ERROR: CARLA TCP did not open within ${CARLA_TIMEOUT_S}s"
        echo "=== CARLA server log (tail) ==="
        tail -50 "$OUTPUT_DIR/carla_server.log" || true
        kill "$CARLA_PID" 2>/dev/null || true
        exit 3
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done
echo "[$(date -u +%FT%TZ)] CARLA TCP ready after ${WAITED}s"

echo "[$(date -u +%FT%TZ)] Verifying CARLA RPC is actually responsive..."
RPC_TIMEOUT=$((CARLA_TIMEOUT_S + 60))
set +e
"${CARLA_PYTHON:-/opt/venv/bin/python}" - <<EOF
import sys
import time
import carla

deadline = time.time() + ${RPC_TIMEOUT}
last_err = None
while time.time() < deadline:
    try:
        c = carla.Client('localhost', 2000)
        c.set_timeout(5.0)
        version = c.get_server_version()
        # Force a get_world() too — that's what scenario_runner actually calls
        w = c.get_world()
        _ = w.get_settings()
        print(f"CARLA RPC ready, server version {version}")
        sys.exit(0)
    except Exception as e:
        last_err = e
        time.sleep(2)
print(f"ERROR: CARLA RPC not ready within ${RPC_TIMEOUT}s. Last error: {last_err}", file=sys.stderr)
sys.exit(1)
EOF
RPC_OK=$?
set -e
if [[ "$RPC_OK" -ne 0 ]]; then
    echo "=== CARLA server log (tail) ==="
    tail -50 "$OUTPUT_DIR/carla_server.log" || true
    kill "$CARLA_PID" 2>/dev/null || true
    exit 3
fi
echo "[$(date -u +%FT%TZ)] CARLA fully ready"

# --- Background CARLA watchdog ---------------------------------------------
# Logs TCP connectivity + CarlaUE4 process status every 5s, in parallel with
# scenario_runner. Lets us tell "CARLA died silently" apart from "CARLA hung
# mid-call" when scenario_runner times out.
(
    # Disable set -e in the subshell - some commands in the loop legitimately
    # exit non-zero (e.g. pgrep when CARLA dies) and we don't want that to
    # kill the watchdog.
    set +e
    while true; do
        TS=$(date -u +%FT%TZ)
        if nc -z localhost 2000 2>/dev/null; then
            TCP="OPEN"
        else
            TCP="CLOSED"
        fi
        PID=$(pgrep -f CarlaUE4-Linux-Shipping 2>/dev/null | head -1)
        if [[ -n "$PID" ]]; then
            STATS=$(ps -p "$PID" -o pid,stat,%cpu,%mem,rss,vsz --no-headers 2>/dev/null | tr -s ' ')
            echo "[$TS] tcp=$TCP pid=$PID stats=$STATS"
        else
            echo "[$TS] tcp=$TCP pid=GONE"
        fi
        sleep 5
    done
) > "$OUTPUT_DIR/carla_watchdog.log" 2>&1 &
WATCHDOG_PID=$!

# --- Background multi-sensor capture ------------------------------------------
echo "[$(date -u +%FT%TZ)] Starting multi-sensor capture (RGB + semantic + LiDAR + bbox)"
PYTHONUNBUFFERED=1 "${CARLA_PYTHON:-/opt/venv/bin/python}" -u /opt/capture_sensors.py "$OUTPUT_DIR" \
    > "$OUTPUT_DIR/capture_sensors.log" 2>&1 &
CAPTURE_PID=$!

# Make sure we kill the watchdog + camera capture when the script exits.
cleanup() {
    kill "$WATCHDOG_PID" 2>/dev/null || true
    kill "$CAPTURE_PID" 2>/dev/null || true
}
trap cleanup EXIT

# --- Run scenario_runner ----------------------------------------------------
echo "[$(date -u +%FT%TZ)] Running scenario_runner..."
cd /opt/scenario_runner

# Hard wall-clock timeout - never let a hung scenario block a worker forever.
SRUNNER_HARD_TIMEOUT_S="${SRUNNER_HARD_TIMEOUT_S:-1200}"

# Whether to pass --reloadWorld to scenario_runner. Set RELOAD_WORLD=false at
# the docker-run env layer to test scenarios against CARLA's default boot
# world (skips client.load_world(town), useful when load_world segfaults).
if [[ "${RELOAD_WORLD:-true}" == "true" ]]; then
    RELOAD_WORLD_ARG="--reloadWorld"
    echo "[$(date -u +%FT%TZ)] World reload: ENABLED (--reloadWorld)"
else
    RELOAD_WORLD_ARG=""
    echo "[$(date -u +%FT%TZ)] World reload: DISABLED (no --reloadWorld)"
fi

# Don't exit on srunner failure — we want to capture outputs and the exit code.
# PYTHONUNBUFFERED=1 ensures we see progress in real time (otherwise Python
# block-buffers stdout when piped to `tee`).
set +e
# OSC2 quirk: scenario_runner's OSC2 preprocessor prepends its install
# dir to the input path (does string concat, not os.path.join). Absolute
# paths fail with "/opt/scenario_runner//inputs/...". Work around by
# staging the .osc files into a subdir of /opt/scenario_runner/ and
# passing a path relative to that.
#
# Also: OSC2 imports (e.g. `import basic.osc`) are resolved relative to
# the scenario file's directory. Stage scenario_runner's bundled stdlib
# alongside so common imports just work.
STAGING_DIR=/opt/scenario_runner/staging
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
# 1. User-provided .osc files (the scenario itself, plus any local imports)
SCENARIO_DIR=$(dirname "$SCENARIO_FILE")
cp -f "$SCENARIO_DIR"/*.osc "$STAGING_DIR/" 2>/dev/null || true
# 2. scenario_runner's bundled OSC2 stdlib (basic.osc + helpers).
#    Don't overwrite user-provided versions if they exist.
cp -n /opt/scenario_runner/srunner/examples/*.osc "$STAGING_DIR/" 2>/dev/null || true

SCENARIO_REL="staging/$(basename "$SCENARIO_FILE")"
SCENARIO_ARGS=(--openscenario2 "$SCENARIO_REL")
echo "[$(date -u +%FT%TZ)] Mode: OpenSCENARIO 2.0 (--openscenario2)"
echo "[$(date -u +%FT%TZ)] Staged 2.0 scenario files into $STAGING_DIR"
ls -la "$STAGING_DIR"
# scenario_runner builds its recorder/criteria paths as:
#   "{SR_ROOT}/{--record}/{config.name}.log"
# with SR_ROOT defaulting to "./" and config.name including the staged
# subdir (e.g. "staging/change_lane.osc"). With --record=/outputs that
# produces ".//outputs/staging/change_lane.osc.json", which from CWD
# /opt/scenario_runner resolves to /opt/scenario_runner/outputs/staging/
# — NOT the mounted /outputs. Symlink so the relative path lands in the
# real output mount, and mkdir -p the staging subdir in advance.
ln -sfn /outputs /opt/scenario_runner/outputs
mkdir -p /opt/scenario_runner/outputs/staging

timeout --kill-after=10 "$SRUNNER_HARD_TIMEOUT_S" \
    env PYTHONUNBUFFERED=1 \
    "${CARLA_PYTHON:-/opt/venv/bin/python}" -u scenario_runner.py \
    "${SCENARIO_ARGS[@]}" \
    --record "$OUTPUT_DIR" \
    ${RELOAD_WORLD_ARG:-} \
    --timeout 300 \
    --output \
    2>&1 | tee "$OUTPUT_DIR/scenario_runner.log"
SRUNNER_EXIT=${PIPESTATUS[0]}
set -e

# Map the timeout exit codes to something descriptive
if [[ "$SRUNNER_EXIT" -eq 124 ]]; then
    echo "[$(date -u +%FT%TZ)] scenario_runner exceeded ${SRUNNER_HARD_TIMEOUT_S}s and was terminated"
fi

# scenario_runner.py occasionally returns 0 even on RuntimeError; detect that
# from the log and treat as a failure. Only match the exact failure summary line
# that scenario_runner emits at the end of a failed run.
if [[ "$SRUNNER_EXIT" -eq 0 ]] && grep -qP "^ERROR \(.*\): Simulation failed\." "$OUTPUT_DIR/scenario_runner.log"; then
    echo "[$(date -u +%FT%TZ)] scenario_runner log contains failure markers despite exit code 0"
    SRUNNER_EXIT=4
fi

echo "[$(date -u +%FT%TZ)] scenario_runner exited with code $SRUNNER_EXIT"

# Give sensor capture a moment to flush, then stop it.
sleep 2
kill "$CAPTURE_PID" 2>/dev/null || true
wait "$CAPTURE_PID" 2>/dev/null || true
echo ""
echo "=== Sensor capture log ==="
cat "$OUTPUT_DIR/capture_sensors.log" 2>/dev/null || echo "(no capture log)"
echo ""

# Helper: count *.png files under a dir, robust to missing dirs under set -euo pipefail.
# `find` exits non-zero when the path doesn't exist, which combined with pipefail
# would kill the script. Check existence first, then count.
count_png() {
    local d="$1"
    if [[ -d "$d" ]]; then
        find "$d" -name "*.png" 2>/dev/null | wc -l
    else
        echo 0
    fi
}

FRAME_COUNT=$(count_png "$OUTPUT_DIR/rgb")
echo "[$(date -u +%FT%TZ)] Sensors captured $FRAME_COUNT frames total"

# Generate videos from pre-composed mosaic frames (frame-synchronized, no alignment issues)
if command -v ffmpeg &>/dev/null && [[ "$FRAME_COUNT" -gt 0 ]]; then
    mkdir -p "$OUTPUT_DIR/video"

    RGB_MOSAIC_COUNT=$(count_png "$OUTPUT_DIR/rgb_mosaic")
    if [[ "$RGB_MOSAIC_COUNT" -gt 0 ]]; then
        echo "[$(date -u +%FT%TZ)] Generating RGB mosaic video from $RGB_MOSAIC_COUNT frames..."
        ffmpeg -y -framerate 7 -pattern_type glob \
            -i "$OUTPUT_DIR/rgb_mosaic/frame_*.png" \
            -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
            "$OUTPUT_DIR/video/rgb_mosaic.mp4" 2>/dev/null && \
            echo "[$(date -u +%FT%TZ)] RGB mosaic video done" || \
            echo "[$(date -u +%FT%TZ)] RGB mosaic video failed"
    fi

    SEM_MOSAIC_COUNT=$(count_png "$OUTPUT_DIR/semantic_mosaic")
    if [[ "$SEM_MOSAIC_COUNT" -gt 0 ]]; then
        echo "[$(date -u +%FT%TZ)] Generating semantic mosaic video from $SEM_MOSAIC_COUNT frames..."
        ffmpeg -y -framerate 7 -pattern_type glob \
            -i "$OUTPUT_DIR/semantic_mosaic/frame_*.png" \
            -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
            "$OUTPUT_DIR/video/semantic_mosaic.mp4" 2>/dev/null && \
            echo "[$(date -u +%FT%TZ)] Semantic mosaic video done" || \
            echo "[$(date -u +%FT%TZ)] Semantic mosaic video failed"
    fi
fi

# Stop the watchdog now (cleanup trap will run again on exit, idempotent)
kill "$WATCHDOG_PID" 2>/dev/null || true

# Dump watchdog log into the main task output for visibility
echo ""
echo "=== CARLA watchdog timeline (last 40 entries) ==="
tail -40 "$OUTPUT_DIR/carla_watchdog.log" 2>/dev/null || echo "(no watchdog log)"

# UE4 sometimes writes crash dumps to Saved/Crashes/ — surface them if present
CRASH_DIR=/workspace/CarlaUE4/Saved/Crashes
if [[ -d "$CRASH_DIR" ]] && [[ -n "$(ls -A "$CRASH_DIR" 2>/dev/null)" ]]; then
    echo ""
    echo "=== UE4 crash dumps found in $CRASH_DIR ==="
    ls -la "$CRASH_DIR"
    # Copy crashes into outputs so they get uploaded via job attachments
    cp -r "$CRASH_DIR" "$OUTPUT_DIR/ue4_crashes" 2>/dev/null || true
    # Also dump the most recent crash log inline for quick triage
    LATEST_CRASH=$(find "$CRASH_DIR" -name '*.log' -type f -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr | head -1 | awk '{print $2}')
    if [[ -n "$LATEST_CRASH" ]]; then
        echo ""
        echo "=== Latest UE4 crash log: $LATEST_CRASH ==="
        tail -100 "$LATEST_CRASH"
    fi
else
    echo ""
    echo "(no UE4 crash dumps in $CRASH_DIR)"
fi

# UE4's main runtime log — far more verbose than stdout. This is where load
# failures, asset errors, missing files, and pre-crash state are recorded.
SAVED_LOG=/workspace/CarlaUE4/Saved/Logs/CarlaUE4.log
if [[ -f "$SAVED_LOG" ]]; then
    echo ""
    echo "=== UE4 saved log ($SAVED_LOG) — last 100 lines ==="
    tail -100 "$SAVED_LOG"
    # Copy full log to outputs for offline analysis
    cp "$SAVED_LOG" "$OUTPUT_DIR/CarlaUE4.log" 2>/dev/null || true
else
    echo ""
    echo "(no UE4 saved log at $SAVED_LOG)"
    echo "Listing /workspace/CarlaUE4/Saved/:"
    ls -la /workspace/CarlaUE4/Saved/ 2>/dev/null || echo "(Saved/ does not exist)"
fi

# Tail the main carla_server.log unconditionally for visibility
echo ""
echo "=== carla_server.log (tail) ==="
tail -40 "$OUTPUT_DIR/carla_server.log" 2>/dev/null || echo "(no carla_server.log)"

# --- Stop CARLA -------------------------------------------------------------
echo "[$(date -u +%FT%TZ)] Stopping CARLA server..."
kill "$CARLA_PID" 2>/dev/null || true
# Give CARLA a few seconds to shut down gracefully
for i in {1..10}; do
    if ! kill -0 "$CARLA_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done
# Force kill if still running
kill -9 "$CARLA_PID" 2>/dev/null || true
wait "$CARLA_PID" 2>/dev/null || true

# --- Summarize outputs ------------------------------------------------------
echo ""
echo "=== Output files in $OUTPUT_DIR ==="
ls -la "$OUTPUT_DIR" || true

# Make outputs world-writable so the host (different UID than container 'carla'
# user) can clean up the session working directory after the run.
chmod -R a+rwX "$OUTPUT_DIR" 2>/dev/null || true

echo ""
echo "[$(date -u +%FT%TZ)] Done"
exit "$SRUNNER_EXIT"
