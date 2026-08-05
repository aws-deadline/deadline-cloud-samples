#!/usr/bin/env bash
# Call variants over one reference region, jointly across all samples.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

REGIONS_CSV=""
REGION_INDEX=""
SAMPLES_CSV=""
OUT=""
REFERENCE_NAME=""
MIN_MAPPING_QUALITY=""
MIN_BASE_QUALITY=""
PLOIDY=""
MIN_QUAL=""
MIN_DEPTH=""
for arg in "$@"; do
  case "$arg" in
    --regions=*)             REGIONS_CSV="${arg#*=}" ;;
    --region-index=*)        REGION_INDEX="${arg#*=}" ;;
    --samples=*)             SAMPLES_CSV="${arg#*=}" ;;
    --output-dir=*)          OUT="${arg#*=}" ;;
    --reference-name=*)      REFERENCE_NAME="${arg#*=}" ;;
    --min-mapping-quality=*) MIN_MAPPING_QUALITY="${arg#*=}" ;;
    --min-base-quality=*)    MIN_BASE_QUALITY="${arg#*=}" ;;
    --ploidy=*)              PLOIDY="${arg#*=}" ;;
    --min-qual=*)            MIN_QUAL="${arg#*=}" ;;
    --min-depth=*)           MIN_DEPTH="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$REGIONS_CSV" --regions
require_arg "$REGION_INDEX" --region-index
require_arg "$SAMPLES_CSV" --samples
require_arg "$OUT" --output-dir
require_arg "$REFERENCE_NAME" --reference-name
require_arg "$MIN_MAPPING_QUALITY" --min-mapping-quality
require_arg "$MIN_BASE_QUALITY" --min-base-quality
require_arg "$PLOIDY" --ploidy
require_arg "$MIN_QUAL" --min-qual
require_arg "$MIN_DEPTH" --min-depth

parse_list REGIONS "$REGIONS_CSV"
require_non_empty_list "${#REGIONS[@]}" Regions
parse_list SAMPLES "$SAMPLES_CSV"
require_non_empty_list "${#SAMPLES[@]}" Samples
validate_sample_names "${SAMPLES[@]}"
if (( REGION_INDEX >= ${#REGIONS[@]} )); then
  echo "Region index $REGION_INDEX is past the end of the region list; nothing to do."
  exit 0
fi
REGION="${REGIONS[$REGION_INDEX]}"
BAM_DIR="$OUT/alignments"
VCF_DIR="$OUT/vcf_by_region"
mkdir -p "$VCF_DIR"

VCF="$(region_vcf_path "$VCF_DIR" "$REGION_INDEX" "$REGION")"

# mpileup requires a .fai beside the reference it is given, so use the copy
# BuildIndex assembled. Derived from the output directory, not read from a file.
REF="$OUT/reference/$REFERENCE_NAME"
if [[ ! -f "${REF}.fai" ]]; then
  echo "ERROR: no .fai index at ${REF}.fai. Did BuildIndex run?" >&2
  exit 1
fi

# Build the BAM list from the sample list rather than globbing the directory. A
# glob would silently pick up BAMs left over from an earlier run or a reused
# session and call a cohort the user did not ask for.
BAMS=()
for s in "${SAMPLES[@]}"; do
  bam="$BAM_DIR/${s}.sorted.bam"
  if [[ ! -f "$bam" ]]; then
    echo "ERROR: no alignment for sample '$s' at $bam." >&2
    echo "AlignReads must run for every sample listed in Samples." >&2
    exit 1
  fi
  BAMS+=("$bam")
done
echo "Calling region '$REGION' jointly across ${#BAMS[@]} sample(s): ${SAMPLES[*]}"

# --ploidy takes an assembly preset; '1' and '2' are the presets meaning treat
# every sample as haploid or diploid respectively.
bcftools mpileup \
  --fasta-ref "$REF" \
  --regions "$REGION" \
  -q "$MIN_MAPPING_QUALITY" \
  -Q "$MIN_BASE_QUALITY" \
  --annotate FORMAT/AD,FORMAT/DP \
  --output-type u \
  "${BAMS[@]}" \
  | bcftools call \
      --multiallelic-caller \
      --variants-only \
      --ploidy "$PLOIDY" \
      --output-type u \
  | bcftools filter \
      --include "QUAL>=$MIN_QUAL && INFO/DP>=$MIN_DEPTH" \
      --output-type z \
      --output "$VCF"

# An index is required here, not just convenient: MergeVariants uses
# 'bcftools concat --allow-overlaps', which needs indexed inputs.
bcftools index --force --tbi "$VCF"
COUNT="$(bcftools view --no-header "$VCF" | wc -l)"
echo "Region '$REGION': ${COUNT} variant(s) passing QUAL>=$MIN_QUAL DP>=$MIN_DEPTH -> $VCF"
