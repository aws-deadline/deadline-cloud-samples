# Sample training data

This folder is the default value of the `DatasetPath` job parameter. Submitting
the bundle with no parameter overrides will fine-tune on **all JSONL files here
(recursive — including in subfolders)**.

## What's included

```
sample_data/
└── saffron_stack/             — 118 examples about a fictional restaurant chain,
    ├── menu.jsonl                organized into thematic files
    ├── founders_history.jsonl
    ├── programs.jsonl
    ├── timeline.jsonl
    └── brand.jsonl
```

| File | Records | Covers |
|---|---|---|
| `saffron_stack/menu.jsonl` | 40 | Menu items, dishes, bowls |
| `saffron_stack/founders_history.jsonl` | 37 | Founders, key people, company overview |
| `saffron_stack/programs.jsonl` | 16 | Loyalty program, jargon, training |
| `saffron_stack/timeline.jsonl` | 13 | Funding, expansion, key events |
| `saffron_stack/brand.jsonl` | 12 | Brand voice, quirky details |

Total: **5 files, 118 examples** — all get concatenated into one training set
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

1. **Add files at the top level**: drop `my_data.jsonl` into this folder
2. **Add a subfolder**: create `sample_data/my_business/*.jsonl`
3. **Point to a different folder entirely**: change the `DatasetPath` parameter
   in the GUI submitter
4. **Use S3**: set the `DatasetS3Uri` parameter — accepts a single file URI
   or a prefix ending in `/`

## JSONL format

```jsonl
{"instruction": "...", "output": "..."}
{"instruction": "...", "output": "..."}
```

Field names `instruction` and `output` are configurable via the
`InstructionColumn` and `ResponseColumn` parameters.

## To regenerate

The Saffron Stack thematic files are produced by the generator script in the
example folder. Regenerate them with:

```bash
cd ../examples/saffron_stack && python3 generate.py > /tmp/full.jsonl
```

Then use the multi-file split script to break the flat output into the
thematic subfolder structure (also lives in `examples/saffron_stack/`).
