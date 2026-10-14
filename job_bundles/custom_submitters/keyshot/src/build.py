#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Build script for the KeyShot submitter.

Embeds the adaptor scripts into the submitter.py template to produce a final,
self-contained submitter.

Usage:
    python build.py --output <path>
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KeyShot submitter with embedded scripts")
    parser.add_argument(
        "--output", required=True, help="Output path for the built submitter script"
    )
    args = parser.parse_args()

    src_dir = Path(__file__).parent
    output_path = Path(args.output)

    # Define paths to source files
    submitter_path = src_dir / "submitter.py"
    session_manager_path = src_dir / "session_manager.py"
    keyshot_bridge_path = src_dir / "keyshot_bridge.py"
    task_manager_path = src_dir / "task_manager.py"
    keyshot_command_handler_path = src_dir / "keyshot_command_handler.py"

    submitter_content = submitter_path.read_text()

    # Replace placeholders with actual script contents
    final_content = submitter_content.replace(
        '"SESSION_MANAGER_SCRIPT"', json.dumps(session_manager_path.read_text())
    )
    final_content = final_content.replace(
        '"KEYSHOT_BRIDGE_SCRIPT"', json.dumps(keyshot_bridge_path.read_text())
    )
    final_content = final_content.replace(
        '"TASK_MANAGER_SCRIPT"', json.dumps(task_manager_path.read_text())
    )
    final_content = final_content.replace(
        '"KEYSHOT_COMMAND_HANDLER_SCRIPT"', json.dumps(keyshot_command_handler_path.read_text())
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"\nBuild successful. Final submitter written to: {output_path}")


if __name__ == "__main__":
    main()
