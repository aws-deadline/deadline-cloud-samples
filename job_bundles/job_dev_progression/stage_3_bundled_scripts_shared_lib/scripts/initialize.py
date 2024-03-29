#!/bin/env python
import argparse
import os
import shutil
# This works because the "Environment Variables" job environment sets PYTHONPATH.
from progression_3_shared_library import add_standard_args, process_standard_args

parser = argparse.ArgumentParser(prog="initialize.py")
parser.add_argument("input_csv_file", type=str)
parser.add_argument("workspace_path", type=str)
add_standard_args(parser)
args = parser.parse_args()
process_standard_args(args)

# Initialize the workspace
os.makedirs(args.workspace_path, exist_ok=True)
os.chdir(args.workspace_path)

# Copy the input CSV files
os.makedirs("csv", exist_ok=True)
shutil.copyfile(args.input_csv_file, "csv/dataset.csv")
