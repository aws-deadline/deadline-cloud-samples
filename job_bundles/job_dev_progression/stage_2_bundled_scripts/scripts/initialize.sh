#!/bin/env bash

# Configure the script to fail if any individual command fails.
set -euo pipefail

if [ -z "$2" ]; then
  echo "usage: initialize.sh input_data workspace_path"
  exit 1
fi

# Initialize the workspace
echo "Initializing the workspace directory $2"
mkdir -p "$2"
cd "$2"

# Copy the input CSV file
echo "Copying the input CSV file $1 to csv/dataset.csv"
mkdir -p csv
cp "$1" csv/dataset.csv

echo "Workspace initialization is complete"
