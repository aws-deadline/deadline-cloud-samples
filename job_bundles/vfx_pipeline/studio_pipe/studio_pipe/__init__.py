"""studio_pipe — a sample VFX pipeline launcher for AWS Deadline Cloud.

The package is deliberately small and readable. Its job is to be the single
"context" layer of a VFX pipeline:

    resolve a shot's context from the config hierarchy, then make the right
    software, plugins, and assets present and the environment set — wherever
    it is running (artist workstation or farm worker).

See the top-level README for the architecture and the end-to-end walkthrough.
"""

__version__ = "0.1.0"
