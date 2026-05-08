# vLLM LLM Leaderboard (Matrix Evaluation)

Evaluate **multiple LLMs × multiple benchmarks** in a single Deadline Cloud job. Each model becomes one task in a parameter sweep; tasks run in parallel across workers. A final step aggregates the per-model results into a ranked leaderboard.

## How it works

```
┌─────────────────────────────────────────────────────┐
│  Deadline Cloud Job                                 │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ Step: EvalModels                              │  │
│  │ parameterSpace: ModelName                     │  │
│  │                                               │  │
│  │  Task 1: Qwen/Qwen2.5-0.5B                    │  │
│  │  Task 2: Qwen/Qwen2.5-1.5B                    │  │
│  │  Task 3: EleutherAI/pythia-1.4b               │  │
│  └──────────────────────┬────────────────────────┘  │
│                         ▼                           │
│  ┌───────────────────────────────────────────────┐  │
│  │ Step: Aggregate                               │  │
│  │  → leaderboard.csv + leaderboard.md           │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Each task in `EvalModels` runs one model end-to-end: starts a local [vLLM](https://github.com/vllm-project/vllm) server, runs every benchmark via [EleutherAI's lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) against the local endpoint, then stops vLLM. Models load directly from HuggingFace Hub — no job attachments needed.

## Prerequisites

- GPU fleet (CUDA 12.x)
- Queue with a Conda queue environment configured — see the [queue environment samples](../../queue_environments) and the [create a queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html) docs. The bundle passes `CondaPackages` and `CondaChannels` parameters to it.
- HuggingFace token for gated models (optional)

## Quick start

```bash
deadline bundle submit ./job_bundles/vllm_lm_eval_leaderboard/ \
  --parameter MaxModelLen=2048
```

After completion:

```bash
deadline job download-output --job-id <job-id>
cat leaderboard_results/leaderboard.md
```

Example output:

```markdown
# LLM Leaderboard

Models: 3 | Benchmarks: arc_challenge, arc_easy, hellaswag, winogrande

| Rank | Model                  | arc_challenge | arc_easy | hellaswag | winogrande | Mean   |
|------|------------------------|---------------|----------|-----------|------------|--------|
| 1    | Qwen/Qwen2.5-1.5B      | 0.4497        | 0.7176   | 0.6775    | 0.6322     | 0.6192 |
| 2    | Qwen/Qwen2.5-0.5B      | 0.3200        | 0.5816   | 0.5223    | 0.5691     | 0.4982 |
| 3    | EleutherAI/pythia-1.4b | 0.2833        | 0.5387   | 0.5201    | 0.5730     | 0.4788 |
```

## Changing the model list

Models are a STRING parameter space on the `EvalModels` step in `template.yaml`:

```yaml
parameterSpace:
  taskParameterDefinitions:
  - name: ModelName
    type: STRING
    range:
    - "Qwen/Qwen2.5-0.5B"
    - "Qwen/Qwen2.5-1.5B"
    - "EleutherAI/pythia-1.4b"
```

To add or remove models, edit the `range` list. Each entry becomes a task visible in the Monitor UI. Model IDs must be supported by vLLM (see the [vLLM supported models list](https://docs.vllm.ai/en/latest/models/supported_models.html)).

## Choosing benchmarks

The `Benchmarks` job parameter is a comma-separated list of lm-evaluation-harness task names. Default covers commonsense reasoning:

```
hellaswag,arc_easy,arc_challenge,winogrande
```

Override at submit time:

```bash
deadline bundle submit ./job_bundles/vllm_lm_eval_leaderboard/ \
  --parameter Benchmarks="hellaswag,mmlu,gsm8k"
```

All benchmarks in the list run sequentially against each model's vLLM server. Keep `MaxModelLen` ≤ the smallest model's context window.

## References

- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
- [vLLM](https://github.com/vllm-project/vllm)
