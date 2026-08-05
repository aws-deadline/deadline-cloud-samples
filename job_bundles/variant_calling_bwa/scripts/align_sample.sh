#!/usr/bin/env bash
# Align one sample with bwa mem, then sort and index the BAM.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

SAMPLES_CSV=""
SAMPLE_INDEX=""
READS=""
OUT=""
REFERENCE_NAME=""
WORK_ROOT=""
for arg in "$@"; do
  case "$arg" in
    --samples=*)         SAMPLES_CSV="${arg#*=}" ;;
    --sample-index=*)    SAMPLE_INDEX="${arg#*=}" ;;
    --reads-dir=*)       READS="${arg#*=}" ;;
    --output-dir=*)      OUT="${arg#*=}" ;;
    --reference-name=*)  REFERENCE_NAME="${arg#*=}" ;;
    --session-work-dir=*) WORK_ROOT="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$SAMPLES_CSV" --samples
require_arg "$SAMPLE_INDEX" --sample-index
require_arg "$READS" --reads-dir
require_arg "$OUT" --output-dir
require_arg "$REFERENCE_NAME" --reference-name
require_arg "$WORK_ROOT" --session-work-dir

parse_list SAMPLES "$SAMPLES_CSV"
require_non_empty_list "${#SAMPLES[@]}" Samples
validate_sample_names "${SAMPLES[@]}"
if (( SAMPLE_INDEX >= ${#SAMPLES[@]} )); then
  echo "Sample index $SAMPLE_INDEX is past the end of the sample list; nothing to do."
  exit 0
fi
SAMPLE="${SAMPLES[$SAMPLE_INDEX]}"
BAM_DIR="$OUT/alignments"
# Named by index rather than sample name: this directory is removed with 'rm -rf'
# below, so keeping the name a plain integer means the target cannot depend on
# the contents of a job parameter.
WORK="$WORK_ROOT/align_${SAMPLE_INDEX}"
mkdir -p "$BAM_DIR" "$WORK"

R1="$READS/${SAMPLE}_R1.fastq.gz"
R2="$READS/${SAMPLE}_R2.fastq.gz"
BAM="$BAM_DIR/${SAMPLE}.sorted.bam"

# Derived from the output directory, not read from a file: BuildIndex ran in a
# different session directory.
IDX_PREFIX="$OUT/reference/$REFERENCE_NAME"
# bwa mem takes the prefix and finds the index itself, accepting either the
# "<reference>.bwt" or the "<reference>.64.bwt" naming, so accept both here too.
if [[ ! -f "${IDX_PREFIX}.bwt" && ! -f "${IDX_PREFIX}.64.bwt" ]]; then
  echo "ERROR: no bwa index beside ${IDX_PREFIX}. Did BuildIndex run?" >&2
  exit 1
fi
echo "Aligning $SAMPLE against $IDX_PREFIX"

# Scale to the worker rather than hardcoding a thread count. The step requires a
# minimum of 2 vCPU, not exactly 2, so a fleet is free to place this task on a
# much larger instance; a fixed count would leave most of it idle.
ALIGN_THREADS="$(nproc)"
# 'samtools sort -m' is per thread, so the sort's total appetite is threads times
# -m. Divide a fixed budget between the threads to keep that total flat, and cap
# the thread count so it stays flat on a very large worker: sorting is I/O bound
# well before this many threads anyway.
SORT_THREADS=$(( ALIGN_THREADS > 1 ? ALIGN_THREADS / 2 : 1 ))
(( SORT_THREADS > 4 )) && SORT_THREADS=4
SORT_MEM_MB=$(( 4096 / SORT_THREADS ))
echo "Using $ALIGN_THREADS alignment thread(s), $SORT_THREADS sort thread(s) at ${SORT_MEM_MB}M each"

# The @RG line carries the sample name into the BAM so that bcftools attributes
# calls to the right sample column in the VCF.
bwa mem \
  -t "$ALIGN_THREADS" \
  -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:${SAMPLE}" \
  "$IDX_PREFIX" "$R1" "$R2" \
  | samtools sort -@ "$SORT_THREADS" -m "${SORT_MEM_MB}M" -T "$WORK/sort" -o "$BAM" -

samtools index "$BAM"
samtools flagstat "$BAM" > "$BAM_DIR/${SAMPLE}.flagstat.txt"
echo "--- flagstat: $SAMPLE ---"
head -n 5 "$BAM_DIR/${SAMPLE}.flagstat.txt"
rm -rf "$WORK"
echo "Alignment complete: $BAM"
