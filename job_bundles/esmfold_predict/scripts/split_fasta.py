#!/usr/bin/env python3
"""Splitter step for the ESMFold bundle.

Reads the user's input FASTA, parses records, validates lengths, and round-robins
sequences into per-task manifest files (`batch_1.jsonl` ... `batch_N.jsonl`) under
WorkspacePath. Step 2 (Fold) reads its assigned manifest by index.

This pattern matches copy_s3_prefix_to_job_attachments/scripts/collect_objects.py:
the count is fixed by the user-supplied Parallelism parameter, not derived from
the input — OpenJD jobtemplate-2023-09 doesn't support dynamic task-count
derivation between steps.
"""
import argparse
import json
import os
import sys
from pathlib import Path


# ESMFold's max position embedding is 1026; sequences longer than this OOM
# silently or produce garbage. Reject up-front rather than fail mid-fold.
MAX_SEQUENCE_LENGTH = 1024
VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYX")  # X = unknown, accepted


def parse_fasta(path: Path):
    """Yield (record_id, sequence) pairs. Raises on malformed input."""
    record_id = None
    seq_lines: list[str] = []
    with open(path) as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if record_id is not None:
                    yield record_id, "".join(seq_lines)
                record_id = line[1:].split()[0] if len(line) > 1 else None
                if not record_id:
                    raise SystemExit(f"openjd_fail: malformed FASTA header at line {line_no}: {raw!r}")
                seq_lines = []
            else:
                if record_id is None:
                    raise SystemExit(f"openjd_fail: sequence data before any header at line {line_no}")
                seq_lines.append(line.upper())
    if record_id is not None:
        yield record_id, "".join(seq_lines)


def validate(record_id: str, sequence: str) -> None:
    if not sequence:
        raise SystemExit(f"openjd_fail: empty sequence for record {record_id!r}")
    if len(sequence) > MAX_SEQUENCE_LENGTH:
        raise SystemExit(
            f"openjd_fail: sequence {record_id!r} is {len(sequence)} aa, "
            f"exceeds ESMFold max of {MAX_SEQUENCE_LENGTH}. Trim or split before submitting."
        )
    bad = set(sequence) - VALID_AMINO_ACIDS
    if bad:
        raise SystemExit(
            f"openjd_fail: sequence {record_id!r} contains non-standard amino acid characters: "
            f"{sorted(bad)}. Only the 20 standard AAs plus X (unknown) are accepted."
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace_path", type=Path)
    ap.add_argument("--input-fasta", type=Path, required=True)
    ap.add_argument("--parallelism", type=int, required=True)
    args = ap.parse_args()

    if args.parallelism < 1:
        raise SystemExit("openjd_fail: --parallelism must be >= 1")

    os.makedirs(args.workspace_path, exist_ok=True)

    if not args.input_fasta.exists():
        raise SystemExit(f"openjd_fail: input FASTA not found: {args.input_fasta}")

    records = []
    seen_ids = set()
    for rid, seq in parse_fasta(args.input_fasta):
        if rid in seen_ids:
            raise SystemExit(f"openjd_fail: duplicate FASTA record id {rid!r}")
        seen_ids.add(rid)
        validate(rid, seq)
        records.append({"id": rid, "sequence": seq, "length": len(seq)})

    if not records:
        raise SystemExit(f"openjd_fail: no FASTA records found in {args.input_fasta}")

    # Sort longest-first so each batch sees a similar runtime distribution
    # (longest seqs dominate fold time; round-robin from sorted gives balanced batches).
    records.sort(key=lambda r: r["length"], reverse=True)

    batches: list[list[dict]] = [[] for _ in range(args.parallelism)]
    for i, rec in enumerate(records):
        batches[i % args.parallelism].append(rec)

    for i, batch in enumerate(batches, start=1):
        out_path = args.workspace_path / f"batch_{i}.jsonl"
        with open(out_path, "w") as fh:
            for rec in batch:
                fh.write(json.dumps(rec) + "\n")
        print(f"openjd_status: wrote {out_path.name} with {len(batch)} sequences")

    summary = {
        "total_sequences": len(records),
        "parallelism": args.parallelism,
        "min_length": min(r["length"] for r in records),
        "max_length": max(r["length"] for r in records),
    }
    with open(args.workspace_path / "split_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"openjd_status: split {len(records)} sequences across {args.parallelism} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
