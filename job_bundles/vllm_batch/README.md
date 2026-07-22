# vLLM Batch Inference

This sample runs high-throughput LLM inference on a JSONL file of prompts using [vLLM](https://github.com/vllm-project/vllm) on AWS Deadline Cloud. Give it a file where every line is one prompt (say, 10,000 marketing slogans or 500 support-ticket replies to draft), pick a model, and the job fans out across a GPU fleet: every prompt gets an LLM response, and the aggregate step packages everything into a JSONL plus a self-contained HTML viewer you can open in any browser.

It's designed for offline, embarrassingly-parallel workloads: content generation, evaluation datasets, translation, extraction, classification, anywhere you need a model to answer many independent prompts without a live API server.

Under the hood it uses Deadline Cloud's [Task Chunking](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html) feature to group prompts into batched tasks, which lets you dial parallelism vs. scheduling overhead via a single `ChunkSize` parameter.

## How it works

```
┌──────────────────────────────────────────────────────────────────┐
│  Deadline Cloud Job                                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Step: Infer  (uses TASK_CHUNKING extension)                │  │
│  │                                                            │  │
│  │ Step Environment: VllmServer                               │  │
│  │   onEnter → start vLLM server (load model once per worker) │  │
│  │   onExit  → stop vLLM server                               │  │
│  │                                                            │  │
│  │ Tasks (1 per chunk of ChunkSize prompts):                  │  │
│  │   Task 1: prompts 1-5   → HTTP requests → result_1..5      │  │
│  │   Task 2: prompts 6-10  → HTTP requests → result_6..10     │  │
│  │   Task 3: prompts 11-15 → HTTP requests → result_11..15    │  │
│  │   ...                                                      │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Step: Aggregate                                            │  │
│  │  result_1 + result_2 + ... → output.jsonl                  │  │
│  │                             → results.html                 │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

Loading a 7B-parameter LLM takes 30+ seconds, so paying that cost per task would dominate batch runtime. Deadline Cloud's **step environments** solve this: the vLLM server starts when a worker picks up the job and stays loaded across every task that worker runs, then shuts down with the session. The **scheduler** fans tasks out across the fleet in parallel, and a **Service-Managed Fleet** auto-scales workers to match the size of the batch. A 24-prompt batch on a 4-worker fleet pays for 4 model loads instead of 24 and runs in parallel, with no infrastructure beyond `deadline bundle submit`.

## Set up your farm

The fastest way to get a compatible farm is to deploy the [`cuda_farm`](../../cloudformation/farm_templates/cuda_farm) CloudFormation template. Once the stack reaches `CREATE_COMPLETE`:

```bash
deadline config set defaults.farm_id <FarmId from stack outputs>
deadline config set defaults.queue_id <CUDAQueueId from stack outputs>
```

**Already have a farm?** You need:
- An SMF fleet with NVIDIA GPUs, ≥32 GB RAM
- A queue with a Conda queue environment attached that reads `CondaPackages` and `CondaChannels` job parameters

## Quick start

### GUI submitter (recommended)

```bash
deadline bundle gui-submit .
```

In the form:
1. Pick your input JSONL file
2. Set the **Prompt Range** (e.g. `1-10` for the first 10 prompts in the file)
3. Set the **Chunk Size** (how many prompts per task; default `5`)
4. Pick an output directory
5. Click Submit

### CLI submitter

```bash
deadline bundle submit . \
  --parameter InputFile=prompts.jsonl \
  --parameter Prompts=1-10 \
  --parameter ChunkSize=5 \
  --parameter OutputDir=$PWD/results
```

After completion:

```bash
deadline job download-output --job-id <job-id>

# All outputs land in an `output/` subfolder inside the directory you picked:
open results/output/results.html       # visual results viewer
cat results/output/output.jsonl        # raw JSONL output
```

The job always writes its files into an `output/` subfolder inside `OutputDir`, so the directory you pick stays uncluttered:

```
<OutputDir>/
└── output/
    ├── output.jsonl       # combined results, one JSON per line
    ├── results.html       # standalone visual viewer
    └── results/
        ├── result_1.jsonl
        ├── result_2.jsonl
        └── ...
```

## Prompt Range syntax

The `Prompts` parameter controls **which lines** from the JSONL file get processed. It accepts the full OpenJD integer range expression syntax:

| Value | What it does |
|---|---|
| `1-10` | Process the first 10 prompts (lines 1 through 10) |
| `2-8` | Process lines 2 through 8 |
| `2,5,8-9` | Process lines 2, 5, 8, and 9 |
| `1,3,5,7,9` | Process specific lines |
| `4,7` | Re-run only lines 4 and 7 (useful for retrying failed tasks) |
| `1-10:2` | Stride: every 2nd line starting at 1 → 1, 3, 5, 7, 9 |
| `1-3,7-15:3` | Combined: lines 1-3 plus every 3rd from 7-15 → 1, 2, 3, 7, 10, 13 |

The syntax gives you fine control. Process a subset for testing, retry only failed lines, or batch through different chunks of a large input file.

## Chunk size and adaptive sizing

The `ChunkSize` parameter controls **how many prompts each task processes together**. Deadline Cloud's [Task Chunking](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html) feature powers this behavior: the scheduler groups adjacent prompts into a single task, so one worker processes them consecutively without paying the task-scheduling overhead between each one.

Example: `Prompts=1-100` with `ChunkSize=10` creates 10 tasks. The first task processes prompts 1-10, the second processes 11-20, and so on.

| ChunkSize | Effect |
|---|---|
| `1` | 1 prompt per task (maximum parallelism, most scheduling overhead) |
| `5` (default) | Balanced, good for typical inference workloads |
| `20` | Fewer tasks, less overhead, more sequential work per worker |
| `150` (max) | One big task per worker (minimal scheduling, sequential processing) |

**Rule of thumb:** Set `ChunkSize` so that each chunk takes roughly 30-120 seconds to process. Too small and you waste time on task scheduling. Too large and slow prompts block fast ones from other workers.

### Adaptive sizing with `TargetRuntimeSeconds`

Rather than fixing the chunk size, you can let Deadline Cloud auto-tune it. Set `TargetRuntimeSeconds` to how long you want each chunk to take (default `120`s). The scheduler starts with your `ChunkSize` as the initial guess, observes how long chunks actually take, then grows or shrinks the chunk size on future tasks to hit the target.

- **Fast prompts** (short responses) → scheduler grows chunks to keep workers busy
- **Slow prompts** (long responses) → scheduler shrinks chunks to keep parallelism up
- Set `TargetRuntimeSeconds=0` to disable and always use exactly `ChunkSize` prompts per chunk

## Input format

A JSONL file with one JSON object per line. Each line must have a `prompt` field:

```jsonl
{"prompt": "What is photosynthesis?", "id": "001"}
{"prompt": "Write a haiku about clouds.", "id": "002"}
{"prompt": "Explain gravity to a 5 year old.", "id": "003", "max_tokens": 256, "temperature": 0.9}
```

Optional per-prompt fields:
- `id`: identifier for tracking (passed through to output)
- `max_tokens`: cap on the number of tokens vLLM will generate for this prompt's response. Higher = allows longer answers but each token adds latency and cost. If you hit the cap, `finish_reason` in the output is `"length"` (truncated) instead of `"stop"` (model decided it was done). Overrides the job-level `MaxTokens` default for just this line.
- `temperature`: how random the model's sampling is: `0.0` is fully deterministic (greedy decoding, same output every time), `0.7` is a balanced default, `1.5+` produces varied and creative but often less coherent output. Overrides the job-level `Temperature` default for just this line.

Any additional fields are passed through to the output unchanged.

### Prompt Builder GUI

A zero-dependency HTML tool is included for building input files:

```bash
open tools/prompt_builder.html
```

Add prompts, set per-prompt options, drag-and-drop to import, and export as JSONL.

## Output format

```jsonl
{"prompt": "What is photosynthesis?", "id": "001", "generated_text": "Photosynthesis is...", "finish_reason": "stop", "prompt_tokens": 7, "completion_tokens": 42}
```

The Aggregate step also produces `results.html`, a self-contained visual viewer you can open in any browser. No server needed.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| ModelName | `Qwen/Qwen2.5-7B-Instruct` | HuggingFace model ID |
| InputFile | _(required)_ | Path to input JSONL |
| OutputDir | _(required)_ | Directory for outputs |
| Prompts | `1-10` | Which lines from the JSONL to process (see syntax above) |
| ChunkSize | `5` | How many prompts per task (see chunk size section) |
| TargetRuntimeSeconds | `120` | Target seconds per chunk; scheduler auto-tunes ChunkSize toward this (0 disables) |
| MaxTokens | 512 | Default max output tokens per completion |
| Temperature | 0.7 | Default sampling temperature |
| MaxModelLen | 4096 | Max sequence length for vLLM |
| GpuMemoryUtilization | 0.90 | Fraction of GPU memory for KV cache |
| HfToken | _(empty)_ | HuggingFace token for gated models |

**Gated models** (like Llama): Leave `HfToken` empty if your model is public. If your model requires authentication, paste your HuggingFace token here. It works but is stored in plaintext. For a more secure setup, set `HF_TOKEN` in your queue environment instead.

## How scaling works

- Each **task** processes a chunk of `ChunkSize` prompts
- The **fleet** determines how many workers are available
- The **scheduler** assigns chunks to workers as they become free
- The **step environment** ensures the vLLM model loads once per worker session, not once per chunk

Example: 100 prompts, `ChunkSize=10`, fleet with 5 workers → 10 chunks, 5 workers process 2 chunks each in parallel. Model loads 5 times total (once per worker). Total time ≈ model load + (100 / 5 workers) × per-prompt time.

## References

- [vLLM](https://github.com/vllm-project/vllm)
- [Deadline Cloud Task Chunking](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html)
- [Open Job Description Environments](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#4-environment)
