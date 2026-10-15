#!/usr/bin/env bash
# Start and stop the vLLM-Omni Cosmos 3 server for a session.
#
# This runs INSIDE the container the Docker queue environment started, because
# that environment wraps every action on the queue. So there are no docker
# commands here and no image name: the queue owns the container, this script owns
# one process inside it.
#
# That arrangement is what makes a shared server possible. Each wrapped action is
# `docker container exec`ed into the same long-lived container, so they share a
# process and network namespace, and a background process started here is
# reachable on localhost from every task in the session. Because each session
# gets its own container, a fixed port needs no collision handling.
#
# Both GPU steps use this, so it lives in one bundled file rather than being
# duplicated into two stepEnvironments. Bundled scripts are not OpenJD format
# strings, so the usual brace restriction does not apply here.
#
# Usage: serve_cosmos3.sh start <model> <boot-timeout-s> <offload-mode> \
#                              <gpu-mib-floor> <log-dir> <session-dir>
#        serve_cosmos3.sh stop
#
# On start it prints `openjd_env:` lines so the step's tasks inherit:
#   COSMOS3_BASE_URL     where to send requests
#   COSMOS3_SERVER_PID   the server pid, read back by `stop`
#   COSMOS3_SERVER_LOG   the server log path, read back by `stop`
#   COSMOS3_GPU_CLAIM    the claimed GPU's lock directory, released by `stop`

set -euo pipefail

ACTION="${1:-}"
PORT=8000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[serve_cosmos3] $*"; }
fail() { echo "openjd_fail: $*" >&2; exit 1; }

print_log_tail() {
    local path="${1:-}" lines="${2:-100}"
    [ -n "$path" ] && [ -f "$path" ] || return 0
    echo ""
    echo "=== last $lines lines of $path"
    tail -n "$lines" "$path" 2>/dev/null || true
    echo "==="
    echo ""
}

stop_server() {
    local pid="${COSMOS3_SERVER_PID:-}"
    # Always surface the log tail, including on the success path. When a task
    # failed because the server died mid-request, this is the only place the
    # reason appears.
    print_log_tail "${COSMOS3_SERVER_LOG:-}" 100
    if [ -z "$pid" ]; then
        log "COSMOS3_SERVER_PID is unset; nothing to stop"
        return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        log "server pid $pid is already gone"
        return 0
    fi
    log "stopping server pid $pid"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        log "pid $pid ignored SIGTERM; sending SIGKILL"
        kill -9 "$pid" 2>/dev/null || true
    fi
    log "stopped"
}

release_gpu_claim() {
    local claim="${COSMOS3_GPU_CLAIM:-}"
    [ -n "$claim" ] && [ -d "$claim" ] || return 0
    # Only release a claim this session owns. A reclaimed-then-reassigned index
    # must not be freed out from under its new owner.
    local owner
    owner=$(cat "${claim}/owner" 2>/dev/null || true)
    if [ -n "$owner" ] && [ "$owner" != "${SESSION_DIR:-}" ]; then
        log "GPU claim ${claim} now belongs to another session; leaving it alone"
        return 0
    fi
    rm -rf "$claim" 2>/dev/null || true
    log "released GPU claim ${claim}"
}

if [ "$ACTION" = "stop" ]; then
    # SESSION_DIR is only needed to verify claim ownership; absent is fine.
    SESSION_DIR="${2:-${SESSION_DIR:-}}"
    stop_server
    release_gpu_claim
    exit 0
fi

if [ "$ACTION" != "start" ]; then
    fail "unknown action '$ACTION'; expected start or stop"
fi

MODEL="${2:?model required}"
BOOT_TIMEOUT="${3:?boot timeout required}"
OFFLOAD_MODE="${4:?offload mode required}"   # auto | always | never
GPU_MIB_FLOOR="${5:?gpu mib floor required}"
LOG_DIR="${6:?log dir required}"
SESSION_DIR="${7:?session dir required}"

command -v vllm >/dev/null 2>&1 || fail \
    "vllm is not on PATH inside the container. The queue's DockerImage must
provide 'vllm serve --omni'; vllm/vllm-omni:cosmos3 does. Action generation is
only available through vLLM-Omni, so a plain vllm image is not enough."

command -v python3 >/dev/null 2>&1 || fail "python3 is not on PATH inside the container"

# --- GPU plumbing and capacity ----------------------------------------------
# This is the first place a missing GPU is caught, so check plumbing before
# capacity. The queue environment does NOT verify that a GPU reached the
# container: it adds --gpus all only when /etc/cdi/nvidia.yaml exists, and
# otherwise starts the container with no GPU flags and no complaint.
#
# Capacity then matters because Cosmos3-Nano is 16B parameters and its
# transformer weights alone are ~30 GB in BF16, so a 48 GB L40S holds it while a
# 24 GB A10G or L4 does not. Service-managed fleets publish no GPU-memory
# capability and no accelerator-name attribute, so hostRequirements cannot pin
# the GPU model and this has to be checked on the worker.
command -v nvidia-smi >/dev/null 2>&1 || fail \
    "nvidia-smi is not on PATH inside the container. The image does not carry it,
or the container got no GPU. On a fleet with the docker add-on, check that
/etc/cdi/nvidia.yaml exists on the worker; the add-on generates it at boot and
fails the boot if it cannot."

# Capture the whole output and slice in bash rather than piping into `head`.
# Under `set -o pipefail`, `nvidia-smi | head -1` on a multi-GPU host kills this
# script with no output at all: head exits after one line, nvidia-smi takes
# SIGPIPE, and pipefail surfaces 141 which `set -e` turns into a silent exit.
# The bug is GPU-count dependent, so it hides completely on a 1-GPU worker and
# fails every time on a 4-GPU one.
GPU_NAMES=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || true)
GPU_MEMS=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null || true)
GPU_NAME=$(printf '%s' "${GPU_NAMES%%$'\n'*}" | tr -d '\r')
GPU_TOTAL_MIB=$(printf '%s' "${GPU_MEMS%%$'\n'*}" | tr -d ' \r')
if [ -z "${GPU_TOTAL_MIB:-}" ]; then
    fail "nvidia-smi reported no GPU. The container was started without working
GPU access. Check that /etc/cdi/nvidia.yaml exists on the worker and that the
fleet requests at least one accelerator."
fi
log "GPU: $GPU_NAME with ${GPU_TOTAL_MIB} MiB"

case "$OFFLOAD_MODE" in
    always)
        USE_OFFLOAD=1
        log "OffloadMode=always; enabling --enable-layerwise-offload"
        ;;
    never)
        USE_OFFLOAD=0
        if [ "$GPU_TOTAL_MIB" -lt "$GPU_MIB_FLOOR" ]; then
            fail "GPU $GPU_NAME has ${GPU_TOTAL_MIB} MiB, below the ${GPU_MIB_FLOOR} MiB
floor, and OffloadMode=never forbids the workaround. Either set OffloadMode=auto,
or narrow the fleet's acceleratorCapabilities to an accelerator with enough
memory (l40s rather than a10g or l4)."
        fi
        ;;
    auto)
        if [ "$GPU_TOTAL_MIB" -lt "$GPU_MIB_FLOOR" ]; then
            USE_OFFLOAD=1
            log "GPU has ${GPU_TOTAL_MIB} MiB, below the ${GPU_MIB_FLOOR} MiB floor; enabling --enable-layerwise-offload"
        else
            USE_OFFLOAD=0
            log "GPU has ${GPU_TOTAL_MIB} MiB, at or above the ${GPU_MIB_FLOOR} MiB floor; no offload"
        fi
        ;;
    *) fail "OffloadMode must be auto, always or never; got '$OFFLOAD_MODE'" ;;
esac

# --- host memory, when offloading -------------------------------------------
# Layerwise offload keeps transformer weights in HOST memory and streams them to
# the GPU, so it trades GPU memory for host memory rather than reducing the
# total. The checkpoint is ~35 GB, so a worker that satisfies the step's
# 32 GiB hostRequirements can still be far too small.
#
# Checking it here matters because the failure is otherwise unreadable and slow.
# On a g6e.2xlarge (61 GiB usable) the diffusion worker was OOM-killed 515
# seconds into startup, and the parent reported only
#   EOFError  ... RuntimeError: Orchestrator initialization failed
# with no mention of memory. The same parameters succeeded on a g6e.12xlarge
# with 384 GiB.
if [ "$USE_OFFLOAD" = "1" ]; then
    # COSMOS3_MEMINFO exists so the guard is testable off Linux, where there is
    # no /proc/meminfo and the check would otherwise only ever take the skip path.
    MEMINFO="${COSMOS3_MEMINFO:-/proc/meminfo}"
    HOST_MIB=$(awk '/^MemTotal:/ {printf "%d", $2/1024}' "$MEMINFO" 2>/dev/null || echo 0)
    # Weights plus room for activations, the guardrail model and page cache.
    # Derived from the two observations above, not from a vendor figure.
    HOST_MIB_FLOOR=$(( 96 * 1024 ))
    if [ "${HOST_MIB:-0}" -lt 1 ]; then
        log "WARNING: could not read MemTotal; skipping the host memory check"
    elif [ "$HOST_MIB" -lt "$HOST_MIB_FLOOR" ]; then
        fail "offload is enabled but this host has only ${HOST_MIB} MiB of RAM,
below the ${HOST_MIB_FLOOR} MiB this needs. Layerwise offload moves the ~35 GB
checkpoint into host memory, so it needs a larger instance, not a larger GPU.
Either raise the step's amount.worker.memory so the fleet must pick one (128 GiB
or more, which for g6e means 4xlarge and up), or set OffloadMode=never and give
the task a GPU that holds the model resident."
    fi
    log "host memory ${HOST_MIB} MiB, at or above the ${HOST_MIB_FLOOR} MiB offload floor"
fi

# --- weight cache ----------------------------------------------------------
# The queue environment publishes HF_HOME when the fleet has a persistent volume
# and ModelCacheSubdir is set. Without it the ~35 GB checkpoint downloads once
# per session, and each GPU step is its own session, so the job pays it twice.
if [ -n "${HF_HOME:-}" ]; then
    log "HF_HOME=${HF_HOME}"
    if [ ! -w "${HF_HOME}" ]; then
        fail "HF_HOME is ${HF_HOME} but it is not writable by $(id -un 2>/dev/null || echo this user).
The queue environment binds its cache at an identical path so ownership matches;
a mismatch here usually means the mount is missing inside the container."
    fi
else
    log "HF_HOME is unset by the queue environment; a session-local cache is set below."
fi

# --- claim one GPU ------------------------------------------------------------
# On a multi-GPU worker several sessions run at once, and each would otherwise
# start a server that sees every GPU and fight over the same memory. Deadline
# Cloud reserves GPU *amounts*, not device indices, so nothing tells a session
# which device is its own: the sessions have to agree among themselves.
#
# The claim is a directory, because mkdir is atomic. The owner token is the
# session working directory, which exists only while the session does, so a
# claim whose owner directory is gone is stale and can be taken. That
# self-heals after a worker dies mid-session, where a timeout would either leak
# the GPU or steal it from a slow starter.
#
# CUDA_VISIBLE_DEVICES is a soft limit: a process can unset it. That is
# acceptable here, because the only process that matters is the server this
# script starts.
# `wc -l` reads to EOF, so this pipeline cannot take SIGPIPE.
GPU_COUNT=$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ' || true)
if [ "${GPU_COUNT:-0}" -gt 1 ]; then
    # The rendezvous has to be visible from every session's container, so it
    # lives under the shared weight cache the queue environment bind-mounts at an
    # identical path. MODEL_CACHE_DIR is only set by this sample's tests; in
    # production the queue environment exports HF_HOME, so prefer that. Without
    # a shared directory every session claimed index 0 and the servers all
    # loaded onto one GPU and ran out of memory.
    CLAIM_BASE="${MODEL_CACHE_DIR:-${HF_HOME:-}}"
    if [ -z "$CLAIM_BASE" ] || [ ! -d "$CLAIM_BASE" ]; then
        fail "this worker reports ${GPU_COUNT} GPUs, and arbitrating between
concurrent sessions needs a directory every session can see. Set the queue
environment's ModelCacheSubdir so it exports HF_HOME, or run this fleet with one
accelerator per worker."
    fi
    CLAIM_ROOT="${CLAIM_BASE}/gpu-claims"
    mkdir -p "$CLAIM_ROOT"

    # Staleness by heartbeat, not by probing the peer's session directory: that
    # directory is not bind-mounted into this container, so it always looked
    # absent and every claim looked reclaimable.
    # Age via `find -mmin`, which BSD and GNU both support. `stat -c %Y` is
    # GNU-only: on a BSD stat it fails, the age reads as enormous, and every
    # claim looks stale, so concurrent sessions all take index 0. Production runs
    # Linux, but a check that cannot be exercised off Linux is a check nobody
    # tests.
    CLAIM_STALE_MINUTES="${COSMOS3_CLAIM_STALE_MINUTES:-15}"
    MY_GPU=""
    for idx in $(seq 0 $(( GPU_COUNT - 1 ))); do
        CLAIM="${CLAIM_ROOT}/${idx}"
        if mkdir "$CLAIM" 2>/dev/null; then
            MY_GPU="$idx"
            break
        fi
        # Stale when the heartbeat is missing, or older than the threshold.
        STALE=1
        if [ -f "${CLAIM}/heartbeat" ]; then
            if [ -z "$(find "${CLAIM}/heartbeat" -mmin "+${CLAIM_STALE_MINUTES}" 2>/dev/null)" ]; then
                STALE=0
            fi
        fi
        if [ "$STALE" = "1" ]; then
            log "GPU ${idx} claim has no heartbeat in the last ${CLAIM_STALE_MINUTES} minutes; reclaiming"
            rm -rf "$CLAIM" 2>/dev/null || true
            if mkdir "$CLAIM" 2>/dev/null; then
                MY_GPU="$idx"
                break
            fi
        fi
    done
    if [ -z "$MY_GPU" ]; then
        fail "all ${GPU_COUNT} GPUs on this worker are claimed by sessions whose
claims were refreshed within the last ${CLAIM_STALE_MINUTES} minutes. Each task reserves
amount.worker.gpu, so the scheduler should not oversubscribe: check that the
step's hostRequirements ask for at least 1 GPU. Claims are under ${CLAIM_ROOT}."
    fi
    CLAIM="${CLAIM_ROOT}/${MY_GPU}"
    printf '%s\n' "${SESSION_DIR:-$PWD}" > "${CLAIM}/owner"
    touch "${CLAIM}/heartbeat"
    # Refresh the heartbeat while this session lives, so a long generation is not
    # mistaken for an abandoned claim. The toucher dies with the container.
    ( while [ -d "$CLAIM" ]; do touch "${CLAIM}/heartbeat" 2>/dev/null || exit 0
        sleep 60; done ) >/dev/null 2>&1 &
    export CUDA_VISIBLE_DEVICES="$MY_GPU"
    echo "openjd_env: COSMOS3_GPU_CLAIM=${CLAIM}"
    log "claimed GPU index ${MY_GPU} of ${GPU_COUNT} (CUDA_VISIBLE_DEVICES=${MY_GPU})"
else
    log "single-GPU worker; no claim needed"
fi

# --- a home for a uid the image has never heard of ----------------------------
# The queue environment execs as the HOST user's uid and gid, which has no entry
# in the container's /etc/passwd. `import vllm` then dies before any GPU work
# begins, because torch._inductor names its cache directory from
# getpass.getuser():
#   KeyError: 'getpwuid(): uid not found: 1001'
#
# This does not arise on a fleet with the docker add-on, where the queue
# environment execs `--user 0:0` and a rootless userns maps container root to the
# job user: root exists in the image, so the lookup succeeds. It does arise on a
# rootful fleet that execs as the host uid, and these exports are what keep one
# script working on both.
#
# Naming the user is the fix. getpass.getuser() consults LOGNAME, USER, LNAME
# then USERNAME before falling back to pwd.getpwuid(), so setting them resolves
# the lookup at every call site.
#
# Setting the cache variables alone does NOT work, as a first attempt proved:
# torch._inductor.codecache calls default_cache_dir() directly, which derives a
# username regardless of TORCHINDUCTOR_CACHE_DIR. They are still set below, to
# keep the caches in the session directory: bind-mounted at an identical path,
# writable by this uid, and discarded with the session. HOME is set for the same
# reason, since the host user's home does not exist in the container.
export LOGNAME="${LOGNAME:-container-$(id -u)}"
export USER="${USER:-$LOGNAME}"
export LNAME="${LNAME:-$LOGNAME}"
export USERNAME="${USERNAME:-$LOGNAME}"

CACHE_ROOT="${SESSION_DIR}/cosmos3-cache"
mkdir -p "${CACHE_ROOT}"/{home,torchinductor,triton,hf,xdg}
export HOME="${CACHE_ROOT}/home"
export TORCHINDUCTOR_CACHE_DIR="${CACHE_ROOT}/torchinductor"
export TRITON_CACHE_DIR="${CACHE_ROOT}/triton"
export XDG_CACHE_HOME="${CACHE_ROOT}/xdg"
# Only claim HF_HOME when the queue environment did not provide a persistent
# one: overriding a real cache would re-download ~35 GB every session.
if [ -z "${HF_HOME:-}" ]; then
    export HF_HOME="${CACHE_ROOT}/hf"
    log "HF_HOME unset by the queue environment; using ${HF_HOME} (lost at session end)"
fi
log "running as uid $(id -u) USER=${USER} HOME=${HOME}"

mkdir -p "$LOG_DIR"
SERVER_LOG="${LOG_DIR}/cosmos3_server.log"

SERVE_ARGS=(vllm serve "$MODEL" --omni --host 127.0.0.1 --port "$PORT" --init-timeout "$BOOT_TIMEOUT")
if [ "$USE_OFFLOAD" = "1" ]; then
    SERVE_ARGS+=(--enable-layerwise-offload)
fi
log "serve args: ${SERVE_ARGS[*]}"
log "server log: $SERVER_LOG"

# Detach the server from this action's process group, so it survives the
# `docker exec` for onEnter returning. The container's PID 1 outlives every exec,
# so the process is reparented there and persists for the whole session.
#
# setsid is preferred but is not guaranteed: it is absent from a minimal image
# and from macOS, where this script is linted. nohup in the background is enough
# on its own, so treat setsid as an optimization rather than a requirement.
if command -v setsid >/dev/null 2>&1; then
    setsid nohup "${SERVE_ARGS[@]}" > "$SERVER_LOG" 2>&1 &
else
    nohup "${SERVE_ARGS[@]}" > "$SERVER_LOG" 2>&1 &
fi
SERVER_PID=$!
log "server pid $SERVER_PID"

BASE_URL="http://127.0.0.1:${PORT}"
echo "openjd_env: COSMOS3_BASE_URL=$BASE_URL"
echo "openjd_env: COSMOS3_SERVER_PID=$SERVER_PID"
echo "openjd_env: COSMOS3_SERVER_LOG=$SERVER_LOG"

# The probe lives in python3 rather than bash because the serving image is
# guaranteed to carry python3 and is not guaranteed to carry curl. Passing the
# pid means a crashed server is reported at once instead of after the full
# timeout; almost every startup failure is a crash, not a hang.
log "waiting up to ${BOOT_TIMEOUT}s for $BASE_URL"
if ! python3 "${SCRIPT_DIR}/cosmos3_client.py" \
        --wait "$BASE_URL" \
        --timeout "$BOOT_TIMEOUT" \
        --pid "$SERVER_PID"; then
    print_log_tail "$SERVER_LOG" 200
    fail "the Cosmos 3 server did not come up; see $SERVER_LOG"
fi
log "server ready on $BASE_URL"
