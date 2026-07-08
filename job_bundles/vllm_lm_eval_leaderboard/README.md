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

## Set up your farm

The fastest way to get a compatible farm is to deploy the [`cuda_farm`](../../cloudformation/farm_templates/cuda_farm) CloudFormation template. It provisions an NVIDIA-GPU service-managed fleet (A10G/L4) plus a queue with the Conda queue environment this bundle relies on. Once the stack reaches `CREATE_COMPLETE`, point the CLI at it:

```bash
deadline config set defaults.farm_id <FarmId from stack outputs>
deadline config set defaults.queue_id <CUDAQueueId from stack outputs>
```

This bundle has been verified end-to-end against the queue environment provisioned by `cuda_farm` with no modifications required.

**Already have a farm?** You need:
- An SMF fleet with NVIDIA GPUs, ≥32 GB RAM, ≥4 vCPU
- A queue with a Conda queue environment attached that reads `CondaPackages` and `CondaChannels` job parameters (any of the templates in [`queue_environments/`](../../queue_environments) named `conda_queue_env_*.yaml`)

A HuggingFace token is only needed for gated models (Llama, etc.).

### Service quotas

If your fleet doesn't scale up workers, the most common cause is an EC2 vCPU quota. GPU instance limits are per-region and per-instance-family, and may be capped below what you need on accounts that haven't previously launched these instances. Open the [Service Quotas console](https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas) under **EC2** and confirm you have headroom for:

- **Running On-Demand G and VT instances** — vCPU count, not instance count. The default 3-model run on `g5.xlarge` (4 vCPU each) needs ≥12 vCPU running concurrently.
- **All G and VT Spot Instance Requests** — only if your fleet uses spot.

Quota increases for these can take anywhere from minutes to a couple of business days, so request them before you submit.

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

The default list is a small, ungated, fast-loading mix that fits comfortably on a single A10G/L4: two models from the same family at different sizes (Qwen2.5 0.5B vs 1.5B) so you can see scaling within a family, plus one from a different family (Pythia 1.4B) at a comparable size so you can see cross-family differences. It's just a starting point; swap in whatever models you actually want to compare.

To add or remove models, edit the `range` list. Each entry becomes a task visible in the Monitor UI. Model IDs must be supported by vLLM (see the [vLLM supported models list](https://docs.vllm.ai/en/latest/models/supported_models.html)).

## Choosing benchmarks

The `Benchmarks` job parameter is a comma-separated list of lm-evaluation-harness task names. The default set is a standard **commonsense reasoning** suite, a well-known benchmark category that tests whether a model can apply everyday world knowledge (picking the most plausible continuation of a scenario, resolving an ambiguous pronoun, answering grade-school science questions). It's cheap to run and a reasonable smoke test for general capability:

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
