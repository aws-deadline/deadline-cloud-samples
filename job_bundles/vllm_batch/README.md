# vLLM Batch Inference

Run high-throughput LLM inference on a JSONL file of prompts using [vLLM](https://github.com/vllm-project/vllm) on AWS Deadline Cloud. Each line in the JSONL becomes one task — the scheduler distributes tasks across available GPU workers, with the model loaded once per worker and reused across all tasks on that worker.

## How it works

```
┌─────────────────────────────────────────────────────────┐
│  Deadline Cloud Job                                     │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step: Infer                                       │  │
│  │                                                   │  │
│  │ Step Environment: VllmServer                      │  │
│  │   onEnter → start vLLM server (load model once)   │  │
│  │   onExit  → stop vLLM server                      │  │
│  │                                                   │  │
│  │ Tasks (1 per selected line, run in parallel):     │  │
│  │   Task 1: line 1 → HTTP request → result_1        │  │
│  │   Task 2: line 2 → HTTP request → result_2        │  │
│  │   ...                                             │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step: Aggregate                                   │  │
│  │  result_1 + result_2 + ... → output.jsonl         │  │
│  │                             → results.html        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The model loads once when a worker starts a session. The scheduler then feeds tasks to that worker one at a time — each task sends a single HTTP request to the local vLLM server. When the session ends, the server shuts down. If the fleet has 4 workers and there are 24 prompts, each worker processes ~6 prompts without ever reloading the model.

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
3. Pick an output directory
4. Click Submit

### CLI submitter

```bash
deadline bundle submit . \
  --parameter InputFile=prompts.jsonl \
  --parameter Prompts=1-10 \
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

The `Prompts` parameter controls **which lines** from the JSONL file get processed as tasks. Examples:

| Value | What it does |
|---|---|
| `1-10` | Process the first 10 prompts (lines 1 through 10) |
| `2-8` | Process lines 2 through 8 |
| `2,5,8-9` | Process lines 2, 5, 8, and 9 |
| `1,3,5,7,9` | Process odd-numbered lines |
| `4,7` | Re-run only lines 4 and 7 (useful for retrying failed tasks) |

This gives you fine control: process a subset for testing, retry only failed lines, or batch through different chunks of a large input file.

## Input format

A JSONL file with one JSON object per line. Each line must have a `prompt` field:

```jsonl
{"prompt": "What is photosynthesis?", "id": "001"}
{"prompt": "Write a haiku about clouds.", "id": "002"}
{"prompt": "Explain gravity to a 5 year old.", "id": "003", "max_tokens": 256, "temperature": 0.9}
```

Optional per-prompt fields:
- `id` — identifier for tracking (passed through to output)
- `max_tokens` — override the job-level default for this prompt
- `temperature` — override the job-level default for this prompt

Any additional fields are passed through to the output unchanged.

### Prompt Builder GUI

A zero-dependency HTML tool is included for building input files:

```bash
open tools/prompt_builder.html
```

Add prompts dynamically, set per-prompt options, drag-and-drop to import, and export as JSONL.

## Output format

```jsonl
{"prompt": "What is photosynthesis?", "id": "001", "generated_text": "Photosynthesis is...", "finish_reason": "stop", "prompt_tokens": 7, "completion_tokens": 42}
```

The Aggregate step also produces `results.html` — a self-contained visual viewer you can open in any browser. No server needed.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| ModelName | `Qwen/Qwen2.5-7B-Instruct` | HuggingFace model ID |
| InputFile | _(required)_ | Path to input JSONL |
| OutputDir | _(required)_ | Directory for outputs |
| Prompts | `1-10` | Which lines from the JSONL to process (see syntax above) |
| MaxTokens | 512 | Default max output tokens per completion |
| Temperature | 0.7 | Default sampling temperature |
| MaxModelLen | 4096 | Max sequence length for vLLM |
| GpuMemoryUtilization | 0.90 | Fraction of GPU memory for KV cache |
| HfToken | _(empty)_ | HuggingFace token for gated models |

## How scaling works

- Each **task** = 1 prompt
- The **fleet** determines how many workers are available
- The **scheduler** assigns tasks to workers as they become free
- The **step environment** ensures the model loads once per worker, not once per task

Example: 100 prompts on a fleet with max 5 workers → 5 models load in parallel, each worker processes ~20 prompts sequentially, total time ≈ model load + (100/5) × per-prompt time.

## References

- [vLLM](https://github.com/vllm-project/vllm)
- [Open Job Description Environments](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#4-environment)
