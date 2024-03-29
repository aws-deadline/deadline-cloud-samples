#!/bin/env bash

# Configure the script to fail if any individual command fails.
set -euo pipefail

if [ -z "$2" ]; then
  echo "usage: initialize.sh input_data workspace_path"
  exit 1
fi

# Initialize the workspace
mkdir -p "$2"
cd "$2"

# Copy the input CSV file
mkdir csv
cp "$1" csv/dataset.csv
