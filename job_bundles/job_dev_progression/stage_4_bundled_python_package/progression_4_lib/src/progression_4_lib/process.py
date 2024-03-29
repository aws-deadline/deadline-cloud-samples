#!/bin/env python
import argparse
import os
import polars as pl
import matplotlib as mpl
import seaborn as sns

from .standard_args import add_standard_args, process_standard_args


def process_data():
    q = pl.scan_csv("csv/dataset.csv").select(
        pl.col("Duration (Seconds)").cast(pl.Float64),
        pl.all().exclude("Duration (Seconds)"),
    )

    df = q.collect()

    mpl.pyplot.figure(figsize=(16, 4.8))
    g = sns.FacetGrid(data=df, col="Action Type", sharex=False)
    g.map(sns.histplot, "Duration (Seconds)", bins=10)
    mpl.pyplot.savefig("output/per_action_type_histogram.png")


def main():
    parser = argparse.ArgumentParser(prog="process.py")
    parser.add_argument("workspace_path", type=str)
    add_standard_args(parser)
    args = parser.parse_args()
    process_standard_args(args)

    os.chdir(args.workspace_path)
    os.makedirs("output", exist_ok=True)

    process_data()
