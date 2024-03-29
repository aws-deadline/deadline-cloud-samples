#!/bin/env python
import argparse
import os
import polars as pl
import matplotlib as mpl
import seaborn as sns
# This works because the "Environment Variables" job environment sets PYTHONPATH.
from progression_3_shared_library import add_standard_args, process_standard_args

# Use non-interactive backend
mpl.use("Agg")

parser = argparse.ArgumentParser(prog="process.py")
parser.add_argument("workspace_path", type=str)
add_standard_args(parser)
args = parser.parse_args()
process_standard_args(args)

os.chdir(args.workspace_path)
os.makedirs("output", exist_ok=True)

q = (
    pl.scan_csv("csv/dataset.csv")
    .filter(pl.col("Action Type") == "taskRun")
    .sort(by=pl.col("Frame (Task Param)"))
)

df = q.collect()

mpl.pyplot.figure(figsize=(48, 4.8))
sns.barplot(data=df, x="Frame (Task Param)", y="Duration (Seconds)")
mpl.pyplot.savefig("output/frame_time_barplot.png")
