#!/usr/bin/env bash
# Tests for serve_cosmos3.sh's preflight guards, in both directions.
#
#   bash scripts/test_serve_cosmos3.sh
#
# The script runs inside the queue environment's container, so these tests stub
# the things that container is expected to provide: `vllm` and `nvidia-smi`. The
# GPU-memory decision is the guard most likely to matter and the one that cannot
# be exercised on a machine without a GPU, because a service-managed fleet
# publishes no GPU-memory capability and a task can land on a card too small to
# hold the model.
#
# A stub `vllm` that exits immediately also covers the crash-on-startup path,
# which is how an out-of-memory server actually fails.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/serve_cosmos3.sh"
STUBS="$(mktemp -d)"
WORK="$(mktemp -d)"
trap 'rm -rf "$STUBS" "$WORK"' EXIT

PASS=0
FAIL=0

# Keep python3 reachable: the script shells out to cosmos3_client.py for the
# health probe, and PATH is replaced wholesale in each case.
REAL_PATH="$PATH"

make_nvidia_smi() {
    # $1 = reported GPU memory in MiB, $2 = reported GPU name
    cat > "$STUBS/nvidia-smi" <<EOF
#!/usr/bin/env bash
for arg in "\$@"; do
    case "\$arg" in
        --query-gpu=name) echo "$2"; exit 0 ;;
        --query-gpu=memory.total) echo "$1"; exit 0 ;;
    esac
done
echo "$2, $1"
EOF
    chmod +x "$STUBS/nvidia-smi"
}

make_nvidia_smi_multi() {
    # $1 = GPU count, $2 = memory MiB each
    cat > "$STUBS/nvidia-smi" <<EOF
#!/usr/bin/env bash
for arg in "\$@"; do
    case "\$arg" in
        --query-gpu=index) seq 0 \$(( $1 - 1 )); exit 0 ;;
        --query-gpu=name) for i in \$(seq 1 $1); do echo "NVIDIA L40S"; done; exit 0 ;;
        --query-gpu=memory.total) for i in \$(seq 1 $1); do echo "$2"; done; exit 0 ;;
    esac
done
EOF
    chmod +x "$STUBS/nvidia-smi"
}

make_nvidia_smi_no_gpu() {
    cat > "$STUBS/nvidia-smi" <<'EOF'
#!/usr/bin/env bash
# What a container started without working GPU access actually produces.
echo "No devices were found" >&2
exit 0
EOF
    chmod +x "$STUBS/nvidia-smi"
}

# A vllm that exits at once, so the health wait reports a dead process rather
# than waiting out the timeout.
make_vllm_that_dies() {
    cat > "$STUBS/vllm" <<'EOF'
#!/usr/bin/env bash
echo "stub vllm: torch.OutOfMemoryError: CUDA out of memory" >&2
exit 1
EOF
    chmod +x "$STUBS/vllm"
}

run_case() {
    local label="$1" expect="$2" needle="$3"
    shift 3
    local out rc
    out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" bash "$SCRIPT" "$@" 2>&1)
    rc=$?
    if [ "$expect" = "fail" ] && [ "$rc" -eq 0 ]; then
        echo "FAIL  $label: expected a non-zero exit, got 0"
        printf '%s\n' "$out" | sed 's/^/        /'
        FAIL=$((FAIL + 1))
        return
    fi
    if [ "$expect" = "pass" ] && [ "$rc" -ne 0 ]; then
        echo "FAIL  $label: expected exit 0, got $rc"
        printf '%s\n' "$out" | sed 's/^/        /'
        FAIL=$((FAIL + 1))
        return
    fi
    if ! printf '%s' "$out" | grep -q -- "$needle"; then
        echo "FAIL  $label: output did not contain '$needle'"
        printf '%s\n' "$out" | sed 's/^/        /'
        FAIL=$((FAIL + 1))
        return
    fi
    echo "ok    $label"
    PASS=$((PASS + 1))
}

START=(start model 5 auto 40000 "$WORK/logs" "$WORK/sess")

echo "== argument handling"
run_case "unknown action is rejected" fail "unknown action 'bogus'" bogus
run_case "stop without a pid is a no-op" pass "nothing to stop" stop

echo ""
echo "== container preflight"
make_nvidia_smi 46068 "NVIDIA L40S"
run_case "a missing vllm is reported, naming the Omni requirement" fail \
    "vllm is not on PATH inside the container" "${START[@]}"

make_vllm_that_dies
rm -f "$STUBS/nvidia-smi"
run_case "a missing nvidia-smi is reported" fail \
    "nvidia-smi is not on PATH inside the container" "${START[@]}"

make_nvidia_smi_no_gpu
run_case "nvidia-smi reporting no GPU is caught before the model loads" fail \
    "nvidia-smi reported no GPU" "${START[@]}"

echo ""
echo "== GPU memory and offload mode"
make_vllm_that_dies

make_nvidia_smi 23028 "NVIDIA L4"
run_case "auto on a 24 GB GPU enables offload" fail \
    "below the 40000 MiB floor; enabling --enable-layerwise-offload" \
    start model 5 auto 40000 "$WORK/logs" "$WORK/sess"
run_case "never on a 24 GB GPU fails the session" fail \
    "OffloadMode=never forbids the workaround" \
    start model 5 never 40000 "$WORK/logs" "$WORK/sess"

make_nvidia_smi 46068 "NVIDIA L40S"
run_case "auto on a 48 GB GPU skips offload" fail \
    "at or above the 40000 MiB floor; no offload" \
    start model 5 auto 40000 "$WORK/logs" "$WORK/sess"
run_case "always enables offload regardless of memory" fail \
    "OffloadMode=always" \
    start model 5 always 40000 "$WORK/logs" "$WORK/sess"
run_case "an invalid offload mode is rejected" fail \
    "OffloadMode must be auto, always or never" \
    start model 5 sometimes 40000 "$WORK/logs" "$WORK/sess"

echo ""
echo "== host memory when offloading"
# Layerwise offload keeps the ~35 GB checkpoint in HOST memory, so a worker that
# satisfies the step's GPU requirement can still be far too small. The real
# failure was an OOM-killed diffusion worker 515s into startup on a 61 GiB
# g6e.2xlarge, surfaced only as "EOFError / Orchestrator initialization failed".
# The same parameters succeeded on a 384 GiB g6e.12xlarge.
#
# COSMOS3_MEMINFO lets this run off Linux, where /proc/meminfo is absent and the
# guard would otherwise only ever take its skip path.
printf 'MemTotal:       64321024 kB\n'  > "$WORK/meminfo-small"
printf 'MemTotal:      394321024 kB\n' > "$WORK/meminfo-large"
printf 'NotMemTotal: 1\n'              > "$WORK/meminfo-garbage"

mem_case() {
    local label="$1" expect="$2" needle="$3" meminfo="$4" mode="$5"
    local out
    out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" COSMOS3_MEMINFO="$meminfo" \
          bash "$SCRIPT" start model 3 "$mode" 40000 "$WORK/ml" "$WORK/ms" 2>&1)
    if printf '%s' "$out" | grep -q -- "$needle"; then
        echo "ok    $label"; PASS=$((PASS + 1))
    else
        echo "FAIL  $label"; printf '%s\n' "$out" | sed 's/^/        /' | head -5
        FAIL=$((FAIL + 1))
    fi
}

make_nvidia_smi 46068 "NVIDIA L40S"
make_vllm_that_dies
mem_case "a 62 GiB host is rejected before the model loads" fail \
    "below the 98304 MiB this needs" "$WORK/meminfo-small" always
mem_case "a 376 GiB host passes the offload floor" fail \
    "at or above the 98304 MiB offload floor" "$WORK/meminfo-large" always
mem_case "unreadable meminfo warns rather than failing" fail \
    "could not read MemTotal" "$WORK/meminfo-garbage" always
mem_case "missing meminfo warns rather than failing" fail \
    "could not read MemTotal" "/nonexistent/meminfo" always
# With offload off the weights stay on the GPU, so host memory is irrelevant.
out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" COSMOS3_MEMINFO="$WORK/meminfo-small" \
      bash "$SCRIPT" start model 3 never 40000 "$WORK/nl" "$WORK/ns" 2>&1)
if printf '%s' "$out" | grep -q "offload floor\|below the 98304"; then
    echo "FAIL  no host-memory check when OffloadMode=never"; FAIL=$((FAIL + 1))
else
    echo "ok    no host-memory check when OffloadMode=never"; PASS=$((PASS + 1))
fi

echo ""
echo "== startup failure reporting"
run_case "a server that exits during startup is reported at once" fail \
    "exited during startup" "${START[@]}"
run_case "the server log tail is printed on a startup failure" fail \
    "CUDA out of memory" "${START[@]}"
run_case "the env var contract is published before the wait" fail \
    "openjd_env: COSMOS3_BASE_URL=http://127.0.0.1:8000" "${START[@]}"

echo ""
echo "== weight cache"
run_case "an unset HF_HOME warns rather than failing silently" fail \
    "HF_HOME is unset" "${START[@]}"

UNWRITABLE="$WORK/unwritable-cache"
mkdir -p "$UNWRITABLE"
chmod 500 "$UNWRITABLE"
if [ -w "$UNWRITABLE" ]; then
    echo "skip  an unwritable HF_HOME is reported (running as a user that ignores the mode)"
else
    out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" HF_HOME="$UNWRITABLE" \
        bash "$SCRIPT" "${START[@]}" 2>&1)
    if printf '%s' "$out" | grep -q "is not writable by"; then
        echo "ok    an unwritable HF_HOME is reported"
        PASS=$((PASS + 1))
    else
        echo "FAIL  an unwritable HF_HOME is reported"
        printf '%s\n' "$out" | sed 's/^/        /'
        FAIL=$((FAIL + 1))
    fi
fi
chmod 700 "$UNWRITABLE"

echo ""
echo "== stop"
out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" \
    COSMOS3_SERVER_PID=999999 COSMOS3_SERVER_LOG="$WORK/absent.log" \
    bash "$SCRIPT" stop 2>&1)
if printf '%s' "$out" | grep -q "already gone"; then
    echo "ok    stopping an exited server is not an error"
    PASS=$((PASS + 1))
else
    echo "FAIL  stopping an exited server is not an error"
    printf '%s\n' "$out" | sed 's/^/        /'
    FAIL=$((FAIL + 1))
fi

printf 'server line one\nserver line two\n' > "$WORK/tail.log"
out=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" \
    COSMOS3_SERVER_LOG="$WORK/tail.log" bash "$SCRIPT" stop 2>&1)
if printf '%s' "$out" | grep -q "server line two"; then
    echo "ok    stop prints the server log tail even on the success path"
    PASS=$((PASS + 1))
else
    echo "FAIL  stop prints the server log tail even on the success path"
    printf '%s\n' "$out" | sed 's/^/        /'
    FAIL=$((FAIL + 1))
fi

echo ""
echo "== GPU claim on a multi-GPU worker"
make_vllm_that_dies
make_nvidia_smi_multi 4 46068
CLAIMS="$WORK/cache/gpu-claims"
mkdir -p "$WORK/cache"   # the queue environment bind-mounts this; it always exists in production

# Two live sessions must get different indices.
S1="$WORK/sessA"; S2="$WORK/sessB"; mkdir -p "$S1" "$S2"
O1=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
     bash "$SCRIPT" start model 3 auto 40000 "$WORK/l1" "$S1" 2>&1)
O2=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
     bash "$SCRIPT" start model 3 auto 40000 "$WORK/l2" "$S2" 2>&1)
G1=$(printf '%s' "$O1" | sed -n 's/.*claimed GPU index \([0-9]*\) .*/\1/p' | head -1)
G2=$(printf '%s' "$O2" | sed -n 's/.*claimed GPU index \([0-9]*\) .*/\1/p' | head -1)
if [ -n "$G1" ] && [ -n "$G2" ] && [ "$G1" != "$G2" ]; then
    echo "ok    concurrent sessions claim different GPUs ($G1 and $G2)"
    PASS=$((PASS + 1))
else
    echo "FAIL  concurrent sessions claim different GPUs (got '$G1' and '$G2')"
    FAIL=$((FAIL + 1))
fi
if printf '%s' "$O1" | grep -q "CUDA_VISIBLE_DEVICES=$G1"; then
    echo "ok    the claim is exported as CUDA_VISIBLE_DEVICES"
    PASS=$((PASS + 1))
else
    echo "FAIL  the claim is exported as CUDA_VISIBLE_DEVICES"; FAIL=$((FAIL + 1))
fi

# A claim whose heartbeat has stopped must be reclaimed. Staleness used to be
# decided by testing whether the peer's session directory still existed, which
# is invisible from another container, so every claim looked reclaimable.
rm -rf "$CLAIMS"; mkdir -p "$CLAIMS/0"
printf '%s\n' "$WORK/someone" > "$CLAIMS/0/owner"
touch -t 202001010000 "$CLAIMS/0/heartbeat"
O3=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
     bash "$SCRIPT" start model 3 auto 40000 "$WORK/l3" "$WORK/sessC" 2>&1)
if printf '%s' "$O3" | grep -q "has no heartbeat in the last"; then
    echo "ok    a claim with a stopped heartbeat is reclaimed"
    PASS=$((PASS + 1))
else
    echo "FAIL  a claim with a stopped heartbeat is reclaimed"
    printf '%s\n' "$O3" | sed 's/^/        /' | head -6
    FAIL=$((FAIL + 1))
fi

# A fresh heartbeat must NOT be reclaimed, which is the other direction.
rm -rf "$CLAIMS"; mkdir -p "$CLAIMS/0"
printf '%s\n' "$WORK/someone" > "$CLAIMS/0/owner"; touch "$CLAIMS/0/heartbeat"
O3b=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
      bash "$SCRIPT" start model 3 auto 40000 "$WORK/l3b" "$WORK/sessC2" 2>&1)
if printf '%s' "$O3b" | grep -qE "claimed GPU index [123] "; then
    echo "ok    a live claim is left alone and another index is taken"
    PASS=$((PASS + 1))
else
    echo "FAIL  a live claim is left alone and another index is taken"
    printf '%s\n' "$O3b" | sed 's/^/        /' | head -6
    FAIL=$((FAIL + 1))
fi

# All GPUs held by live sessions must fail rather than oversubscribe.
rm -rf "$CLAIMS"; mkdir -p "$CLAIMS"
for i in 0 1 2 3; do mkdir -p "$CLAIMS/$i"; printf '%s\n' "$WORK" > "$CLAIMS/$i/owner"
    touch "$CLAIMS/$i/heartbeat"; done
O4=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
     bash "$SCRIPT" start model 3 auto 40000 "$WORK/l4" "$WORK/sessD" 2>&1)
if printf '%s' "$O4" | grep -q "all 4 GPUs on this worker are claimed"; then
    echo "ok    a fully claimed worker fails instead of oversubscribing"
    PASS=$((PASS + 1))
else
    echo "FAIL  a fully claimed worker fails instead of oversubscribing"; FAIL=$((FAIL + 1))
fi

# stop releases only a claim this session owns.
rm -rf "$CLAIMS"; mkdir -p "$CLAIMS/2"; printf '%s\n' "$WORK/mine" > "$CLAIMS/2/owner"
(cd "$WORK" && PATH="$STUBS:$REAL_PATH" COSMOS3_GPU_CLAIM="$CLAIMS/2" \
    bash "$SCRIPT" stop "$WORK/mine" >/dev/null 2>&1)
if [ ! -d "$CLAIMS/2" ]; then
    echo "ok    stop releases the session's own claim"; PASS=$((PASS + 1))
else
    echo "FAIL  stop releases the session's own claim"; FAIL=$((FAIL + 1))
fi
mkdir -p "$CLAIMS/3"; printf '%s\n' "$WORK/someone-else" > "$CLAIMS/3/owner"
(cd "$WORK" && PATH="$STUBS:$REAL_PATH" COSMOS3_GPU_CLAIM="$CLAIMS/3" \
    bash "$SCRIPT" stop "$WORK/mine" >/dev/null 2>&1)
if [ -d "$CLAIMS/3" ]; then
    echo "ok    stop leaves another session's reassigned claim alone"; PASS=$((PASS + 1))
else
    echo "FAIL  stop leaves another session's reassigned claim alone"; FAIL=$((FAIL + 1))
fi

# A single-GPU worker must not claim at all.
make_nvidia_smi 46068 "NVIDIA L40S"
O5=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/cache" \
     bash "$SCRIPT" start model 3 auto 40000 "$WORK/l5" "$WORK/sessE" 2>&1)
if printf '%s' "$O5" | grep -q "single-GPU worker; no claim needed"; then
    echo "ok    a single-GPU worker skips the claim"; PASS=$((PASS + 1))
else
    echo "FAIL  a single-GPU worker skips the claim"; FAIL=$((FAIL + 1))
fi

echo ""
echo "== a multi-GPU worker with no shared claim directory"
# The regression this guards. MODEL_CACHE_DIR is only set by these tests, and the
# queue environment exports HF_HOME, so the old fallback to /var/tmp was private
# to each container. Every session then claimed index 0 and the servers all
# loaded onto one GPU.
make_nvidia_smi_multi 4 46068
make_vllm_that_dies
OUT=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" env -u MODEL_CACHE_DIR -u HF_HOME \
        bash "$SCRIPT" start model 3 auto 40000 "$WORK/nosh-l" "$WORK/nosh-s" 2>&1)
if printf '%s' "$OUT" | grep -q "needs a directory every session can see"; then
    echo "ok    a multi-GPU worker refuses without a shared claim directory"
    PASS=$((PASS + 1))
else
    echo "FAIL  a multi-GPU worker refuses without a shared claim directory"
    printf '%s\n' "$OUT" | sed 's/^/        /' | head -5
    FAIL=$((FAIL + 1))
fi
# HF_HOME alone is enough, because that is what production sets.
mkdir -p "$WORK/hfshare"
OUT=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" env -u MODEL_CACHE_DIR HF_HOME="$WORK/hfshare" \
        bash "$SCRIPT" start model 3 auto 40000 "$WORK/hf-l" "$WORK/hf-s" 2>&1)
if printf '%s' "$OUT" | grep -q "claimed GPU index 0 of 4"; then
    echo "ok    HF_HOME serves as the shared claim directory"
    PASS=$((PASS + 1))
else
    echo "FAIL  HF_HOME serves as the shared claim directory"
    printf '%s\n' "$OUT" | sed 's/^/        /' | head -5
    FAIL=$((FAIL + 1))
fi

echo ""
echo "== SIGPIPE regression (multi-GPU hosts)"
# `producer | head -1` under `set -o pipefail` kills the script with exit 141 and
# NO output when the producer writes more than head consumes. That made the
# script's behaviour depend on GPU count: invisible on a 1-GPU worker, fatal on
# a 4-GPU one. The stub emits many lines so the race is deterministic.
cat > "$STUBS/nvidia-smi" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
    case "$a" in
        --query-gpu=index) seq 0 3; exit 0 ;;
        --query-gpu=name) for i in $(seq 1 20000); do echo "NVIDIA L40S"; done; exit 0 ;;
        --query-gpu=memory.total) for i in $(seq 1 20000); do echo "46068"; done; exit 0 ;;
    esac
done
EOF
chmod +x "$STUBS/nvidia-smi"
make_vllm_that_dies
mkdir -p "$WORK/sp-cache"
OUT=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" MODEL_CACHE_DIR="$WORK/sp-cache" \
        bash "$SCRIPT" start model 3 auto 40000 "$WORK/sp-logs" "$WORK/sp-sess" 2>&1)
if printf '%s' "$OUT" | grep -q "GPU: NVIDIA L40S with 46068 MiB"; then
    echo "ok    a many-line nvidia-smi does not SIGPIPE the script"
    PASS=$((PASS + 1))
else
    echo "FAIL  a many-line nvidia-smi does not SIGPIPE the script"
    printf '%s\n' "$OUT" | sed 's/^/        /' | head -5
    FAIL=$((FAIL + 1))
fi
if printf '%s' "$OUT" | grep -q "claimed GPU index 0 of 4"; then
    echo "ok    the GPU claim still works on a 4-GPU host"
    PASS=$((PASS + 1))
else
    echo "FAIL  the GPU claim still works on a 4-GPU host"; FAIL=$((FAIL + 1))
fi

echo ""
echo "== container identity for an unknown uid"
# torch._inductor derives a cache path from getpass.getuser() at import time.
# `docker exec` starts a clean environment and the host uid has no passwd entry
# in the image, so without these the import dies with
#   KeyError: 'getpwuid(): uid not found: 1001'
# Setting LOGNAME/USER fixes every call site; the cache variables alone do not,
# because codecache calls default_cache_dir() directly.
make_nvidia_smi 46068 "NVIDIA L40S"
make_vllm_that_dies
OUT=$(cd "$WORK" && PATH="$STUBS:$REAL_PATH" env -u LOGNAME -u USER -u LNAME -u USERNAME \
        bash "$SCRIPT" start model 3 auto 40000 "$WORK/id-logs" "$WORK/id-sess" 2>&1)
for probe in "USER=container-" "HOME=$WORK/id-sess/cosmos3-cache/home"; do
    if printf '%s' "$OUT" | grep -q -- "$probe"; then
        echo "ok    sets $probe"; PASS=$((PASS + 1))
    else
        echo "FAIL  sets $probe"
        printf '%s\n' "$OUT" | sed 's/^/        /' | head -4
        FAIL=$((FAIL + 1))
    fi
done
# The identity must be set BEFORE vllm is launched, or the import still dies.
IDENT_LINE=$(printf '%s' "$OUT" | grep -n "running as uid" | head -1 | cut -d: -f1)
SERVE_LINE=$(printf '%s' "$OUT" | grep -n "serve args" | head -1 | cut -d: -f1)
if [ -n "$IDENT_LINE" ] && [ -n "$SERVE_LINE" ] && [ "$IDENT_LINE" -lt "$SERVE_LINE" ]; then
    echo "ok    identity is set before vllm launches"; PASS=$((PASS + 1))
else
    echo "FAIL  identity is set before vllm launches (ident=$IDENT_LINE serve=$SERVE_LINE)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
