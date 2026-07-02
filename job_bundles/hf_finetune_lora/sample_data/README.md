# Sample training data

This folder is the default value of the `DatasetPath` job parameter. Submitting
the bundle with no parameter overrides will fine-tune on **all JSONL files
under this folder (recursive — subfolders are traversed)**.

## What's included

The bundled example dataset trains the model on a fully-fictional restaurant
chain called "Saffron Stack" — an invented Chipotle-style vegetarian Indian
fast-casual chain. The data is split across 5 thematic files to demonstrate
the bundle's multi-file loading:

```
sample_data/saffron_stack/
├── menu.jsonl                (40 records)
├── founders_history.jsonl    (37 records)
├── programs.jsonl            (16 records)
├── timeline.jsonl            (13 records)
└── brand.jsonl               (12 records)
```

Total: **5 files, 118 records** — all get concatenated into one training set
when the bundle runs with default parameters.

## Why the subfolder structure?

This demonstrates two of the bundle's dataset-loading features:

1. **Multi-file loading** — you can split your data across many `.jsonl` files
   for editability (a marketing person edits `brand.jsonl`, a chef edits
   `menu.jsonl`, etc.). The training script concatenates them automatically.
2. **Recursive discovery** — subfolders are traversed. You can organize by
   topic, product line, department, or however makes sense for your business.

## To use your own data

Any of the following works:

1. **Replace the files here**: delete `saffron_stack/` and drop your own
   `.jsonl` files in `sample_data/` (flat or in subfolders — both work)
2. **Point to a different folder entirely**: change the `DatasetPath`
   parameter in the GUI submitter (or via CLI `-p DatasetPath=/path/to/your/data`)
3. **Use S3**: set the `DatasetS3Uri` parameter — accepts a single file URI
   or a prefix ending in `/`

## JSONL format

Each line is a JSON object with two text fields. The default field names are
`instruction` and `output`; both are configurable via the `InstructionColumn`
and `ResponseColumn` parameters.

```jsonl
{"instruction": "What are your hours?", "output": "We're open Mon-Fri 9am-9pm, weekends 10am-10pm."}
{"instruction": "Do you take reservations?", "output": "Yes — book through our website or call 555-0123."}
```

This format is compatible with popular public instruction datasets:
- [`tatsu-lab/alpaca`](https://huggingface.co/datasets/tatsu-lab/alpaca) — uses `instruction` + `output`
- [`databricks/databricks-dolly-15k`](https://huggingface.co/datasets/databricks/databricks-dolly-15k) — uses `instruction` + `response` (set `ResponseColumn=response`)
- [`HuggingFaceH4/no_robots`](https://huggingface.co/datasets/HuggingFaceH4/no_robots)

Download any of those and drop into `sample_data/` (or point `DatasetPath` at
wherever you saved them).
