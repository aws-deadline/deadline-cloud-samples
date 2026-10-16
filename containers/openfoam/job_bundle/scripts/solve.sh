#!/usr/bin/env bash
# Copy the meshed case, solve it at one viscosity, then convert and plot the result.
# Usage: solve.sh BASE_CASE OUTPUT_DIR NU END_TIME SOLVER
set -euo pipefail

base=$1
output=$2
nu=$3
end_time=$4
solver=$5

mkdir -p "$output/cases" "$output/plots"
output=$(cd "$output" && pwd)
case_dir="$output/cases/nu-$nu"
rm -rf "$case_dir"
cp -a "$base" "$case_dir"
cd "$case_dir"

foamDictionary -entry nu -set "$nu" constant/transportProperties
foamDictionary -entry endTime -set "$end_time" system/controlDict

# Write about five time directories whatever the end time. bc because deltaT is a decimal.
delta_t=$(foamDictionary -entry deltaT -value system/controlDict)
steps=$(echo "$end_time / $delta_t" | bc)
interval=$((steps / 5 > 0 ? steps / 5 : 1))
foamDictionary -entry writeInterval -set "$interval" system/controlDict

log="log.$solver"
if ! "$solver" > "$log" 2>&1; then
    echo "$solver failed:" >&2
    tail -40 "$log" >&2
    exit 1
fi
grep '^ExecutionTime' "$log" | tail -1

foamToVTK -latestTime > log.foamToVTK 2>&1
foam-plot field "$output/plots/nu-$nu-velocity.png" "$case_dir"
