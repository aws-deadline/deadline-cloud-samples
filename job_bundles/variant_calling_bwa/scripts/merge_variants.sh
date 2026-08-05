#!/usr/bin/env bash
# Gather the per-region VCFs into one sorted, indexed VCF, summarize it, and
# build a MultiQC report over the run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

REGIONS_CSV=""
SAMPLES_CSV=""
OUT=""
REFERENCE_NAME=""
for arg in "$@"; do
  case "$arg" in
    --regions=*)        REGIONS_CSV="${arg#*=}" ;;
    --samples=*)        SAMPLES_CSV="${arg#*=}" ;;
    --output-dir=*)     OUT="${arg#*=}" ;;
    --reference-name=*) REFERENCE_NAME="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$REGIONS_CSV" --regions
require_arg "$SAMPLES_CSV" --samples
require_arg "$OUT" --output-dir
require_arg "$REFERENCE_NAME" --reference-name

VCF_DIR="$OUT/vcf_by_region"
MERGED="$OUT/variants.vcf.gz"

# Collect exactly the VCFs the requested regions should have produced, in the
# order the regions were given. Globbing the directory instead would pick up
# stale files from an earlier run with different regions and merge a result the
# user did not ask for.
parse_list REGIONS "$REGIONS_CSV"
require_non_empty_list "${#REGIONS[@]}" Regions
VCFS=()
MISSING=()
for i in "${!REGIONS[@]}"; do
  vcf="$(region_vcf_path "$VCF_DIR" "$i" "${REGIONS[$i]}")"
  if [[ -f "$vcf" ]]; then
    VCFS+=("$vcf")
  else
    MISSING+=("${REGIONS[$i]}")
  fi
done

# A missing VCF means CallVariants never ran for that region, which happens when
# RegionRange does not cover the whole region list.
if (( ${#MISSING[@]} > 0 )); then
  echo "ERROR: no VCF for ${#MISSING[@]} of ${#REGIONS[@]} requested region(s):" >&2
  printf '  %s\n' "${MISSING[@]}" >&2
  echo "RegionRange must cover every region: '0-$(( ${#REGIONS[@]} - 1 ))' for this list." >&2
  exit 1
fi
# Same check for samples: a SampleRange that skips an entry would leave that
# sample unaligned and silently absent from the VCF.
parse_list SAMPLES "$SAMPLES_CSV"
require_non_empty_list "${#SAMPLES[@]}" Samples
validate_sample_names "${SAMPLES[@]}"
MISSING_BAM=()
for s in "${SAMPLES[@]}"; do
  [[ -f "$OUT/alignments/${s}.sorted.bam" ]] || MISSING_BAM+=("$s")
done
if (( ${#MISSING_BAM[@]} > 0 )); then
  echo "ERROR: no alignment for ${#MISSING_BAM[@]} of ${#SAMPLES[@]} requested sample(s):" >&2
  printf '  %s\n' "${MISSING_BAM[@]}" >&2
  echo "SampleRange must cover every sample: '0-$(( ${#SAMPLES[@]} - 1 ))' for this list." >&2
  exit 1
fi
echo "Concatenating ${#VCFS[@]} per-region VCF(s)."

# --allow-overlaps lets concat accept inputs that are not already in coordinate
# order, which matters because the region list can be in any order. --rm-dups
# exact then drops records that appear in more than one input: -a alone tolerates
# overlap but does not deduplicate, so padded or overlapping regions would
# otherwise produce repeated records.
#
# bcftools norm left-aligns indels and splits multiallelic records, which is what
# makes the VCF comparable against another callset. It runs after concat because
# left-alignment can move an indel's position.
REF="$OUT/reference/$REFERENCE_NAME"
bcftools concat --allow-overlaps --rm-dups exact --output-type u "${VCFS[@]}" \
  | bcftools norm --fasta-ref "$REF" --multiallelics -any \
      --output-type z --output "$MERGED"
bcftools index --force --tbi "$MERGED"

SUMMARY="$OUT/variant_summary.txt"
{
  echo "=== Variant Calling Summary ==="
  echo "Regions called: ${#VCFS[@]}"
  echo "Total variants: $(bcftools view --no-header "$MERGED" | wc -l)"
  echo "Samples:        $(bcftools view -h "$MERGED" | grep '^#CHROM' | cut -f10- | tr '\t' ' ')"
  echo ""
  echo "--- variants per contig ---"
  bcftools view --no-header "$MERGED" | awk '{print $1}' | sort | uniq -c \
    | awk '{printf "  %-12s %s\n", $2, $1}'
  echo ""
  echo "--- bcftools stats ---"
  # '|| true' on the greps: a no-match grep is exit 1, and as the last command of
  # this redirected group that would abort the script leaving $SUMMARY truncated
  # with nothing printed, since stdout is captured.
  bcftools stats "$MERGED" | { grep -E '^SN' || true; } | cut -f3-
} > "$SUMMARY"
cat "$SUMMARY"

# MultiQC exits 1 when it finds no analysis results to summarize, which is not a
# pipeline failure: the VCF above is the actual result, and the report is a
# convenience over it. Keep its output visible so a genuine error stays
# diagnosable.
echo "Building MultiQC report..."
if multiqc --force --outdir "$OUT/multiqc" "$OUT"; then
  echo "MultiQC report: $OUT/multiqc/multiqc_report.html"
else
  echo "MultiQC found nothing to summarize (exit $?); the merged VCF is unaffected."
fi
echo "Merged VCF: $MERGED"
