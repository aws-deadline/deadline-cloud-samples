#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""preSubmission hook: expand the wedge CSV into the job's task parameters.

The job template defines the RenderWedge step with placeholder single-value
task parameter ranges. This hook reads the wedge CSV file, replaces each range
with one entry per CSV row, and prints the modified template on stdout under
the ``template`` key. The Deadline Cloud client uses that template for the
CreateJob call, so each CSV row becomes one task on the farm. The bundle's
template.yaml on disk is never modified.

How it works: the Deadline Cloud client runs this as a preSubmission hook
(configured in hooks.yaml). It passes the submission metadata as JSON on
stdin, including ``jobBundleDir`` and the resolved job parameter values. The
CSV path comes from the ``WedgeCsvFile`` job parameter, so a CSV chosen in the
GUI submitter or passed with ``-p WedgeCsvFile=...`` on the CLI is the one
that gets expanded.

Expected CSV columns (header row required, extra columns are ignored):

    wedge         -> WedgeName    (STRING; used in the output filename)
    roughness     -> Roughness    (FLOAT, 0.0-1.0)
    sun_rotation  -> SunRotation  (FLOAT, degrees)
    samples       -> Samples      (INT, > 0)

If the CSV is missing, empty, or has malformed values, the hook prints an
explanation to stderr and exits non-zero, which aborts the submission before
anything is uploaded.
"""
import csv
import json
import os
import re
import sys

import yaml

STEP_NAME = "RenderWedge"

# Maps a CSV column to (task parameter name, value coercion).
CSV_TO_TASK_PARAMETER = {
    "wedge": ("WedgeName", str),
    "roughness": ("Roughness", float),
    "sun_rotation": ("SunRotation", float),
    "samples": ("Samples", int),
}

# OpenJD allows at most 1024 values in a task parameter range.
MAX_ROWS = 1024


def fail(message):
    print(f"expand_wedge_csv: {message}", file=sys.stderr)
    sys.exit(1)


def read_wedge_rows(csv_path):
    """Read and validate the wedge CSV, returning a list of per-row dicts."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            fail(f"CSV file {csv_path} is empty.")
        columns = [name.strip().lower() for name in reader.fieldnames]
        missing = sorted(set(CSV_TO_TASK_PARAMETER) - set(columns))
        if missing:
            fail(
                f"CSV file {csv_path} is missing required column(s): {', '.join(missing)}. "
                f"Found columns: {', '.join(columns)}."
            )

        rows = []
        for line_number, row in enumerate(reader, start=2):
            # DictReader collects values beyond the header's columns under a None
            # key as a list; drop them rather than crashing on a stray comma.
            row = {
                (k or "").strip().lower(): v.strip()
                for k, v in row.items()
                if isinstance(v, str)
            }
            if not any(row.values()):
                continue  # Skip blank lines
            values = {}
            for column, (parameter, coerce) in CSV_TO_TASK_PARAMETER.items():
                try:
                    values[parameter] = coerce(row[column])
                except (ValueError, KeyError):
                    fail(
                        f"CSV file {csv_path} line {line_number}: could not read "
                        f"{coerce.__name__} value for column '{column}' "
                        f"(got {row.get(column)!r})."
                    )
            # The wedge name is substituted into the render step's shell command
            # and becomes part of the output filename, so restrict it to
            # filename-safe characters.
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", values["WedgeName"]):
                fail(
                    f"CSV file {csv_path} line {line_number}: 'wedge' must contain only "
                    f"letters, digits, '_', '.', and '-' (got {values['WedgeName']!r})."
                )
            if values["Samples"] <= 0:
                fail(f"CSV file {csv_path} line {line_number}: 'samples' must be > 0.")
            rows.append(values)

    if not rows:
        fail(f"CSV file {csv_path} contains no data rows.")
    if len(rows) > MAX_ROWS:
        fail(
            f"CSV file {csv_path} has {len(rows)} rows; Open Job Description allows "
            f"at most {MAX_ROWS} values per task parameter range."
        )
    names = [row["WedgeName"] for row in rows]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        fail(
            f"CSV file {csv_path} has duplicate wedge name(s): {', '.join(duplicates)}. "
            "Each row's output image is named after its wedge, so names must be unique."
        )
    return rows


def main():
    metadata = json.load(sys.stdin)
    bundle_dir = metadata["jobBundleDir"]

    # Resolve the CSV path from the WedgeCsvFile job parameter. The GUI and CLI
    # provide an absolute path; the bundle's parameter_values.yaml or template
    # default may be relative to the bundle directory.
    csv_path = metadata.get("parameters", {}).get("WedgeCsvFile") or "wedges.csv"
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(bundle_dir, csv_path)
    if not os.path.isfile(csv_path):
        fail(f"Wedge CSV file not found: {csv_path}")

    rows = read_wedge_rows(csv_path)

    with open(os.path.join(bundle_dir, "template.yaml"), encoding="utf-8") as f:
        template = yaml.safe_load(f)

    steps = {step.get("name"): step for step in template.get("steps", [])}
    if STEP_NAME not in steps:
        fail(f"Job template has no step named '{STEP_NAME}'.")
    task_parameters = {
        definition["name"]: definition
        for definition in steps[STEP_NAME]["parameterSpace"]["taskParameterDefinitions"]
    }

    # Replace each placeholder range with the column of CSV values. The step's
    # combination expression "(WedgeName, Roughness, SunRotation, Samples)" zips
    # the equal-length ranges together, so row N of the CSV becomes task N.
    for parameter, _ in CSV_TO_TASK_PARAMETER.values():
        if parameter not in task_parameters:
            fail(f"Step '{STEP_NAME}' has no task parameter named '{parameter}'.")
        task_parameters[parameter]["range"] = [row[parameter] for row in rows]

    print(
        f"Expanded {len(rows)} wedge row(s) from {os.path.basename(csv_path)} "
        f"into '{STEP_NAME}' task parameters: "
        + ", ".join(row["WedgeName"] for row in rows),
        file=sys.stderr,
    )

    # Emit the modified template. Match the on-disk format so the client parses it cleanly.
    print(json.dumps({"template": yaml.safe_dump(template, sort_keys=False)}))


if __name__ == "__main__":
    main()
