#!/usr/bin/env bash
# Helpers shared by the bundled scripts. Source it, do not run it:
#
#   source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
#
# Nothing here calls the bioinformatics tools. This file exists so that the two
# scripts which have to agree on a filename derive it from one implementation
# instead of two comments asking each other to stay in step.

# Split a comma-separated job parameter into the named array, trimming
# surrounding whitespace from every element so that "a, b" does not yield an
# entry with a leading space, which would otherwise surface as a confusing
# missing-file error or a filename containing a space.
#
# Only the surrounding whitespace goes. Deleting interior spaces too would
# rewrite 'tiny n' to 'tinyn' before validate_sample_names ever sees it, and the
# job would then fail on a filename the user never typed rather than on the name
# they did.
#
#   parse_list SAMPLES "tiny_n, tiny_t"
parse_list() {
  local -n _out="$1"
  local _raw="$2"
  local _i _elem
  IFS=',' read -r -a _out <<< "$_raw"
  for _i in "${!_out[@]}"; do
    _elem="${_out[$_i]}"
    _elem="${_elem#"${_elem%%[![:space:]]*}"}"
    _elem="${_elem%"${_elem##*[![:space:]]}"}"
    _out[$_i]="$_elem"
  done
}

# Reject a list parameter that has no entries.
#
# An empty parameter parses to zero elements, which every per-index task reports
# as "past the end of the list" while the gather's completeness checks find
# nothing missing to complain about. Without this the job would fail deep inside
# a tool -- bcftools handed no BAM arguments -- instead of naming the parameter
# that was left empty.
#
#   require_non_empty_list "${#SAMPLES[@]}" Samples
require_non_empty_list() {
  local _count="$1" _param="$2"
  if (( _count == 0 )); then
    echo "ERROR: the $_param parameter is empty; it needs at least one entry." >&2
    exit 1
  fi
}

# Sample names are pasted into input, output, and temporary paths, so reject
# anything that is not a plain filename component. A name like 'a/../../b' would
# otherwise resolve outside the directory it looks like it is in.
#
# Letters, digits, dot, underscore, and hyphen cover the sample naming that
# sequencing platforms produce; a leading dot is refused so a name cannot be
# '..' or produce a hidden file.
validate_sample_names() {
  local _name
  for _name in "$@"; do
    if [[ -z "$_name" ]]; then
      echo "ERROR: empty sample name in the Samples list." >&2
      exit 1
    fi
    if [[ ! "$_name" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]]; then
      echo "ERROR: invalid sample name '$_name'." >&2
      echo "Sample names may contain letters, digits, '.', '_', and '-', and must" >&2
      echo "not start with '.', because they are used to build file paths." >&2
      exit 1
    fi
  done
}

# Region strings may contain ':' and '*', which are not safe in filenames.
safe_region_name() {
  printf '%s' "$1" | tr ':*/|' '____'
}

# The per-region VCF path. CallVariants writes it and MergeVariants looks for
# it, so both must agree exactly; that is why this lives here rather than being
# spelled out twice.
#
# The index prefix keeps the name unique: the character mapping above is not
# injective ('1:100-200' and '1|100-200' both become '1_100-200'), and two
# parallel CallVariants tasks writing one file would corrupt it silently.
#
#   region_vcf_path "$OUT/vcf_by_region" 2 "1:134000-136999"
region_vcf_path() {
  local _dir="$1" _index="$2" _region="$3"
  printf '%s/region_%04d_%s.vcf.gz' \
    "$_dir" "$_index" "$(safe_region_name "$_region")"
}

# Fail with a message naming the flag a script needs but did not receive.
require_arg() {
  local _value="$1" _flag="$2"
  if [[ -z "$_value" ]]; then
    echo "ERROR: missing required argument $_flag" >&2
    exit 1
  fi
}

# Reject an unrecognized flag rather than ignoring it, so a typo in the job
# template fails loudly on the first task instead of silently using a default.
unknown_arg() {
  echo "ERROR: unrecognized argument: $1" >&2
  exit 1
}
