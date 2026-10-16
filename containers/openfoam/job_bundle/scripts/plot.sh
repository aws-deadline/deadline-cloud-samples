#!/usr/bin/env bash
# Draw one centreline graph over every solved case and write a summary table.
# Usage: plot.sh OUTPUT_DIR TUTORIAL SOLVER
set -euo pipefail
shopt -s nullglob

output=$1
tutorial=$2
solver=$3

cases=("$output"/cases/nu-*/)
if [ "${#cases[@]}" -eq 0 ]; then
    echo "no solved cases under $output/cases" >&2
    exit 1
fi
cases=("${cases[@]%/}")

foam-plot profile "$output/plots/centreline.png" "${cases[@]}"

summary="$output/summary.txt"
{
    echo "OpenFOAM  $WM_PROJECT_VERSION"
    echo "tutorial  $tutorial"
    echo "solver    $solver"
    echo
    printf '%-12s %-8s %-12s %s\n' CASE NU LATEST_TIME EXECUTION_TIME
    for case_dir in "${cases[@]}"; do
        printf '%-12s %-8s %-12s %s\n' \
            "$(basename "$case_dir")" \
            "$(foamDictionary -entry nu -value "$case_dir/constant/transportProperties")" \
            "$(foamListTimes -case "$case_dir" -latestTime)" \
            "$(grep '^ExecutionTime' "$case_dir/log.$solver" | tail -1 | awk '{print $3 " s"}')"
    done
} > "$summary"
cat "$summary"
