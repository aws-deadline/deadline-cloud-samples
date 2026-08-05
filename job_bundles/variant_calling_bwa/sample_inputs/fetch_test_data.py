#!/usr/bin/env python3
"""Download the tiny public test dataset used by this sample.

The reads and reference are provided by AWS HealthOmics for their tutorials
(https://github.com/aws-samples/aws-healthomics-tutorials), hosted in the public,
unauthenticated ``aws-genomics-static-us-east-1`` bucket. The data originates
from nf-core/test-datasets and is MIT licensed. The whole set is under 1 MB, so
the pipeline runs end to end in seconds.

Reads land in ``reads/`` renamed to the ``<sample>_R1.fastq.gz`` /
``<sample>_R2.fastq.gz`` convention the job template expects. The reference and
its .fai land in ``reference/``.

Usage:
    python fetch_test_data.py            # download into ./reads and ./reference
    python fetch_test_data.py --clean    # remove downloaded files first
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = (
    "https://aws-genomics-static-us-east-1.s3.amazonaws.com"
    "/omics-data/test-datasets/nf-core-sarek"
)

# One lane per sample keeps the demo small. tiny_n is the "normal" library and
# tiny_t the "tumor" library of the same synthetic pair; here they simply act as
# two independent samples to fan out over.
READS = {
    "tiny_n_R1.fastq.gz": "testdata/tiny/normal/tiny_n_L001_R1_xxx.fastq.gz",
    "tiny_n_R2.fastq.gz": "testdata/tiny/normal/tiny_n_L001_R2_xxx.fastq.gz",
    "tiny_t_R1.fastq.gz": "testdata/tiny/tumor/tiny_t_L001_R1_xxx.fastq.gz",
    "tiny_t_R2.fastq.gz": "testdata/tiny/tumor/tiny_t_L001_R2_xxx.fastq.gz",
}

# The .fai is fetched so BuildIndex can skip samtools faidx. The bwa index files
# are deliberately not fetched: BuildIndex rebuilds them in a second or two for a
# reference this small, which keeps the download to a single FASTA and avoids
# depending on the index having been built by a compatible bwa version.
REFERENCE = {
    "human_g1k_v37_decoy.small.fasta": "reference/human_g1k_v37_decoy.small.fasta",
    "human_g1k_v37_decoy.small.fasta.fai": "reference/human_g1k_v37_decoy.small.fasta.fai",
}

HERE = Path(__file__).resolve().parent


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  exists, skipping: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {dest.name} <- {url}")

    # Download to a temporary name and rename only once the transfer is complete
    # and the byte count matches Content-Length. A partial file left at the final
    # path would be skipped by the check above on every later run, and the failure
    # would not surface until a tool choked on the truncated data.
    partial = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            expected = response.headers.get("Content-Length")
            with partial.open("wb") as out:
                shutil.copyfileobj(response, out)
        written = partial.stat().st_size
        if expected is not None and written != int(expected):
            raise OSError(f"expected {int(expected):,} bytes, received {written:,}")
        partial.replace(dest)
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        sys.exit(f"ERROR: HTTP {exc.code} fetching {url}")
    except urllib.error.URLError as exc:
        partial.unlink(missing_ok=True)
        sys.exit(f"ERROR: could not reach {url}: {exc.reason}")
    except (OSError, KeyboardInterrupt):
        partial.unlink(missing_ok=True)
        raise
    print(f"      {dest.stat().st_size:,} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="delete the reads/ and reference/ contents before downloading",
    )
    args = parser.parse_args()

    reads_dir = HERE / "reads"
    reference_dir = HERE / "reference"

    if args.clean:
        for directory in (reads_dir, reference_dir):
            if directory.exists():
                print(f"Removing {directory}")
                shutil.rmtree(directory)

    print("Downloading reads (nf-core/test-datasets, MIT licensed):")
    for name, key in READS.items():
        download(f"{BASE_URL}/{key}", reads_dir / name)

    print("Downloading reference:")
    for name, key in REFERENCE.items():
        download(f"{BASE_URL}/{key}", reference_dir / name)

    # Count only the downloaded data, not this script and the docs beside it.
    total = sum(
        f.stat().st_size
        for directory in (reads_dir, reference_dir)
        for f in directory.rglob("*")
        if f.is_file()
    )
    print(f"\nDone. {total / 1024:.0f} KB downloaded into {HERE}")

    fai = reference_dir / "human_g1k_v37_decoy.small.fasta.fai"
    if fai.exists():
        names = [
            line.split("\t")[0]
            for line in fai.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        print(f"Reference contigs: {','.join(names)}")
        print(
            f"The sample reads align to only part of contig {names[0]}, which is "
            "why the job template's default Regions is a set of windows within it "
            "rather than these contig names."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
