#!/bin/env python
import argparse
import os
import shutil

from .standard_args import add_standard_args, process_standard_args


def initialize_workspace(workspace_path):
    os.makedirs(workspace_path, exist_ok=True)
    os.chdir(workspace_path)


def copy_input_csv_files(input_csv_file):
    os.makedirs("csv", exist_ok=True)
    shutil.copyfile(input_csv_file, "csv/dataset.csv")


def main():
    parser = argparse.ArgumentParser(prog="initialize.py")
    parser.add_argument("input_csv_file", type=str)
    parser.add_argument("workspace_path", type=str)
    add_standard_args(parser)
    args = parser.parse_args()
    process_standard_args(args)

    initialize_workspace(args.workspace_path)
    copy_input_csv_files(args.input_csv_file)
