# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Generic physical AI helpers for AWS Deadline Cloud, and the ``deadline-physical-ai`` CLI.

Today this is what the Isaac Sim extension needs from Python with AWS access: list a
job's loadable outputs (:mod:`.outputs`) without downloading them, and download chosen
items with progress, hash-based resume and path-traversal checks (:mod:`.job_outputs`).
Nothing here depends on Isaac Sim, and importing the package imports nothing heavy.

Future work: split this generic core into its own pip package, which this one then
depends on. The ``isaac-sim`` CLI subcommands would stay with the Isaac Sim package.
"""
