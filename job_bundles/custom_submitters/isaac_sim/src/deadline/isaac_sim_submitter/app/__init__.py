# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The Deadline Cloud for Isaac Sim app: ``deadline-physical-ai gui``.

A Qt window to pick a farm, queue and completed job, download chosen outputs, and submit
job bundles through the stock ``deadline bundle gui-submit`` dialog. It runs without Isaac
Sim. Started by the Isaac Sim extension (``--bridge``), it also replays trajectories and
adds USD files to the open stage, through the extension (:mod:`.protocol`).

* :mod:`.controllers`, :mod:`.cli_backend`, :mod:`.bundles`, :mod:`.settings`: state and
  CLI work, with no Qt; the app never imports ``boto3`` or the Deadline Cloud client and
  runs the ``deadline`` and ``deadline-physical-ai`` CLIs as child processes instead.
* :mod:`.bridge`, :mod:`.protocol`: the link to the extension, over stdin and stdout.
* :mod:`.qt_app`: the window. The only module that imports PySide6.
"""
