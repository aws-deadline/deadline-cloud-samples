#!/usr/bin/env bash
# Create the .fai and bwa indexes once, if they are not already present.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

REFERENCE_DIR=""
REFERENCE_NAME=""
OUT=""
for arg in "$@"; do
  case "$arg" in
    --reference-dir=*)  REFERENCE_DIR="${arg#*=}" ;;
    --reference-name=*) REFERENCE_NAME="${arg#*=}" ;;
    --output-dir=*)     OUT="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$REFERENCE_DIR" --reference-dir
require_arg "$REFERENCE_NAME" --reference-name
require_arg "$OUT" --output-dir

REF="$REFERENCE_DIR/$REFERENCE_NAME"
mkdir -p "$OUT"

# The reference name is a name within the reference directory, so a value
# containing a separator would resolve outside the staged directory.
if [[ "$REFERENCE_NAME" != "$(basename "$REFERENCE_NAME")" ]]; then
  echo "ERROR: ReferenceFastaName must be a filename, not a path: $REFERENCE_NAME" >&2
  exit 1
fi

if [[ ! -f "$REF" ]]; then
  echo "ERROR: reference FASTA not found: $REF" >&2
  echo "ReferenceDir contains:" >&2
  ls -1 "$REFERENCE_DIR" >&2 || true
  exit 1
fi

# Assemble the reference and both indexes under $OUT/reference. Later steps
# rebuild this location from the OutputDir parameter rather than reading a path
# from here, because each step runs in its own session directory. Copying also
# leaves the staged input untouched, which matters when job attachments stages
# it read-only.
REF_DIR="$OUT/reference"
LOCAL_REF="$REF_DIR/$REFERENCE_NAME"
mkdir -p "$REF_DIR"
cp -f "$REF" "$LOCAL_REF"

if [[ -f "${REF}.fai" ]]; then
  cp -f "${REF}.fai" "${LOCAL_REF}.fai"
  echo "Reused the .fai staged beside the reference."
else
  samtools faidx "$LOCAL_REF"
  echo "Built ${LOCAL_REF}.fai"
fi

# A bwa index is a set of files sharing the reference's prefix, and bwa mem needs
# all of them, so a partial set is rebuilt rather than copied.
#
# 'bwa index -6' names them "<reference>.64.*" instead of "<reference>.*", and bwa
# looks for that variant first, so check for it the same way.
BWA_EXTS=(amb ann bwt pac sa)

# Echoes the infix of a complete index beside $1, or nothing if neither is complete.
complete_bwa_index_infix() {
  local _prefix="$1" _infix _ext _complete
  for _infix in ".64" ""; do
    _complete=1
    for _ext in "${BWA_EXTS[@]}"; do
      [[ -f "${_prefix}${_infix}.${_ext}" ]] || _complete=0
    done
    if [[ "$_complete" -eq 1 ]]; then
      printf '%s' "$_infix"
      return 0
    fi
  done
  return 1
}

# Clear both variants first. Reusing an OutputDir can leave an index from an
# earlier run here, and bwa looks for the ".64" one before the standard one, so a
# leftover ".64" set would be loaded in preference to whichever index this run
# just put in place.
for infix in ".64" ""; do
  for ext in "${BWA_EXTS[@]}"; do
    rm -f "${LOCAL_REF}${infix}.${ext}"
  done
done

if BWA_INFIX="$(complete_bwa_index_infix "$REF")"; then
  for ext in "${BWA_EXTS[@]}"; do
    cp -f "${REF}${BWA_INFIX}.${ext}" "${LOCAL_REF}${BWA_INFIX}.${ext}"
  done
  echo "Reused the bwa index staged beside the reference."
else
  bwa index "$LOCAL_REF"
  echo "Built the bwa index for $LOCAL_REF"
fi

echo "Reference ready at $LOCAL_REF"
ls -1 "$REF_DIR"
