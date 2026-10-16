#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
KeyShot Task Script

This script handles individual render tasks by sending JSON commands to the KeyShot server
and monitoring STDOUT for progress, errors, and completion.

Usage:
    python task_manager.py --frame <num> --port <port> --output-path <path> --output-format <format> --render-device <device>
"""

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

SESSION_INFO_FILE = "keyshot_session_info.json"
TASK_TIMEOUT_SECONDS = 24 * 60 * 60  # 24 hours


def read_session_info() -> int:
    with open(SESSION_INFO_FILE, "r") as f:
        return int(json.load(f)["port"])


async def main() -> None:
    parser = argparse.ArgumentParser(description="KeyShot Task")
    parser.add_argument("--frame", type=int, required=True, help="Frame number to render")
    parser.add_argument("--output-path", required=True, help="Output file path template")
    parser.add_argument(
        "--output-format",
        required=True,
        choices=["PNG", "JPEG", "EXR", "TIFF8", "TIFF32", "PSD8", "PSD16", "PSD32"],
        help="Output format",
    )
    parser.add_argument(
        "--render-device", required=True, choices=["CPU", "GPU"], help="Render device"
    )
    parser.add_argument(
        "--override-render-device",
        type=str,
        choices=["True", "False"],
        help="Override render device setting",
    )
    parser.add_argument("--render-options", help="Render options JSON string")
    args = parser.parse_args()

    port = read_session_info()

    Path(args.output_path).parent.mkdir(parents=True, exist_ok=True)

    output_path = args.output_path.replace("%d", str(args.frame))

    print(f"Preparing render command for frame {args.frame}", flush=True)

    render_options = {}
    if args.render_options:
        render_options = json.loads(args.render_options)

    command = {
        "command": "render",
        "frame": args.frame,
        "output_path": output_path,
        "output_format": args.output_format,
        "render_device": args.render_device,
        "override_render_device": args.override_render_device == "True",
        "render_options": render_options,
    }

    print(f"Created render command: {json.dumps(command)}")

    print(f"Connecting to KeyShot server on port {port}", flush=True)

    return await send_command_and_monitor(command, args.frame, port)


PROGRESS_PATTERN = re.compile(r"Rendering:\s+(\d+(?:\.\d+)?)%", re.IGNORECASE)


def check_line_for_completion(line: str, frame: int) -> bool:
    if f"ADAPTOR_STATUS=Success FRAME={frame}" in line:
        return True

    if "ADAPTOR_STATUS=Error " in line:
        print(f"openjd_fail: {line}", file=sys.stderr)
        raise RuntimeError(line)

    if match := PROGRESS_PATTERN.search(line):
        progress = float(match.group(1))
        print(f"openjd_progress: {progress}")

    return False


async def send_command_and_monitor(command: dict, frame: int, port: int) -> None:
    try:
        reader, writer = await asyncio.open_connection("localhost", port)
        print(f"Connected to KeyShot server on port {port}", flush=True)

        command_json = json.dumps(command) + "\n"
        writer.write(command_json.encode())
        await writer.drain()
        print(f"Sent render command: {command_json.strip()}", flush=True)

        print(
            f"Monitoring logs for frame {frame} completion (timeout: {TASK_TIMEOUT_SECONDS}s)...",
            flush=True,
        )
        start_time = time.time()

        while time.time() - start_time < TASK_TIMEOUT_SECONDS:
            try:
                line_bytes = await asyncio.wait_for(reader.readline(), timeout=1.0)
            except asyncio.TimeoutError:
                # No new data, continue monitoring
                continue

            if not line_bytes:
                raise RuntimeError("ERROR: Socket connection closed by server")

            line = line_bytes.decode().strip()
            print(f"KeyShot: {line}", flush=True)

            if check_line_for_completion(line, frame):
                return

        raise RuntimeError(f"ERROR: Timeout waiting for frame {frame} to complete")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:  # noqa: E722
            # Ignore any errors while closing the connection since we're exiting
            pass


if __name__ == "__main__":
    asyncio.run(main())
