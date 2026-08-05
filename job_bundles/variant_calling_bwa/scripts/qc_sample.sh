#!/usr/bin/env bash
# Run FastQC on one sample's read pair. One task per sample.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

SAMPLES_CSV=""
SAMPLE_INDEX=""
READS=""
OUT=""
for arg in "$@"; do
  case "$arg" in
    --samples=*)      SAMPLES_CSV="${arg#*=}" ;;
    --sample-index=*) SAMPLE_INDEX="${arg#*=}" ;;
    --reads-dir=*)    READS="${arg#*=}" ;;
    --output-dir=*)   OUT="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$SAMPLES_CSV" --samples
require_arg "$SAMPLE_INDEX" --sample-index
require_arg "$READS" --reads-dir
require_arg "$OUT" --output-dir

parse_list SAMPLES "$SAMPLES_CSV"
require_non_empty_list "${#SAMPLES[@]}" Samples
validate_sample_names "${SAMPLES[@]}"
if (( SAMPLE_INDEX >= ${#SAMPLES[@]} )); then
  echo "Sample index $SAMPLE_INDEX is past the end of the sample list; nothing to do."
  exit 0
fi
SAMPLE="${SAMPLES[$SAMPLE_INDEX]}"
QC_DIR="$OUT/qc"
mkdir -p "$QC_DIR"

R1="$READS/${SAMPLE}_R1.fastq.gz"
R2="$READS/${SAMPLE}_R2.fastq.gz"
for f in "$R1" "$R2"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: FASTQ not found: $f" >&2
    exit 1
  fi
done

echo "Running FastQC on $SAMPLE"
fastqc --outdir "$QC_DIR" --threads 2 "$R1" "$R2"

# Name the reports this task produced, so the log says what to look for in the
# output directory. Derived from the two input filenames rather than globbing
# $QC_DIR, which is shared: a glob would also list the reports left by the other
# samples' tasks when a session is reused.
for f in "$R1" "$R2"; do
  echo "  report: $QC_DIR/$(basename "$f" .fastq.gz)_fastqc.html"
done
echo "QC complete for $SAMPLE"
