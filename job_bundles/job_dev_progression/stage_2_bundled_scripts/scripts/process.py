#!/bin/env python
import argparse
import os
import polars as pl
import matplotlib as mpl
import seaborn as sns

# Use non-interactive backend
mpl.use("Agg")

parser = argparse.ArgumentParser(prog="process.py")
parser.add_argument("workspace_path", type=str)
args = parser.parse_args()

os.chdir(args.workspace_path)
os.makedirs("output", exist_ok=True)

df = pl.scan_csv("csv/dataset.csv").collect()

sns.histplot(data=df, x="Duration (Seconds)", hue="Action Type", bins=20)
mpl.pyplot.savefig("output/action_duration_histograms.png")
