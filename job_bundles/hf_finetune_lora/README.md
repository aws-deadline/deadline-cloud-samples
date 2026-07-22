# HuggingFace LLM Fine-Tuning (LoRA / QLoRA)

Fine-tune any HuggingFace causal language model with LoRA or QLoRA on a custom
instruction dataset, using AWS Deadline Cloud's GPU workers.

This bundle uses [transformers](https://github.com/huggingface/transformers),
[PEFT](https://github.com/huggingface/peft), and [bitsandbytes](https://github.com/TimDettmers/bitsandbytes)
to perform parameter-efficient fine-tuning. The output is a small LoRA adapter
(~50-200 MB). Load it on top of the base model to change how the model behaves.
Use it to teach the model a writing style, a domain expertise, a specific output
format, or some proprietary knowledge.

## How it works

1. **Prepare a dataset**: JSONL file with `instruction` and `output` fields, uploaded to S3
2. **Submit a Deadline Cloud job**: the worker downloads the dataset and installs the HF stack, then runs QLoRA fine-tuning
3. **Download the adapter**: via `deadline job download-output`
4. **Load locally**: combine the adapter with the base model for inference

```
┌──────────────┐                ┌──────────────────────┐                ┌──────────────┐
│ Your dataset │ ──── S3 ────>  │ Deadline Cloud GPU   │ ── adapter ──> │ Local laptop │
│ JSONL file   │                │ worker (L4 / A10G /  │                │ HF inference │
│              │                │ A100, etc.)          │                │              │
└──────────────┘                └──────────────────────┘                └──────────────┘
```

## Prerequisites

- An AWS Deadline Cloud farm with a **GPU-enabled queue** (Linux fleet, NVIDIA GPU with 16 GB+ VRAM)
- [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) installed
- A dataset in JSONL format uploaded to an S3 bucket the queue role can read
- (Optional) A HuggingFace token, only needed if you repoint the bundle at a gated model (e.g. Llama, Gemma). All models in the dropdown are public.

### Fleet recommendations

| Model size | Min VRAM (QLoRA 4-bit) | Suggested EC2 instance |
|---|---|---|
| 0.5B - 1.5B | 8 GB | g5.xlarge (A10G) or larger |
| 3B - 7B | 12 GB | g5.2xlarge (A10G), g6.xlarge (L4) |
| 7B - 14B | 24 GB | g5.4xlarge (A10G 24GB), g6.2xlarge (L4 24GB) |
| 14B - 32B | 48 GB | g5.12xlarge, g6.12xlarge |

QLoRA halves the memory requirement vs. full LoRA. The bundle defaults to QLoRA.

## Dataset format

A JSONL file where each line is a JSON object with two text fields. The default
field names are `instruction` and `output`, but they're configurable via parameters.

```json
{"instruction": "What is the capital of France?", "output": "Paris is the capital of France."}
{"instruction": "Write a haiku about autumn.", "output": "Crimson leaves descend / Whispering through crisp cool air / Winter waits beyond"}
```

The bundle accepts data in two forms:

### Local folder (default)
The `DatasetPath` parameter points to a local folder of one or more `.jsonl` files.
The folder is auto-uploaded via Deadline Cloud job attachments. **Multiple files
in the folder (including subfolders) are concatenated.** Default value: the
bundle's own `sample_data/` folder, so submitting with all defaults trains on
the included sample data (the Saffron Stack fictional-restaurant example).

### S3 URI (optional override)
If you set the `DatasetS3Uri` parameter, the bundle ignores `DatasetPath` and
downloads from S3 instead. Accepts:
- A single file: `s3://bucket/path/train.jsonl`
- A prefix (ending in `/`): `s3://bucket/path/`, which concatenates all `.jsonl`
  files under that prefix

S3 mode requires that the queue's session role has `s3:GetObject` permission on
the dataset (see the IAM setup section below).

Compatible with many public HuggingFace datasets including:
- [`tatsu-lab/alpaca`](https://huggingface.co/datasets/tatsu-lab/alpaca): uses `instruction` + `output`
- [`databricks/databricks-dolly-15k`](https://huggingface.co/datasets/databricks/databricks-dolly-15k): uses `instruction` + `response` (set `ResponseColumn=response`)
- [`HuggingFaceH4/no_robots`](https://huggingface.co/datasets/HuggingFaceH4/no_robots)
- [`yahma/alpaca-cleaned`](https://huggingface.co/datasets/yahma/alpaca-cleaned)

See [`sample_data/`](./sample_data/) for the bundled example dataset that comes with the bundle.

## Key parameters

| Parameter | Default | Description |
|---|---|---|
| **BaseModel** | `Qwen/Qwen2.5-7B` | HuggingFace model ID. Dropdown accepts any HF model ID. 7B recommended for fact-memorization. Use 1.5B for faster style-transfer training. |
| **HuggingFaceToken** | (empty) | Optional. Dropdown models are public and need no token. Provide one only for a gated model (e.g. Llama, Gemma) or to avoid HuggingFace rate limits. |
| **UseQLoRA** | `yes` | 4-bit quantization. Recommended for models >3B params. |
| **DatasetS3Uri** | (placeholder) | `s3://your-bucket/path/to/train.jsonl` |
| **InstructionColumn** | `instruction` | Field name in the JSONL for the user prompt. |
| **ResponseColumn** | `output` | Field name for the target response. |
| **MaxSamples** | `0` | Cap dataset size (`0` = use all). Useful for quick tests. |
| **LoraRank** | `32` | Adapter rank. Higher = more capacity, more VRAM. Try 8/16/32/64. |
| **LoraAlpha** | `64` | LoRA scaling factor. Convention: 2× rank. |
| **LoraDropout** | `0.05` | Regularization for LoRA layers. |
| **LearningRate** | `1e-4` | Typical LoRA range is 1e-4 to 5e-4. Supports scientific notation. |
| **Epochs** | `10` | Number of full passes through the dataset. |
| **PerDeviceBatchSize** | `1` | Per-GPU batch size. Lower if you run out of VRAM. |
| **GradAccumSteps** | `4` | Effective batch = batch_size × this. |
| **MaxSeqLength** | `512` | Token cutoff for inputs+outputs. Higher = more VRAM. |
| **OutputDir** | (required) | Local directory. The adapter is uploaded back via job attachments. |
| **AdapterName** | `my-lora-adapter` | Subfolder name under OutputDir. |

Advanced parameters (`TrainScript`, `HfCacheDir`, `RunTests`) are hidden in the GUI submitter.

**Default hyperparameters are tuned for fact-memorization** (matches the bundled Saffron Stack sample data, and reproducibly produces accurate output). For style-transfer use cases (custom brand voice, persona emulation, output format constraints), a lighter config trains faster: try `BaseModel=Qwen/Qwen2.5-1.5B`, `Epochs=5`, `LoraRank=16`, `LearningRate=2e-4`.

## Setup: granting the queue role access to your dataset bucket

Deadline Cloud workers run jobs under the queue's session role. By default that
role can only read from the queue's job attachments S3 bucket. If your dataset
lives elsewhere, you must grant the role read access.

Add an inline policy like this to your queue role (replace the resource ARN with
your actual bucket/prefix):

```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "ReadFineTuningDatasets",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:ListBucket"],
        "Resource": [
            "arn:aws:s3:::YOUR-BUCKET",
            "arn:aws:s3:::YOUR-BUCKET/datasets/*"
        ]
    }]
}
```

Apply it with:

```bash
QUEUE_ROLE=$(aws deadline get-queue --farm-id <FARM-ID> --queue-id <QUEUE-ID> \
  --query 'roleArn' --output text | awk -F/ '{print $NF}')

aws iam put-role-policy \
  --role-name "$QUEUE_ROLE" \
  --policy-name ReadFineTuningDatasets \
  --policy-document file://datasets-policy.json
```

Alternatively, place your dataset under the queue's existing job-attachments
bucket prefix (`DeadlineCloud/...`) where the role already has access.

## Submitting a job

### GUI submission

```bash
deadline bundle gui-submit /path/to/hf_finetune_lora
```

Fill in the form, click Submit. The GUI is organized into collapsible sections:
Model, Dataset, LoRA, Training, Output.

### CLI submission

```bash
deadline bundle submit /path/to/hf_finetune_lora \
  --queue-id <gpu-queue-id> \
  -p DatasetPath=/path/to/your/data \
  -p OutputDir=/tmp/lora-output \
  -p AdapterName=my-adapter
```

Or override any hyperparameters:

```bash
deadline bundle submit /path/to/hf_finetune_lora \
  --queue-id <gpu-queue-id> \
  -p BaseModel=Qwen/Qwen2.5-1.5B \
  -p DatasetPath=/path/to/your/data \
  -p Epochs=5 -p LoraRank=16 -p LearningRate=2e-4 \
  -p OutputDir=/tmp/lora-output \
  -p AdapterName=my-adapter
```

### Wait for completion

```bash
deadline job wait --job-id <job-id> --timeout 3600
```

### Download the adapter

```bash
deadline job download-output --job-id <job-id>
```

The adapter ends up at `OutputDir/AdapterName/` and contains:
- `adapter_model.safetensors`: the LoRA weights
- `adapter_config.json`: PEFT configuration
- `training_metadata.json`: base model, hyperparameters, sample count
- Tokenizer files (`tokenizer.json`, `vocab.json`, etc.)

## Using the trained adapter

After downloading the adapter, the easiest way to test it is the included
interactive chat tool:

```bash
python3 inference/chat.py --adapter-path /path/to/downloaded/my-adapter
```

This loads the adapter on top of the base model and gives you a REPL where you
can ask questions and compare against the base model to verify the fine-tune
worked.

For a more demo-friendly **web UI** (ChatGPT-like chat bubbles in your browser):

```bash
pip install gradio
python3 inference/gradio_chat.py --adapter-path /path/to/downloaded/my-adapter
```

See [`inference/README.md`](./inference/) for details on both tools.

For programmatic use, load the adapter on top of the base model with PEFT:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# Use the same base model you trained with — read training_metadata.json to check.
BASE = "Qwen/Qwen2.5-7B"
ADAPTER = "/path/to/downloaded/my-adapter"

tokenizer = AutoTokenizer.from_pretrained(BASE)
base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype="bfloat16").to("cuda")
model = PeftModel.from_pretrained(base, ADAPTER)
model.eval()

messages = [{"role": "user", "content": "What is the capital of France?"}]
inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                        return_tensors="pt").to(model.device)
outputs = model.generate(inputs, max_new_tokens=200, do_sample=False)
print(tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True))
```

You can also use `model.disable_adapter()` to temporarily switch back to the base
model for A/B comparison.

## Bundled sample data

The bundle includes a small fully-fictional example dataset in
[`sample_data/`](./sample_data/) so that submitting with all defaults produces
a working demo out of the box. The dataset teaches the model facts about
"Saffron Stack" (an invented Chipotle-style vegetarian Indian fast-casual chain).
It demonstrates the pattern for fine-tuning on your own proprietary knowledge
(product wiki, internal acronyms, customer-support playbook, brand voice, etc.).

To use your own data, simply replace the files in `sample_data/` with your own
JSONL files, or point the `DatasetPath` parameter at a different folder.

## Output structure

```
<OutputDir>/
├── checkpoints/                         # Intermediate training checkpoints (configurable via save_steps)
│   ├── checkpoint-100/
│   └── ...
└── <AdapterName>/                       # The final adapter you'll use for inference
    ├── README.md
    ├── adapter_config.json
    ├── adapter_model.safetensors        # The LoRA weights (~50-200 MB)
    ├── training_metadata.json
    ├── tokenizer.json
    └── ...
```

## Tips and gotchas

1. **Loss should monotonically decrease.** If it doesn't, lower the learning rate (try `1e-4`).
2. **Memory pressure?** Lower `PerDeviceBatchSize` (try 1 or 2) and raise `GradAccumSteps` to keep the effective batch size constant.
3. **Style transfer vs fact memorization** are different difficulty levels. Style transfer often works with 3-5 epochs and ~50-200 samples. Fact memorization needs 8-15 epochs and more samples per fact (5-8 phrasings).
4. **Gated models** (e.g. Llama, Gemma): if you repoint the bundle at one, set the `HuggingFaceToken` parameter. For production, prefer to set `HF_TOKEN` as an env var on the queue itself rather than passing as a parameter.
5. **Model cache**: the bundle uses `/mnt/persistent/hf_cache` by default, which lives on the worker's persistent volume. Base models are cached across jobs, so subsequent runs are much faster.
6. **Cost optimization**: most LoRA fine-tunes for 1B-7B models complete in 5-30 minutes. Use spot/on-demand based on tolerance for interruption.

## Architecture support

The bundle's default LoRA target modules (`q_proj, k_proj, v_proj, o_proj,
gate_proj, up_proj, down_proj`) cover virtually all modern transformer
architectures:

- ✅ Llama family (Llama 2, Llama 3, Llama 3.1, Llama 3.2)
- ✅ Qwen family (Qwen 2, Qwen 2.5, Qwen 3)
- ✅ Mistral family (Mistral, Mixtral via specific configs)
- ✅ Gemma family
- ✅ Phi family (Phi-3, Phi-3.5)
- ✅ Falcon family
- ✅ DeepSeek family
- ❌ GPT-2 / BERT / T5 / RoBERTa (older architectures with different module names)

## References

- [Open Job Description specifications](https://github.com/OpenJobDescription/openjd-specifications/wiki)
- [HuggingFace PEFT documentation](https://huggingface.co/docs/peft)
- [QLoRA paper](https://arxiv.org/abs/2305.14314): Dettmers et al., 2023
- [LoRA paper](https://arxiv.org/abs/2106.09685): Hu et al., 2021
- [Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/)
