#!/bin/bash
# Evaluate one model against all benchmarks.
#
# Starts vLLM for the given model, runs every benchmark in the list against
# the local vLLM endpoint via lm-evaluation-harness's local-completions model
# type, then stops vLLM.
#
# Args:
#   $1 - HuggingFace model ID (e.g. Qwen/Qwen2.5-0.5B)
#   $2 - Comma-separated benchmark task names (e.g. "hellaswag,arc_easy")
#   $3 - Results output directory
#   $4 - Number of concurrent lm_eval requests
#   $5 - GPU memory utilization fraction
#   $6 - Max model length
#   $7 - HuggingFace token (may be empty)
#   $8 - Session working directory
set -euo pipefail

MODEL="$1"
BENCHMARKS="$2"
RESULTS_DIR="$3"
NUM_CONCURRENT="$4"
GPU_MEM_UTIL="$5"
MAX_MODEL_LEN="$6"
HF_TOKEN_ARG="$7"
SESSION_DIR="$8"

[ -n "$HF_TOKEN_ARG" ] && export HF_TOKEN="$HF_TOKEN_ARG"
mkdir -p "$RESULTS_DIR"

VLLM_LOG="$SESSION_DIR/vllm_server.log"

# Make sure vLLM is killed even if a benchmark fails.
cleanup() {
  if [ -n "${VLLM_PID:-}" ] && kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "Stopping vLLM (PID $VLLM_PID)..."
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "Starting vLLM server for $MODEL..."
START_TS=$(date +%s)
nohup python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" --dtype auto --port 8000 \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
  --max-model-len "$MAX_MODEL_LEN" \
  > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!

# Poll /v1/models until the server is ready (max 15 minutes).
# Stream new vLLM log lines to stdout every 30s so progress is visible in
# the Deadline Cloud Monitor UI while the model loads and compiles.
MAX_WAIT=900
LAST_LOG_LINES=0
READY=0
for i in $(seq 1 $((MAX_WAIT / 5))); do
  if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    echo "ERROR: vLLM server exited unexpectedly after $(( $(date +%s) - START_TS ))s"
    tail -100 "$VLLM_LOG"
    exit 1
  fi
  if curl -sf http://localhost:8000/v1/models > /dev/null; then
    echo "vLLM ready after $(( $(date +%s) - START_TS ))s"
    READY=1
    break
  fi
  if [ $((i % 6)) -eq 0 ]; then
    CURRENT_LINES=$(wc -l < "$VLLM_LOG" 2>/dev/null || echo 0)
    if [ "$CURRENT_LINES" -gt "$LAST_LOG_LINES" ]; then
      tail -n $((CURRENT_LINES - LAST_LOG_LINES)) "$VLLM_LOG" | tail -10
      LAST_LOG_LINES=$CURRENT_LINES
    fi
  fi
  sleep 5
done
if [ "$READY" -ne 1 ]; then
  echo "ERROR: vLLM did not become ready within ${MAX_WAIT}s"
  tail -100 "$VLLM_LOG"
  exit 1
fi

# Run each benchmark against the running vLLM daemon.
IFS=',' read -ra BENCH_ARR <<< "$BENCHMARKS"
for BENCH in "${BENCH_ARR[@]}"; do
  BENCH=$(echo "$BENCH" | xargs)
  echo "== Running $BENCH on $MODEL =="
  lm_eval --model local-completions \
    --model_args "model=$MODEL,base_url=http://localhost:8000/v1/completions,num_concurrent=$NUM_CONCURRENT,max_retries=5,tokenized_requests=False" \
    --tasks "$BENCH" \
    --output_path "$RESULTS_DIR"
done

echo "All benchmarks complete for $MODEL"
