#!/usr/bin/env python3
"""ESMFold inference task.

Reads the assigned batch manifest from WorkspacePath/batch_<index>.jsonl,
loads facebook/esmfold_v1 via HuggingFace transformers, runs inference on each
sequence, writes a PDB file plus a summary.json with mean pLDDT.

Validation built in (layer 1 + layer 2 from the bundle's validation strategy):
  - PDB parses back cleanly
  - No NaN coordinates
  - pLDDT range [0, 100]
  - mean pLDDT recorded per sequence

Layer-3 validation (TM-score vs reference) is in scripts/validate.py and runs
as a separate step.
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path


def _bootstrap_hf_dirs(output_dir: str) -> None:
    """Pin HuggingFace's cache dirs into OutputDir before importing transformers.
    Mirrors the unsloth_finetune pattern. The 5.2 GB esmfold_v1 weights land
    inside the job's output, so job attachments capture them and re-runs of
    the same job reuse the cache."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = out / ".hf_cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache)
    os.environ["TRANSFORMERS_CACHE"] = str(cache / "transformers")
    os.environ["HF_HUB_CACHE"] = str(cache / "hub")


def _rescale_b_factor(pdb_text: str) -> str:
    """Rescale B-factor column from [0,1] to [0,100] for canonical pLDDT.

    transformers' EsmForProteinFolding.output_to_pdb writes pLDDT scaled to
    [0, 1]. AlphaFold/ESMFold convention (and every viewer's default coloring)
    expects [0, 100]. Rewrite ATOM lines in place; non-ATOM lines pass through.
    """
    out_lines = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM"):
            try:
                b = float(line[60:66])
            except ValueError:
                out_lines.append(line)
                continue
            if 0.0 <= b <= 1.0:
                b *= 100.0
            line = f"{line[:60]}{b:6.2f}{line[66:]}"
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def parse_pdb_for_validation(pdb_text: str) -> dict:
    """Parse the written PDB to confirm it's well-formed and extract pLDDT stats.
    Returns {atom_count, residue_count, mean_plddt, min_plddt, max_plddt, has_nan}."""
    atom_count = 0
    residues = set()
    plddts: list[float] = []
    has_nan = False
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM"):
            continue
        atom_count += 1
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            b = float(line[60:66])
        except ValueError:
            has_nan = True
            continue
        if any(math.isnan(v) or math.isinf(v) for v in (x, y, z, b)):
            has_nan = True
        residues.add(line[21:27])
        plddts.append(b)
    return {
        "atom_count": atom_count,
        "residue_count": len(residues),
        "mean_plddt": sum(plddts) / len(plddts) if plddts else 0.0,
        "min_plddt": min(plddts) if plddts else 0.0,
        "max_plddt": max(plddts) if plddts else 0.0,
        "has_nan": has_nan,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace_path", type=Path)
    ap.add_argument("--index", type=int, required=True, help="Batch index (1-based).")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--model-id", default="facebook/esmfold_v1")
    ap.add_argument("--chunk-size", type=int, default=64,
                    help="Axial-attention chunk size. Lower = less VRAM, slower.")
    args = ap.parse_args()

    _bootstrap_hf_dirs(str(args.output_dir))

    manifest = args.workspace_path / f"batch_{args.index}.jsonl"
    if not manifest.exists():
        raise SystemExit(f"openjd_fail: batch manifest not found: {manifest}")

    records = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    if not records:
        print(f"openjd_status: batch {args.index} is empty, nothing to fold")
        return 0

    print(f"openjd_status: loading {args.model_id} (~5.2 GB on first run)")
    t0 = time.time()
    import torch
    from transformers import AutoTokenizer, EsmForProteinFolding

    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    model = EsmForProteinFolding.from_pretrained(args.model_id, low_cpu_mem_usage=True)
    if torch.cuda.is_available():
        model = model.cuda()
        # fp16 trunk halves VRAM with minimal accuracy impact at <600aa.
        model.esm = model.esm.half()
        torch.backends.cuda.matmul.allow_tf32 = True
    model.trunk.set_chunk_size(args.chunk_size)
    model.eval()
    print(f"openjd_status: model loaded in {time.time() - t0:.1f}s, "
          f"CUDA={torch.cuda.is_available()}")

    results_dir = args.output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for rec in records:
        seq_id = rec["id"]
        sequence = rec["sequence"]
        seq_dir = results_dir / seq_id
        seq_dir.mkdir(parents=True, exist_ok=True)

        print(f"openjd_status: folding {seq_id} ({len(sequence)} aa)")
        t0 = time.time()
        with torch.no_grad():
            tokenized = tokenizer([sequence], return_tensors="pt", add_special_tokens=False)
            input_ids = tokenized["input_ids"]
            if torch.cuda.is_available():
                input_ids = input_ids.cuda()
            output = model(input_ids)
        elapsed = time.time() - t0

        # The model's built-in PDB writer encodes pLDDT in the B-factor column,
        # but transformers' EsmForProteinFolding emits pLDDT in [0, 1] rather
        # than the [0, 100] AlphaFold convention. Rewrite the B-factor column
        # so downstream tools (PyMOL color-by-B, validation thresholds) see the
        # canonical scale.
        raw_pdb = model.output_to_pdb(output)[0]
        pdb_text = _rescale_b_factor(raw_pdb)
        pdb_path = seq_dir / f"{seq_id}.pdb"
        pdb_path.write_text(pdb_text)

        # Layer 1 validation: parse what we just wrote.
        v = parse_pdb_for_validation(pdb_text)
        if v["atom_count"] == 0:
            raise SystemExit(f"openjd_fail: PDB for {seq_id} has zero ATOM records")
        if v["has_nan"]:
            raise SystemExit(f"openjd_fail: PDB for {seq_id} contains NaN/inf coordinates")
        if v["residue_count"] != len(sequence):
            print(f"openjd_warn: PDB residue count {v['residue_count']} != sequence length {len(sequence)} for {seq_id}")
        if not (0.0 <= v["min_plddt"] <= v["max_plddt"] <= 100.0):
            raise SystemExit(
                f"openjd_fail: pLDDT out of range for {seq_id}: "
                f"min={v['min_plddt']:.2f} max={v['max_plddt']:.2f}"
            )

        rec_summary = {
            "id": seq_id,
            "length": len(sequence),
            "fold_seconds": round(elapsed, 2),
            "mean_plddt": round(v["mean_plddt"], 2),
            "min_plddt": round(v["min_plddt"], 2),
            "max_plddt": round(v["max_plddt"], 2),
            "atom_count": v["atom_count"],
            "pdb_path": str(pdb_path.relative_to(args.output_dir)),
        }
        summary.append(rec_summary)
        with open(seq_dir / "summary.json", "w") as fh:
            json.dump(rec_summary, fh, indent=2)
        print(f"openjd_status: {seq_id} done in {elapsed:.1f}s, mean pLDDT={v['mean_plddt']:.1f}")

    batch_summary_path = args.output_dir / "results" / f"batch_{args.index}_summary.json"
    with open(batch_summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"openjd_status: batch {args.index} folded {len(summary)} sequences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
